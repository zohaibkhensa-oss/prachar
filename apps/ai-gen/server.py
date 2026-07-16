"""
PRACHAR AI Generation Service — Self-hosted text-to-video and text-to-image.

Uses models that are compatible with torch 2.4 + diffusers 0.32.2:
  - AnimateDiff for text-to-video (via Stable Diffusion 1.5)
  - Stable Diffusion XL for text-to-image
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prachar.ai-gen")

app = FastAPI(title="PRACHAR AI Gen", version="1.0.0")

OUTPUT_DIR = Path("/app/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_video_pipeline = None
_image_pipeline = None

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
log.info("Device: %s, Dtype: %s", DEVICE, DTYPE)


def get_video_pipeline():
    """Load AnimateDiff text-to-video pipeline (via SD 1.5)."""
    global _video_pipeline
    if _video_pipeline is not None:
        return _video_pipeline

    log.info("Loading AnimateDiff + SD 1.5 for text-to-video...")
    from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler

    # Motion adapter provides the temporal layers
    adapter = MotionAdapter.from_pretrained("guoyww/animatediff-motion-adapter-v1-5-2", torch_dtype=DTYPE)

    # SD 1.5 base model with AnimateDiff
    _video_pipeline = AnimateDiffPipeline.from_pretrained(
        "emilianJR/epiCRealism",  # Photorealistic SD 1.5 checkpoint
        motion_adapter=adapter,
        torch_dtype=DTYPE,
    )
    _video_pipeline.scheduler = DDIMScheduler.from_config(
        _video_pipeline.scheduler.config,
        beta_schedule="linear",
        clip_sample=False,
        timestep_spacing="linspace",
        steps_offset=1,
    )
    _video_pipeline.to(DEVICE)
    log.info("AnimateDiff loaded successfully")
    return _video_pipeline


def get_image_pipeline():
    """Load Stable Diffusion XL for text-to-image."""
    global _image_pipeline
    if _image_pipeline is not None:
        return _image_pipeline

    log.info("Loading Stable Diffusion XL...")
    from diffusers import DiffusionPipeline

    _image_pipeline = DiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=DTYPE,
        variant="fp16",
    )
    _image_pipeline.to(DEVICE)
    log.info("SDXL loaded successfully")
    return _image_pipeline


class VideoGenRequest(BaseModel):
    prompt: str
    duration: int = 5
    resolution: str = "480p"
    aspect_ratio: str = "16:9"
    num_frames: int = 16
    seed: int | None = None


class ImageGenRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 30
    seed: int | None = None


class GenResponse(BaseModel):
    url: str
    model: str
    generation_time: float


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "vram_total": f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB" if torch.cuda.is_available() else None,
        "models_loaded": {
            "video": _video_pipeline is not None,
            "image": _image_pipeline is not None,
        },
    }


@app.post("/generate-video", response_model=GenResponse)
async def generate_video(req: VideoGenRequest):
    """Generate video using AnimateDiff."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    start = time.time()
    log.info("Video gen: %s", req.prompt[:60])

    try:
        pipe = get_video_pipeline()

        # AnimateDiff works with 512x512, 16 frames
        frames = req.num_frames or 16

        gen = torch.Generator(device=DEVICE).manual_seed(
            req.seed if req.seed is not None else int(time.time())
        )

        log.info("Generating %d frames at 512x512...", frames)
        output = pipe(
            prompt=req.prompt,
            num_frames=frames,
            guidance_scale=7.5,
            num_inference_steps=25,
            generator=gen,
            width=512,
            height=512,
        )

        video_frames = output.frames[0]  # List of PIL images
        gen_time = time.time() - start
        log.info("Video generated in %.1fs, %d frames", gen_time, len(video_frames))

        # Save as MP4
        video_id = str(uuid.uuid4())
        output_path = OUTPUT_DIR / f"{video_id}.mp4"

        import imageio
        import numpy as np
        writer = imageio.get_writer(str(output_path), fps=8, codec="libx264")
        for frame in video_frames:
            writer.append_data(np.array(frame))
        writer.close()

        return GenResponse(
            url=f"/outputs/{video_id}.mp4",
            model="animatediff-sd15",
            generation_time=round(gen_time, 1),
        )

    except Exception as e:
        log.error("Video gen failed: %s: %s", type(e).__name__, str(e)[:300])
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/generate-image", response_model=GenResponse)
async def generate_image(req: ImageGenRequest):
    """Generate image using SDXL."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    start = time.time()
    log.info("Image gen: %s", req.prompt[:60])

    try:
        pipe = get_image_pipeline()

        gen = torch.Generator(device=DEVICE).manual_seed(
            req.seed if req.seed is not None else int(time.time())
        )

        output = pipe(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=req.num_inference_steps,
            generator=gen,
        )

        image = output.images[0]
        gen_time = time.time() - start
        log.info("Image generated in %.1fs", gen_time)

        image_id = str(uuid.uuid4())
        output_path = OUTPUT_DIR / f"{image_id}.png"
        image.save(str(output_path))

        return GenResponse(
            url=f"/outputs/{image_id}.png",
            model="sdxl-base-1.0",
            generation_time=round(gen_time, 1),
        )

    except Exception as e:
        log.error("Image gen failed: %s: %s", type(e).__name__, str(e)[:300])
        raise HTTPException(status_code=500, detail=str(e)[:200])


app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
