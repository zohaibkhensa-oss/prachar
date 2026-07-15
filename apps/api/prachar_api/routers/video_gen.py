"""AI Video Generation router — auto spin-up GPU, generate, shut down."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import CurrentUser
from prachar_shared.config import get_settings

router = APIRouter(prefix="/api/video", tags=["video-gen"])
log = logging.getLogger(__name__)

# fal.ai models (fallback when no GPU available)
FAL_MODELS = {
    "ltx": "fal-ai/ltx-2.3/text-to-video",
    "seedance_fast": "bytedance/seedance-2.0/fast/text-to-video",
    "seedance": "bytedance/seedance-2.0/text-to-video",
    "wan_fast": "wan-video/wan-2.2-t2v-fast",
    "kling": "kwaivgi/kling-v3.0-pro/text-to-video",
}

ASPECT_RATIOS = {
    "reel": "9:16",
    "short": "9:16",
    "square": "1:1",
    "landscape": "16:9",
    "story": "9:16",
}


class VideoGenRequest(BaseModel):
    prompt: str
    model: str = "ltx"
    duration: str = "5"
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    video_type: str = "landscape"


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


class ImageGenResponse(BaseModel):
    image_url: str
    model: str
    generation_time: float = 0.0


def _get_settings():
    return get_settings()


def _get_ai_gen_url() -> str | None:
    """Get self-hosted AI gen service URL (static, always-on)."""
    s = _get_settings()
    url = getattr(s, "ai_gen_url", "") or os.environ.get("AI_GEN_URL", "")
    return url.strip() or None


def _get_runpod_config() -> tuple[str, str] | None:
    """Get RunPod API key and GPU type for auto spin-up."""
    s = _get_settings()
    key = getattr(s, "runpod_api_key", "") or os.environ.get("RUNPOD_API_KEY", "")
    gpu = getattr(s, "runpod_gpu_type", "rtx4090") or os.environ.get("RUNPOD_GPU_TYPE", "rtx4090")
    if key.strip():
        return key.strip(), gpu.strip()
    return None


@router.post("/generate", response_model=VideoGenResponse)
async def generate_video(
    req: VideoGenRequest,
    user: CurrentUser,
) -> VideoGenResponse:
    """Generate a real AI video from a text prompt.

    Priority:
    1. Self-hosted AI gen service (if AI_GEN_URL is set and running)
    2. RunPod auto spin-up (if RUNPOD_API_KEY is set) — spins up GPU, generates, shuts down
    3. fal.ai fallback (if FAL_KEY is set)
    """
    aspect = ASPECT_RATIOS.get(req.video_type, req.aspect_ratio)
    enhanced_prompt = req.prompt.strip()

    # --- Option 1: Static self-hosted service ---
    ai_gen_url = _get_ai_gen_url()
    if ai_gen_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                health = await client.get(f"{ai_gen_url}/health", timeout=5)
                if health.status_code == 200:
                    log.info("Using static AI gen service: %s", ai_gen_url)
                    result = await _call_self_hosted_video(ai_gen_url, enhanced_prompt, req, aspect)
                    return result
        except Exception as e:
            log.warning("Static AI gen service unavailable: %s", str(e)[:100])

    # --- Option 2: RunPod auto spin-up / shut-down ---
    runpod_config = _get_runpod_config()
    if runpod_config:
        api_key, gpu_type = runpod_config
        log.info("Using RunPod auto spin-up (GPU: %s)", gpu_type)
        try:
            from ..runpod_manager import RunPodManager
            mgr = RunPodManager(api_key, gpu_type)

            async def do_generate(service_url: str) -> VideoGenResponse:
                return await _call_self_hosted_video(service_url, enhanced_prompt, req, aspect)

            result = await mgr.generate_with_auto_shutdown(do_generate, shutdown_after=True)
            # Estimate cost
            result.gpu_cost_estimate = "~$0.04-0.06 (5 min GPU time)"
            return result
        except Exception as e:
            log.error("RunPod generation failed: %s: %s", type(e).__name__, str(e)[:300])
            # Fall through to fal.ai

    # --- Option 3: fal.ai fallback ---
    fal_key = _get_settings().fal_key.strip()
    if fal_key:
        log.info("Falling back to fal.ai")
        return await _call_fal_video(fal_key, req, enhanced_prompt, aspect)

    raise HTTPException(
        status_code=500,
        detail="No video generation service configured. Set AI_GEN_URL (static GPU), RUNPOD_API_KEY (auto GPU), or FAL_KEY (fal.ai) in .env",
    )


@router.post("/generate-image", response_model=ImageGenResponse)
async def generate_image(
    req: ImageGenRequest,
    user: CurrentUser,
) -> ImageGenResponse:
    """Generate an image from text. Same priority chain as video."""
    # Option 1: Static self-hosted
    ai_gen_url = _get_ai_gen_url()
    if ai_gen_url:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{ai_gen_url}/generate-image",
                    json={"prompt": req.prompt, "width": req.width, "height": req.height, "num_inference_steps": req.num_inference_steps},
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    url = data.get("url", "")
                    if url.startswith("/"):
                        url = f"{ai_gen_url}{url}"
                    return ImageGenResponse(image_url=url, model=data.get("model", "self-hosted"), generation_time=data.get("generation_time", 0))
        except Exception:
            pass

    # Option 2: RunPod auto spin-up
    runpod_config = _get_runpod_config()
    if runpod_config:
        api_key, gpu_type = runpod_config
        try:
            from ..runpod_manager import RunPodManager
            mgr = RunPodManager(api_key, gpu_type)

            async def do_generate(service_url: str) -> ImageGenResponse:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{service_url}/generate-image",
                        json={"prompt": req.prompt, "width": req.width, "height": req.height, "num_inference_steps": req.num_inference_steps},
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        url = data.get("url", "")
                        if url.startswith("/"):
                            url = f"{service_url}{url}"
                        return ImageGenResponse(image_url=url, model=data.get("model", "self-hosted"), generation_time=data.get("generation_time", 0))
                    raise RuntimeError(f"Image gen failed: {resp.text[:200]}")

            return await mgr.generate_with_auto_shutdown(do_generate, shutdown_after=True)
        except Exception as e:
            log.error("RunPod image gen failed: %s", str(e)[:200])

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


# --- Helper functions ---

async def _call_self_hosted_video(url: str, prompt: str, req: VideoGenRequest, aspect: str) -> VideoGenResponse:
    """Call the self-hosted AI gen service for video generation."""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{url}/generate-video",
            json={
                "prompt": prompt,
                "duration": int(req.duration.replace("s", "")),
                "resolution": "480p" if req.resolution in ("480p", "720p") else req.resolution,
                "aspect_ratio": aspect,
            },
            timeout=300,
        )
        if resp.status_code == 200:
            data = resp.json()
            video_url = data.get("url", "")
            if video_url.startswith("/"):
                video_url = f"{url}{video_url}"
            return VideoGenResponse(
                video_url=video_url,
                model=data.get("model", "self-hosted"),
                duration=req.duration,
                resolution=req.resolution,
                generation_time=data.get("generation_time", 0),
            )
        raise RuntimeError(f"Self-hosted video gen failed: {resp.text[:200]}")


async def _call_fal_video(fal_key: str, req: VideoGenRequest, prompt: str, aspect: str) -> VideoGenResponse:
    """Call fal.ai for video generation (fallback)."""
    model_id = FAL_MODELS.get(req.model, FAL_MODELS["ltx"])
    submit_url = f"https://queue.fal.run/{model_id}"
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {"prompt": prompt, "resolution": req.resolution}
    if req.model in ("ltx", "seedance_fast", "seedance"):
        payload["duration"] = req.duration
    if req.model in ("ltx", "seedance_fast", "seedance", "kling"):
        payload["aspect_ratio"] = aspect

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
                return VideoGenResponse(video_url=video_url, model=model_id, duration=req.duration, resolution=req.resolution)
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
                        return VideoGenResponse(video_url=video_url, model=model_id, duration=req.duration, resolution=req.resolution)
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
