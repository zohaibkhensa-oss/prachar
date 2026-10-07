"""AI Video & Image Generation router — Grok Imagine 1.5 (primary) + Gemini Veo (fallback).

Video generation priority (cost-optimized):
  - DEFAULT:  Grok Imagine 1.5 via fal.ai (~$0.14/s, 720p + native audio) — best value
  - FALLBACK: Gemini Veo 3.1 ($0.08-0.40/s, 1080p + audio)

Image generation priority:
  1. fal.ai Seedream V4.5 (if FAL_KEY set) — best quality, text rendering
  2. Gemini Imagen (if GEMINI_API_KEY set) — fallback

Image editing:
  1. fal.ai FLUX Kontext Pro ($0.04/image) — instruction-based edits with reference image
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from prachar_shared.config import get_settings
from prachar_shared.redis_utils import normalize_redis_url
from pydantic import BaseModel

from ..deps import CurrentUser, SessionDep

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

# fal.ai model — Wan 3.0 is the DEFAULT (best capabilities + cheapest)
# 1080p, up to 30s per clip, native audio, text-to-video + image-to-video + reference-to-video
# Pricing: ~$0.12/s at 1080p with audio
FAL_MODELS = {
    "wan": "alibaba/wan-3.0/text-to-video",
    "wan3": "alibaba/wan-3.0/text-to-video",
    "wan_image": "alibaba/wan-3.0/image-to-video",
    "wan_reference": "alibaba/wan-3.0/reference-to-video",
}

# Default fal.ai model
FAL_DEFAULT_MODEL = "wan"
FAL_DEFAULT_COST_PER_SEC = 0.12  # 1080p with audio

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


class ImageEditRequest(BaseModel):
    prompt: str          # Instruction-based edit prompt (e.g. "change the car to blue")
    image_url: str       # Reference image URL to edit
    guidance_scale: float = 2.5
    num_inference_steps: int = 28
    seed: int | None = None


class VideoGenResponse(BaseModel):
    video_url: str
    model: str
    duration: str
    resolution: str
    generation_time: float = 0.0
    gpu_cost_estimate: str = ""
    quality_tier: str = "lite"


class TTSRequest(BaseModel):
    prompt: str          # Text to convert to speech (supports natural-language style instructions)
    voice: str = "Kore"  # One of 30 voice presets
    model: str = "gemini-2.5-flash-tts"  # gemini-2.5-flash-tts or gemini-2.5-pro-tts
    speakers: list[dict[str, str]] | None = None  # Multi-speaker: [{"voice": "Charon", "speaker_id": "Host"}, ...]


class TTSResponse(BaseModel):
    audio_url: str
    model: str
    generation_time: float = 0.0


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


def _normalize_quality(req: VideoGenRequest) -> str:
    """Resolve the quality tier, accounting for legacy `model` field."""
    q = (req.quality or "").strip().lower()
    if q in VEO_MODELS or q == "preview":
        return q
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
      - DEFAULT: Wan 3.0 via fal.ai ($0.12/s, 1080p + audio)
      - FALLBACK: Gemini Veo 3.1 ($0.08-0.40/s, 1080p + audio)

    NOTE: This endpoint blocks until generation completes (up to 600s).
    For long-running generation, use POST /video/generate-async instead,
    which dispatches to a Celery worker and returns a job ID immediately.
    """
    from prachar_shared.plans import get_plan

    from ..deps import get_tenant_plan

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

    raise HTTPException(
        status_code=500,
        detail="No video generation service configured. Set GEMINI_API_KEY (recommended) or FAL_KEY in .env",
    )


# ─── Async video generation (Celery) ─────────────────────────────────────────

class AsyncVideoGenResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str = "Video generation dispatched to worker"


@router.post("/generate-async", response_model=AsyncVideoGenResponse)
async def generate_video_async(
    req: VideoGenRequest,
    user: CurrentUser,
    session: SessionDep,
) -> AsyncVideoGenResponse:
    """Submit a video generation job to the Celery worker.

    Returns immediately with a job_id. Poll GET /video/jobs/{job_id} for status.
    This avoids blocking the HTTP request for up to 600 seconds.
    """
    import uuid as _uuid
    try:
        from prachar_workers.tasks import generate_video_task
    except ImportError:
        # Workers not installed — fall back to sync generation
        raise HTTPException(
            status_code=503,
            detail="Async video generation requires the worker package. Use POST /video/generate instead.",
        ) from None

    job_id = str(_uuid.uuid4())
    task = generate_video_task.delay(
        job_id=job_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        prompt=req.prompt,
        quality=req.quality,
        duration=str(req.duration),
        resolution=req.resolution,
        aspect_ratio=req.aspect_ratio,
        video_type=req.video_type,
        with_audio=req.with_audio,
        image_base64=req.image_base64,
        model=req.model,
    )
    log.info("Async video job dispatched: job_id=%s task_id=%s", job_id, task.id)
    return AsyncVideoGenResponse(job_id=job_id, status="pending")


