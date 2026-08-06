"""AI Video & Image Generation router — Kling 2.5 Turbo (primary) + Gemini Veo (premium/image) + Modal (free).

Video generation priority (cost-optimized):
  - DEFAULT:  Kling 2.5 Turbo via fal.ai ($0.07/s, 720p + audio) — best value
  - PREMIUM:  Gemini Veo 3.1 ($0.08-0.40/s, 1080p + audio) — for image-to-video
  - FREE:     Modal.com self-hosted (free, low quality, ~90s cold start)

Image generation priority:
  1. Gemini Imagen (if GEMINI_API_KEY set)

Image generation priority:
  1. Gemini Imagen (if GEMINI_API_KEY set)
  2. Modal.com serverless GPU (if MODAL_IMAGE_URL set)
  3. fal.ai Flux Schnell (if FAL_KEY set)
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import CurrentUser, SessionDep
from prachar_shared.config import get_settings

router = APIRouter(prefix="/video", tags=["video-gen"])
log = logging.getLogger(__name__)

# ─── Gemini Veo model IDs (per tier) ───────────────────────────────────────
VEO_MODELS = {
    "lite": "veo-3.1-lite-generate-preview",
    "fast": "veo-3.1-fast-generate-preview",
    "standard": "veo-3.1-generate-preview",
}

# Per-second cost estimates (for display + budget guard)
VEO_TIER_COST_PER_SEC = {
    "lite": 0.08,      # 1080p with audio
    "fast": 0.12,      # 1080p with audio
    "standard": 0.40,  # 1080p with audio
}

# fal.ai models — Kling 2.5 Turbo is the DEFAULT (cheapest with audio)
# Pricing: $0.07/s at 720p with audio = $0.56 for 8s (vs Veo $0.64-3.20)
FAL_MODELS = {
    "kling_turbo": "fal-ai/kling-video/kling-2.5-turbo/text-to-video",
    "kling": "kwaivgi/kling-v3.0-pro/text-to-video",
    "ltx": "fal-ai/ltx-2.3/text-to-video",
    "seedance_fast": "bytedance/seedance-2.0/fast/text-to-video",
    "seedance": "bytedance/seedance-2.0/text-to-video",
    "wan_fast": "wan-video/wan-2.2-t2v-fast",
    "pixverse": "fal-ai/pixverse/pixverse-v6/text-to-video",
}

# Default fal.ai model (best quality-to-price with audio)
FAL_DEFAULT_MODEL = "kling_turbo"
FAL_DEFAULT_COST_PER_SEC = 0.07  # 720p with audio

ASPECT_RATIOS = {
    "reel": "9:16",
    "short": "9:16",
    "square": "1:1",
    "landscape": "16:9",
    "story": "9:16",
}

# Map video_type → Gemini aspect ratio string
GEMINI_ASPECT_RATIOS = {
    "reel": "9:16",
    "short": "9:16",
    "square": "1:1",
    "landscape": "16:9",
    "story": "9:16",
}


# ─── Request / Response models ─────────────────────────────────────────────

class VideoGenRequest(BaseModel):
    prompt: str
    quality: str = "lite"  # preview | lite | fast | standard
    duration: str | int = "5"  # seconds (Gemini Veo supports 4-8s)
    resolution: str = "1080p"
    aspect_ratio: str = "16:9"
    video_type: str = "landscape"
    with_audio: bool = True
    # Image-to-video: base64-encoded image to use as the first frame
    image_base64: str = ""
    # Legacy field kept for backward compatibility with old clients
    model: str = ""


class ImageGenRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 4


class VideoGenResponse(BaseModel):
    video_url: str
    model: str
    duration: str
    resolution: str
    generation_time: float = 0.0
    gpu_cost_estimate: str = ""
    quality_tier: str = "lite"


class ImageGenResponse(BaseModel):
    image_url: str
    model: str
    generation_time: float = 0.0


def _get_settings():
    return get_settings()


def _get_gemini_api_key() -> str | None:
    s = _get_settings()
    key = getattr(s, "gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    return key.strip() or None


def _get_modal_video_url() -> str | None:
    s = _get_settings()
    url = getattr(s, "modal_video_url", "") or os.environ.get("MODAL_VIDEO_URL", "")
    return url.strip() or None


def _get_modal_image_url() -> str | None:
    s = _get_settings()
    url = getattr(s, "modal_image_url", "") or os.environ.get("MODAL_IMAGE_URL", "")
    return url.strip() or None


def _normalize_quality(req: VideoGenRequest) -> str:
    """Resolve the quality tier, accounting for legacy `model` field."""
    q = (req.quality or "").strip().lower()
    if q in VEO_MODELS or q == "preview":
        return q
    # Map legacy model values to tiers
    legacy = (req.model or "").strip().lower()
    if legacy == "ltx":
        return "lite"
    if legacy in ("seedance_fast", "wan_fast"):
        return "fast"
    if legacy in ("seedance", "kling"):
        return "standard"
    # Default
    return "lite"


def _snap_veo_duration(sec: int) -> int:
    """Snap duration to nearest valid Veo value (4, 6, or 8 seconds only).
    When equidistant, prefer the longer duration (more value for the user)."""
    valid = [8, 6, 4]  # reversed so ties prefer longer
    return min(valid, key=lambda v: abs(v - sec))


# ─── Video generation endpoint ──────────────────────────────────────────────

@router.post("/generate", response_model=VideoGenResponse)
async def generate_video(
    req: VideoGenRequest,
    user: CurrentUser,
    session: SessionDep,
) -> VideoGenResponse:
    """Generate a real AI video from a text prompt.

    Provider priority (cost-optimized):
      - preview/standard: Kling 2.5 Turbo via fal.ai ($0.07/s, 720p + audio) — DEFAULT
      - standard (premium): Gemini Veo 3.1 ($0.08-0.40/s, 1080p + audio) — if Gemini key set
      - image-to-video: Gemini Veo (only Veo supports image input)

    Fallback chain: Kling (fal.ai) → Gemini Veo → Modal.com (free preview)
    """
    from ..deps import get_tenant_plan
    from prachar_shared.plans import get_plan

    quality = _normalize_quality(req)
    enhanced_prompt = req.prompt.strip()
    duration_raw = str(req.duration).replace("s", "")
    duration_sec = int(duration_raw)
    # Kling supports 5/10s, Veo Lite supports 4/6/8s — clamp to 5-8 for Kling,
    # snap to nearest valid Veo value (4/6/8) when using Veo
    duration_sec = max(5, min(8, duration_sec))

    # --- Enforce plan-based quality tier cap ---
    plan_key = await get_tenant_plan(session, user)
    plan = get_plan(plan_key)
    if plan:
        tier_rank = {"preview": 0, "lite": 1, "fast": 2, "standard": 3}
        max_tier = plan.video_quality_tier
        if tier_rank.get(quality, 1) > tier_rank.get(max_tier, 1):
            log.info(
                "Downgrading video quality %s → %s for tenant plan=%s",
                quality, max_tier, plan_key,
            )
            quality = max_tier

    aspect = ASPECT_RATIOS.get(req.video_type, req.aspect_ratio)

    # --- Image-to-video: only Veo supports this, so use Veo directly ---
    if req.image_base64:
        gemini_key = _get_gemini_api_key()
        if gemini_key:
            try:
                log.info("Using Gemini Veo for image-to-video (only Veo supports image input)")
                return await _call_gemini_veo(
                    api_key=gemini_key,
                    prompt=enhanced_prompt,
                    quality="standard" if quality == "standard" else "lite",
                    duration_sec=_snap_veo_duration(duration_sec),
                    aspect_ratio=GEMINI_ASPECT_RATIOS.get(req.video_type, req.aspect_ratio),
                    with_audio=req.with_audio,
                    image_base64=req.image_base64,
                )
            except HTTPException:
                raise
            except Exception as e:
                log.error("Gemini Veo image-to-video failed: %s: %s", type(e).__name__, str(e)[:300])
        # If no Gemini or Veo failed, fall through to text-to-video with Kling

    # --- PRIMARY: Kling 2.5 Turbo via fal.ai ($0.07/s with audio) ---
    fal_key = _get_settings().fal_key.strip()
    if fal_key:
        log.info("Using Kling 2.5 Turbo via fal.ai ($0.07/s, 720p + audio)")
        req_copy = req.model_copy()
        req_copy.model = FAL_DEFAULT_MODEL
        try:
            return await _call_fal_video(fal_key, req_copy, enhanced_prompt, aspect)
        except HTTPException as e:
            log.error("Kling (fal.ai) failed: %s", str(e.detail)[:200])
        except Exception as e:
            log.error("Kling (fal.ai) failed: %s: %s", type(e).__name__, str(e)[:200])

    # --- FALLBACK: Gemini Veo (if Gemini key configured) ---
    gemini_key = _get_gemini_api_key()
    if gemini_key and quality in VEO_MODELS:
        try:
            log.info("Falling back to Gemini Veo %s", quality)
            return await _call_gemini_veo(
                api_key=gemini_key,
                prompt=enhanced_prompt,
                quality=quality,
                duration_sec=_snap_veo_duration(duration_sec),
                aspect_ratio=GEMINI_ASPECT_RATIOS.get(req.video_type, req.aspect_ratio),
                with_audio=req.with_audio,
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error("Gemini Veo failed: %s: %s", type(e).__name__, str(e)[:300])
        except HTTPException as e:
            log.error("fal.ai failed: %s", str(e.detail)[:200])
        except Exception as e:
            log.error("fal.ai failed: %s: %s", type(e).__name__, str(e)[:200])

    # --- Last resort: Modal preview ---
    modal_url = _get_modal_video_url()
    if modal_url:
        try:
            log.info("Last resort: Modal.com preview")
            return await _call_modal_video(modal_url, enhanced_prompt, req)
        except Exception as e:
            log.error("Modal last-resort failed: %s", str(e)[:200])

    raise HTTPException(
        status_code=500,
        detail="No video generation service configured. Set GEMINI_API_KEY (recommended), FAL_KEY, or MODAL_VIDEO_URL in .env",
    )


# ─── Image generation endpoint ──────────────────────────────────────────────

@router.post("/generate-image", response_model=ImageGenResponse)
async def generate_image(
    req: ImageGenRequest,
    user: CurrentUser,
) -> ImageGenResponse:
    """Generate an image from text.

    Priority:
    1. Gemini Imagen (if GEMINI_API_KEY set) — best quality
    2. Modal.com serverless GPU (if MODAL_IMAGE_URL set)
    3. fal.ai Flux Schnell (if FAL_KEY set)
    """
    # Option 1: Gemini Imagen
    gemini_key = _get_gemini_api_key()
    if gemini_key:
        try:
            log.info("Using Gemini Imagen for image generation")
            return await _call_gemini_imagen(api_key=gemini_key, prompt=req.prompt, width=req.width, height=req.height)
        except Exception as e:
            log.error("Gemini Imagen failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 2: Modal.com serverless GPU
    modal_url = _get_modal_image_url()
    if modal_url:
        try:
            log.info("Using Modal.com GPU for image generation")
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                resp = await client.post(
                    modal_url,
                    json={
                        "prompt": req.prompt,
                        "width": req.width,
                        "height": req.height,
                        "num_inference_steps": req.num_inference_steps,
                    },
                    timeout=300,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    url = data.get("url", "")
                    return ImageGenResponse(
                        image_url=url,
                        model=data.get("model", "modal-sdxl"),
                        generation_time=data.get("generation_time", 0),
                    )
                raise RuntimeError(f"Modal image gen failed: {resp.text[:200]}")
        except Exception as e:
            log.error("Modal image gen failed: %s", str(e)[:200])

    # Option 3: fal.ai fallback
    fal_key = _get_settings().fal_key.strip()
    if fal_key:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://fal.run/fal-ai/flux/schnell",
                    headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                    json={"prompt": req.prompt, "image_size": {"width": req.width, "height": req.height}, "num_inference_steps": req.num_inference_steps},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    url = data.get("images", [{}])[0].get("url", "")
                    if url:
                        return ImageGenResponse(image_url=url, model="flux-schnell-fal")
        except Exception:
            pass

    raise HTTPException(status_code=500, detail="No image generation service available")


# ─── Gemini Veo implementation ──────────────────────────────────────────────

async def _call_gemini_veo(
    api_key: str,
    prompt: str,
    quality: str,
    duration_sec: int,
    aspect_ratio: str,
    with_audio: bool,
    image_base64: str = "",
) -> VideoGenResponse:
    """Call Gemini Veo 3.1 via the google-genai SDK for video generation.

    Supports both text-to-video and image-to-video (when image_base64 is provided).
    Uses the long-running operation pattern: start generation, poll until done,
    fetch the resulting video URI, then download and return a streamable URL.
    """
    from google import genai
    from google.genai import types as gtypes
    import asyncio, base64

    model_id = VEO_MODELS[quality]
    client = genai.Client(api_key=api_key)

    # Veo generate_videos config
    config = gtypes.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        number_of_videos=1,
        duration_seconds=duration_sec,
    )

    # Build image object for image-to-video if provided
    image_obj = None
    if image_base64:
        img_bytes = base64.b64decode(image_base64)
        image_obj = gtypes.Image(image_bytes=img_bytes, mime_type="image/png")
        log.info("Gemini Veo: model=%s prompt=%r dur=%ds aspect=%s IMAGE=%dKB",
                 model_id, prompt[:80], duration_sec, aspect_ratio, len(img_bytes)//1024)
    else:
        log.info("Gemini Veo: model=%s prompt=%r dur=%ds aspect=%s", model_id, prompt[:80], duration_sec, aspect_ratio)

    # Start the long-running operation
    kwargs: dict[str, Any] = dict(model=model_id, prompt=prompt, config=config)
    if image_obj:
        kwargs["image"] = image_obj
    operation = client.models.generate_videos(**kwargs)

    # Poll until the operation completes (Veo takes 60-180s typically)
    max_wait = 600  # 10 min hard cap
    poll_interval = 5
    elapsed = 0
    while not operation.done and elapsed < max_wait:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        operation = client.operations.get(operation=operation)
        log.info("Gemini Veo polling: elapsed=%ds done=%s", elapsed, operation.done)

    if not operation.done:
        raise HTTPException(status_code=504, detail=f"Gemini Veo timed out after {elapsed}s")

    # Extract the generated video
    op_response = getattr(operation, "response", None)
    videos = getattr(op_response, "generated_videos", None) if op_response else None
    if not videos:
        raise HTTPException(status_code=500, detail="Gemini Veo returned no videos")

    video = videos[0]
    # SDK v1.29+: video.video.uri (not video.uri)
    video_obj = getattr(video, "video", None)
    video_uri = ""
    if video_obj:
        video_uri = getattr(video_obj, "uri", "") or ""
    if not video_uri:
        video_uri = getattr(video, "uri", "") or ""
    if not video_uri:
        raise HTTPException(status_code=500, detail="Gemini Veo returned empty video URI")

    # The URI is a Google Cloud Storage path; we need to download via the SDK
    # and either return a presigned URL or save to our storage.
    # For now, use the SDK's file download to a temp URL via client.files.download
    try:
        # Download the video bytes and re-upload to a publicly accessible location.
        # In production this should go to S3/MinIO. For now, we use the
        # google-genai client's download helper which returns bytes.
        video_bytes = await asyncio.to_thread(_download_gemini_video, client, video)
        # Upload to our storage (S3/MinIO) and return the URL.
        # Fallback: return the raw GCS URI (works only with auth).
        video_url = await _store_video_bytes(video_bytes, f"veo_{quality}_{duration_sec}s.mp4")
    except Exception as e:
        log.warning("Could not download/re-store Veo video, returning raw URI: %s", str(e)[:200])
        video_url = video_uri

    cost_per_sec = VEO_TIER_COST_PER_SEC.get(quality, 0.08)
    total_cost = cost_per_sec * duration_sec

    return VideoGenResponse(
        video_url=video_url,
        model=f"gemini-veo-{quality}",
        duration=f"{duration_sec}s",
        resolution="1080p",
        generation_time=float(elapsed),
        gpu_cost_estimate=f"~${total_cost:.2f} (Gemini Veo 3.1 {quality.capitalize()} 1080p{' + audio' if with_audio else ''})",
        quality_tier=quality,
    )


def _download_gemini_video(client, video) -> bytes:
    """Download video bytes from Gemini via the SDK.

    SDK v1.29+ returns bytes directly from files.download().
    """
    file_ref = getattr(video, "video", None) or video
    return client.files.download(file=file_ref)


async def _store_video_bytes(data: bytes, filename: str) -> str:
    """Store video bytes and return a URL.

    Uses S3/MinIO if configured, otherwise returns a data URL (base64) as a
    fallback for local dev. In production this should upload to S3 and return
    a presigned URL.
    """
    import base64
    # Fallback: return a data URL (works in browser, not ideal for production)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:video/mp4;base64,{b64}"


# ─── Gemini Image generation (generate_content with image models) ───────────

async def _call_gemini_imagen(api_key: str, prompt: str, width: int, height: int) -> ImageGenResponse:
    """Generate an image using Gemini's image-capable models.

    Uses generate_content with response_modalities=['IMAGE','TEXT'] since the
    dedicated generate_images API is deprecated and Imagen models are no longer
    available to new users. Gemini 2.5 Flash Image is the primary model.
    """
    from google import genai
    from google.genai import types as gtypes
    import asyncio, base64, time

    client = genai.Client(api_key=api_key)
    aspect = _aspect_ratio_from_dims(width, height)
    # Enhance prompt with aspect ratio guidance
    full_prompt = f"{prompt}. Aspect ratio: {aspect}. High quality, professional."

    start = time.time()
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash-image",
        contents=full_prompt,
        config=gtypes.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    if not response.candidates:
        raise RuntimeError("Gemini image model returned no candidates")

    parts = response.candidates[0].content.parts
    img_bytes = None
    for p in parts:
        inline = getattr(p, "inline_data", None)
        if inline and inline.data:
            img_bytes = inline.data
            break

    if not img_bytes:
        raise RuntimeError("Gemini image model returned no image data")

    b64 = base64.b64encode(img_bytes).decode("ascii")
    url = f"data:image/png;base64,{b64}"

    return ImageGenResponse(
        image_url=url,
        model="gemini-2.5-flash-image",
        generation_time=time.time() - start,
    )


def _aspect_ratio_from_dims(width: int, height: int) -> str:
    """Convert width/height to Imagen aspect ratio string."""
    if width == height:
        return "1:1"
    if width > height:
        return "16:9" if width / height > 1.5 else "4:3"
    return "9:16" if height / width > 1.5 else "3:4"


# ─── Modal.com (preview tier) ───────────────────────────────────────────────

async def _call_modal_video(modal_url: str, prompt: str, req: VideoGenRequest) -> VideoGenResponse:
    """Call Modal.com serverless GPU for video generation (preview tier)."""
    duration_sec = int(req.duration.replace("s", "")) if req.duration.endswith("s") else int(req.duration)
    num_frames = 16 if duration_sec <= 5 else 24

    async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
        resp = await client.post(
            modal_url,
            json={
                "prompt": prompt,
                "duration": duration_sec,
                "num_frames": num_frames,
            },
            timeout=600,
        )
        if resp.status_code == 200:
            data = resp.json()
            video_url = data.get("url", "")
            return VideoGenResponse(
                video_url=video_url,
                model=data.get("model", "modal-animatediff"),
                duration=req.duration,
                resolution=req.resolution,
                generation_time=data.get("generation_time", 0),
                gpu_cost_estimate="~$0.01-0.02 (Modal T4 serverless, preview quality)",
                quality_tier="preview",
            )
        raise RuntimeError(f"Modal video gen failed: {resp.text[:200]}")


# ─── fal.ai (fallback) ──────────────────────────────────────────────────────

async def _call_fal_video(fal_key: str, req: VideoGenRequest, prompt: str, aspect: str) -> VideoGenResponse:
    """Call fal.ai for video generation (Kling 2.5 Turbo primary, others fallback)."""
    model_id = FAL_MODELS.get(req.model, FAL_MODELS[FAL_DEFAULT_MODEL])
    submit_url = f"https://queue.fal.run/{model_id}"
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}

    # Build payload based on model
    payload: dict[str, Any] = {"prompt": prompt}

    # Kling 2.5 Turbo: supports duration, aspect_ratio, negative_prompt
    if "kling-2.5-turbo" in model_id or "kling" in model_id:
        duration_val = str(req.duration).replace("s", "")
        payload["duration"] = duration_val  # "5" or "10" (Kling supports these)
        payload["aspect_ratio"] = aspect
        payload["negative_prompt"] = "blur, distort, and low quality, low resolution, watermark"
    elif "seedance" in model_id:
        payload["duration"] = str(req.duration).replace("s", "")
        payload["aspect_ratio"] = aspect
    elif "ltx" in model_id:
        payload["duration"] = str(req.duration).replace("s", "")
        payload["resolution"] = req.resolution
    elif "pixverse" in model_id:
        payload["duration"] = str(req.duration).replace("s", "")
        payload["resolution"] = req.resolution
    else:
        payload["resolution"] = req.resolution

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(submit_url, headers=headers, json=payload)
        if resp.status_code == 403:
            detail = resp.json().get("detail", "fal.ai balance exhausted")
            raise HTTPException(status_code=402, detail=f"fal.ai: {detail}")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"fal.ai error: {resp.text[:200]}")

        result = resp.json()
        request_id = result.get("request_id")
        if not request_id:
            video_url = _extract_video_url(result)
            if video_url:
                dur_sec = int(str(req.duration).replace("s", ""))
                cost = dur_sec * FAL_DEFAULT_COST_PER_SEC
                return VideoGenResponse(
                    video_url=video_url, model=model_id, duration=req.duration,
                    resolution="720p", quality_tier="kling-turbo",
                    gpu_cost_estimate=f"~${cost:.2f} (Kling 2.5 Turbo 720p + audio)",
                )
            raise HTTPException(status_code=500, detail="fal.ai returned no request_id")

        log.info("fal.ai request %s, polling...", request_id)
        status_url = f"https://queue.fal.run/{model_id}/requests/{request_id}/status"
        result_url = f"https://queue.fal.run/{model_id}/requests/{request_id}"

        for attempt in range(120):
            import asyncio
            await asyncio.sleep(2)
            status_resp = await client.get(status_url, headers=headers)
            if status_resp.status_code != 200:
                continue
            status_data = status_resp.json()
            status = status_data.get("status", "")
            log.info("fal.ai [%d]: %s", attempt, status)

            if status == "COMPLETED":
                result_resp = await client.get(result_url, headers=headers)
                if result_resp.status_code == 200:
                    video_url = _extract_video_url(result_resp.json())
                    if video_url:
                        dur_sec = int(str(req.duration).replace("s", ""))
                        cost = dur_sec * FAL_DEFAULT_COST_PER_SEC
                        return VideoGenResponse(
                            video_url=video_url,
                            model=model_id,
                            duration=req.duration,
                            resolution="720p",
                            quality_tier="kling-turbo",
                            generation_time=attempt * 2,
                            gpu_cost_estimate=f"~${cost:.2f} (Kling 2.5 Turbo 720p + audio)",
                        )
                raise HTTPException(status_code=500, detail="fal.ai completed but no video URL")
            if status == "FAILED":
                raise HTTPException(status_code=502, detail=f"fal.ai failed: {status_data.get('error', 'unknown')}")

        raise HTTPException(status_code=504, detail="fal.ai timed out")


def _extract_video_url(data: dict) -> str | None:
    """Extract video URL from fal.ai response."""
    if isinstance(data.get("video"), dict):
        return data["video"].get("url")
    if isinstance(data.get("video"), str):
        return data["video"]
    if isinstance(data.get("output"), dict):
        out = data["output"]
        if isinstance(out.get("video"), dict):
            return out["video"].get("url")
        if isinstance(out.get("video"), str):
            return out["video"]
    for key in ("url", "video_url", "output_url"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None
