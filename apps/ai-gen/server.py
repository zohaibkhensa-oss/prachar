"""
PRACHAR AI Generation Service — Self-hosted text-to-video and text-to-image.

Runs on a cloud GPU (RTX 4090 / A100) with:
  - Wan 2.1 T2V 1.3B for text-to-video (8GB VRAM, ~4 min/clip on 4090)
  - FLUX.1 Schnell for text-to-image (10GB VRAM, ~3s/image)

Deploy:
  docker build -t prachar-ai-gen .
  docker run --gpus all -p 8100:8100 prachar-ai-gen

Usage:
  POST /generate-video  {"prompt": "...", "duration": 5, "resolution": "480p"}
  POST /generate-image  {"prompt": "...", "width": 1024, "height": 1024}
  GET  /health
"""
from __future__ import annotations

import io
import logging
import os
import time
import uuid
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prachar.ai-gen")

app = FastAPI(title="PRACHAR AI Gen", version="1.0.0")

# --- Storage for generated files ---
OUTPUT_DIR = Path("/app/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Model singletons (lazy load) ---
_video_pipeline = None
_image_pipeline = None

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
log.info("Device: %s, Dtype: %s", DEVICE, DTYPE)


def get_video_pipeline():
    """Load Wan 2.1 T2V 1.3B text-to-video pipeline (lazy)."""
    global _video_pipeline
    if _video_pipeline is not None:
        return _video_pipeline

    log.info("Loading Wan 2.1 T2V 1.3B model...")
    from diffusers import AutoencoderKLWan, WanPipeline
    from transformers import UMT5EncoderModel

    model_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=DTYPE)
    text_encoder = UMT5EncoderModel.from_pretrained(model_id, subfolder="text_encoder", torch_dtype=DTYPE)
    _video_pipeline = WanPipeline.from_pretrained(
        model_id, vae=vae, text_encoder=text_encoder, torch_dtype=DTYPE
    )
    _video_pipeline.to(DEVICE)
    _video_pipeline.enable_model_cpu_offload()  # Save VRAM by offloading
    log.info("Wan 2.1 model loaded successfully")
    return _video_pipeline


def get_image_pipeline():
    """Load FLUX.1 Schnell text-to-image pipeline (lazy)."""
    global _image_pipeline
    if _image_pipeline is not None:
        return _image_pipeline

    log.info("Loading FLUX.1 Schnell model...")
    from diffusers import FluxPipeline

    _image_pipeline = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell", torch_dtype=DTYPE
    )
    _image_pipeline.to(DEVICE)
    log.info("FLUX.1 Schnell model loaded successfully")
    return _image_pipeline


# --- Request/Response models ---

class VideoGenRequest(BaseModel):
    prompt: str
    duration: int = 5  # seconds
    resolution: str = "480p"  # "480p" or "720p"
    aspect_ratio: str = "16:9"  # "16:9", "9:16", "1:1"
    num_frames: int = 81  # Wan default
    seed: int | None = None


class ImageGenRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 4  # FLUX schnell is fast
    seed: int | None = None


class GenResponse(BaseModel):
    url: str
    model: str
    generation_time: float


# --- Endpoints ---

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
    """Generate a video from text using Wan 2.1 T2V 1.3B."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    start = time.time()
    log.info("Video generation request: %s", req.prompt[:80])

    try:
        pipe = get_video_pipeline()

        # Set resolution
        if req.resolution == "720p":
            height, width = 720, 1280
        else:
            height, width = 480, 832

        # Adjust for aspect ratio
        if req.aspect_ratio == "9:16":
            width, height = height, width
        elif req.aspect_ratio == "1:1":
            width, height = 480, 480

        # Set seed
        generator = torch.Generator(device=DEVICE).manual_seed(
            req.seed if req.seed is not None else int(time.time())
        )

        log.info("Generating video: %dx%d, %d frames...", width, height, req.num_frames)

        output = pipe(
            prompt=req.prompt,
            num_frames=req.num_frames,
            height=height,
            width=width,
            generator=generator,
            num_inference_steps=20,  # Balance quality vs speed
        )

        video_frames = output.frames[0]  # List of PIL images
        gen_time = time.time() - start
        log.info("Video generated in %.1fs, %d frames", gen_time, len(video_frames))

        # Save as MP4
        video_id = str(uuid.uuid4())
        output_path = OUTPUT_DIR / f"{video_id}.mp4"

        import imageio
        writer = imageio.get_writer(str(output_path), fps=16, codec="libx264")
        for frame in video_frames:
            writer.append_data(frame)
        writer.close()

        return GenResponse(
            url=f"/outputs/{video_id}.mp4",
            model="wan-2.1-t2v-1.3b",
            generation_time=round(gen_time, 1),
        )

    except Exception as e:
        log.error("Video generation failed: %s: %s", type(e).__name__, str(e)[:300])
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/generate-image", response_model=GenResponse)
async def generate_image(req: ImageGenRequest):
    """Generate an image from text using FLUX.1 Schnell."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    start = time.time()
    log.info("Image generation request: %s", req.prompt[:80])

    try:
        pipe = get_image_pipeline()

        generator = torch.Generator(device=DEVICE).manual_seed(
            req.seed if req.seed is not None else int(time.time())
        )

        output = pipe(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=req.num_inference_steps,
            generator=generator,
        )

        image = output.images[0]
        gen_time = time.time() - start
        log.info("Image generated in %.1fs", gen_time)

        # Save as PNG
        image_id = str(uuid.uuid4())
        output_path = OUTPUT_DIR / f"{image_id}.png"
        image.save(str(output_path))

        return GenResponse(
            url=f"/outputs/{image_id}.png",
            model="flux-1-schnell",
            generation_time=round(gen_time, 1),
        )

    except Exception as e:
        log.error("Image generation failed: %s: %s", type(e).__name__, str(e)[:300])
        raise HTTPException(status_code=500, detail=str(e)[:200])


# --- Static file serving for outputs ---
from fastapi.staticfiles import StaticFiles
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