@router.get("/jobs/{job_id}")
async def get_video_job_status(job_id: str, user: CurrentUser) -> dict:
    """Get the status of an async video generation job."""
    try:
        import redis as _redis
        from prachar_shared.config import get_settings
        s = get_settings()
        r = _redis.from_url(normalize_redis_url(s.redis_url), decode_responses=True)
        key = f"video_job:{job_id}"
        data = r.hgetall(key)
        r.close()
        if not data:
            raise HTTPException(status_code=404, detail="job not found")
        # Verify tenant owns this job
        if data.get("tenant_id") != str(user.tenant_id):
            raise HTTPException(status_code=403, detail="job does not belong to your tenant")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to query job: {str(e)[:200]}") from e


# ─── Image generation endpoint ──────────────────────────────────────────────

@router.post("/generate-image", response_model=ImageGenResponse)
async def generate_image(
    req: ImageGenRequest,
    user: CurrentUser,
) -> ImageGenResponse:
    """Generate an image from text (FastAPI endpoint)."""
    return await _generate_image_core(
        prompt=req.prompt,
        width=req.width,
        height=req.height,
        num_inference_steps=req.num_inference_steps,
    )


async def _generate_image_core(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
) -> ImageGenResponse:
    """Generate an image from text — core logic, callable from tools.

    Priority:
    1. fal.ai Seedream V4.5 (if FAL_KEY set) — best quality, text rendering
    2. Gemini Imagen (if GEMINI_API_KEY set) — fallback
    """
    # Map width/height to Seedream image_size enum
    if width == height:
        image_size = "square_hd"
    elif width > height:
        image_size = "landscape_16_9" if width / height > 1.5 else "landscape_4_3"
    else:
        image_size = "portrait_16_9" if height / width > 1.5 else "portrait_4_3"

    # Option 1: fal.ai Seedream V4.5
    fal_key = _get_settings().fal_key.strip()
    if fal_key:
        try:
            import os
            os.environ["FAL_KEY"] = fal_key
            import fal_client
            log.info("Using Seedream V4.5 for image generation")
            data = await fal_client.subscribe_async(
                "fal-ai/bytedance/seedream/v4.5/text-to-image",
                {
                    "prompt": prompt,
                    "image_size": image_size,
                    "num_images": 1,
                    "enable_safety_checker": True,
                },
            )
            images = data.get("images", [])
            if images and images[0].get("url"):
                return ImageGenResponse(image_url=images[0]["url"], model="seedream-v4.5")
        except Exception as e:
            log.error("Seedream V4.5 failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 2: Gemini Imagen (fallback)
    gemini_key = _get_gemini_api_key()
    if gemini_key:
        try:
            log.info("Using Gemini Imagen for image generation (fallback)")
            return await _call_gemini_imagen(api_key=gemini_key, prompt=prompt, width=width, height=height)
        except Exception as e:
            log.error("Gemini Imagen failed: %s: %s", type(e).__name__, str(e)[:200])

    raise HTTPException(status_code=500, detail="No image generation service available")


# ─── Image editing endpoint (FLUX Kontext Pro) ──────────────────────────────

@router.post("/edit-image", response_model=ImageGenResponse)
async def edit_image(
    req: ImageEditRequest,
    user: CurrentUser,
) -> ImageGenResponse:
    """Edit an existing image using instruction-based prompts (FLUX Kontext Pro)."""
    return await _edit_image_core(
        prompt=req.prompt,
        image_url=req.image_url,
        guidance_scale=req.guidance_scale,
        num_inference_steps=req.num_inference_steps,
        seed=req.seed,
    )


async def _edit_image_core(
    prompt: str,
    image_url: str,
    guidance_scale: float = 2.5,
    num_inference_steps: int = 28,
    seed: int | None = None,
) -> ImageGenResponse:
    """Edit an image using FLUX Kontext Pro — instruction-based edits with a reference image.

    Uses fal.ai FLUX.1 Kontext [pro] ($0.04/image).
    """
    fal_key = _get_settings().fal_key.strip()
    if not fal_key:
        raise HTTPException(status_code=500, detail="FAL_KEY not configured for image editing")

    import os
    os.environ["FAL_KEY"] = fal_key
    import fal_client

    payload: dict[str, Any] = {
        "prompt": prompt,
        "image_url": image_url,
        "guidance_scale": guidance_scale,
        "num_inference_steps": num_inference_steps,
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        log.info("Using FLUX Kontext Pro for image editing")
        data = await fal_client.subscribe_async("fal-ai/flux-pro/kontext", payload)
        images = data.get("images", [])
        if images and images[0].get("url"):
            return ImageGenResponse(image_url=images[0]["url"], model="flux-kontext-pro")
        raise HTTPException(status_code=500, detail="FLUX Kontext returned no image")
    except HTTPException:
        raise
    except Exception as e:
        log.error("FLUX Kontext Pro failed: %s: %s", type(e).__name__, str(e)[:200])
        raise HTTPException(status_code=502, detail=f"Image edit failed: {str(e)[:200]}") from e


# ─── TTS endpoint (Gemini TTS via fal.ai) ───────────────────────────────────

@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    req: TTSRequest,
    user: CurrentUser,
) -> TTSResponse:
    """Convert text to speech using Gemini TTS via fal.ai.

    Supports 30 voice presets and natural-language control over style, pace,
    accent, and emotion. Supports multi-speaker synthesis.
    """
    fal_key = _get_settings().fal_key.strip()
    if not fal_key:
        raise HTTPException(status_code=500, detail="FAL_KEY not configured for TTS")

    import os
    os.environ["FAL_KEY"] = fal_key
    import fal_client

    payload: dict[str, Any] = {
        "prompt": req.prompt,
        "voice": req.voice,
        "model": req.model,
    }
    if req.speakers:
        payload["speakers"] = req.speakers

    try:
        log.info("Using Gemini TTS (voice=%s, model=%s)", req.voice, req.model)
        data = await fal_client.subscribe_async("fal-ai/gemini-tts", payload)
        # Response has audio.output with the audio data URI or URL
        audio = data.get("audio", {})
        if isinstance(audio, dict):
            audio_url = audio.get("url", "") or audio.get("output", "")
        elif isinstance(audio, str):
            audio_url = audio
        else:
            audio_url = ""
        if not audio_url:
            # Try alternate fields
            audio_url = data.get("output", {}).get("url", "") if isinstance(data.get("output"), dict) else data.get("output", "")
        if not audio_url:
            raise HTTPException(status_code=500, detail="Gemini TTS returned no audio")
        return TTSResponse(audio_url=audio_url, model=req.model)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Gemini TTS failed: %s: %s", type(e).__name__, str(e)[:200])
        raise HTTPException(status_code=502, detail=f"TTS failed: {str(e)[:200]}") from e


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
    import asyncio
    import base64

    from google import genai
    from google.genai import types as gtypes

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


def _read_repo_env() -> str:
    p = Path(__file__).resolve().parents[3] / ".env"
    return p.read_text() if p.exists() else ""


def _download_gemini_video(client, video) -> bytes:
    """Download video bytes from Gemini via the SDK.

    SDK v1.29+ returns bytes directly from files.download().
    """
    file_ref = getattr(video, "video", None) or video
    return client.files.download(file=file_ref)


async def _store_video_bytes(data: bytes, filename: str) -> str:
    """Store video bytes and return a URL.

    Uploads to fal.ai storage (which returns a public URL), falling back to
    a data URL (base64) only if upload fails.
    """
    import asyncio
    import base64
    import os

    # Read FAL_KEY from env
    env = {}
    env_text = await asyncio.to_thread(_read_repo_env)
    if env_text:
        for line in env_text.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    fal_key = os.environ.get("FAL_KEY") or env.get("FAL_KEY", "")
    if fal_key:
        try:
            os.environ["FAL_KEY"] = fal_key
            import fal_client
            # Upload to fal storage — returns a public URL
            url = await fal_client.upload_async(data, filename, "video/mp4")
            log.info("video stored at fal storage: %s", url[:80])
            return url
        except Exception as exc:
            log.warning("fal storage upload failed: %s — falling back to data URL", str(exc)[:200])

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
    import asyncio
    import base64
    import time

    from google import genai
    from google.genai import types as gtypes

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


# ─── fal.ai (fallback) ──────────────────────────────────────────────────────

async def _call_fal_video(fal_key: str, req: VideoGenRequest, prompt: str, aspect: str) -> VideoGenResponse:
    """Call fal.ai for video generation using the official fal_client library."""
    import os
    os.environ["FAL_KEY"] = fal_key
    import fal_client

    model_id = FAL_MODELS.get(req.model, FAL_MODELS[FAL_DEFAULT_MODEL])

    # Build payload for Wan 3.0
    payload: dict[str, Any] = {"prompt": prompt}

    # Wan 3.0: duration (up to 30s), resolution (1080p), aspect_ratio, audio
    duration_val = int(str(req.duration).replace("s", "").replace(".0", ""))
    payload["duration"] = min(max(duration_val, 1), 30)  # Wan 3.0 supports 1-30s
    payload["aspect_ratio"] = aspect
    payload["resolution"] = req.resolution or "1080p"
    payload["audio"] = True  # Native audio generation

    log.info("Using fal_client.subscribe_async for model %s", model_id)

    try:
        data = await fal_client.subscribe_async(model_id, payload)
    except Exception as exc:
        err_msg = str(exc)[:300]
        if "402" in err_msg or "403" in err_msg or "locked" in err_msg.lower():
            raise HTTPException(status_code=402, detail=f"fal.ai: {err_msg}") from exc
        raise HTTPException(status_code=502, detail=f"fal.ai error: {err_msg}") from exc

    video_url = _extract_video_url(data)
    if not video_url:
        raise HTTPException(status_code=500, detail=f"fal.ai completed but no video URL. Response: {str(data)[:200]}")

    dur_sec = int(str(req.duration).replace("s", ""))
    cost = dur_sec * FAL_DEFAULT_COST_PER_SEC
    return VideoGenResponse(
        video_url=video_url,
        model=model_id,
        duration=str(req.duration),
        resolution="720p",
        quality_tier="kling-turbo",
        gpu_cost_estimate=f"~${cost:.2f} (Kling 2.5 Turbo 720p + audio)",
    )


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
