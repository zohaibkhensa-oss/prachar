"""
PRACHAR AI Generation Service — Modal.com serverless deployment.

Auto-scales to zero when idle. Pay only when generating.
~$0.01 per video on T4 GPU.

Deploy:
    modal deploy apps/ai-gen/modal_app.py

This creates stable HTTPS endpoints:
    https://zohaib-khensa--prachar-ai-gen-generate-video.modal.run
    https://zohaib-khensa--prachar-ai-gen-generate-image.modal.run
    https://zohaib-khensa--prachar-ai-gen-health.modal.run
"""
import modal
import os
import time
import uuid
import numpy as np
from pydantic import BaseModel

# --- Modal app + image ---
app = modal.App("prachar-ai-gen-v2")

image = (
    modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel", add_python="3.11")
    .pip_install(
        "diffusers==0.32.2",
        "transformers==4.44.2",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "imageio",
        "imageio-ffmpeg",
        "fastapi",
        "uvicorn[standard]",
        "pydantic",
        "huggingface-hub",
    )
)

# --- Volume for model caching ---
vol = modal.Volume.from_name("prachar-hf-cache", create_if_missing=True)
OUTPUT_VOL = modal.Volume.from_name("prachar-outputs", create_if_missing=True)

GPU_TYPE = "T4"  # ~$0.000164/sec. Use "A100-40GB" for faster generation.

WORKSPACE = "zohaib-khensa"


# --- Request models ---
class VideoRequest(BaseModel):
    prompt: str
    duration: int = 5
    num_frames: int = 16
    seed: int | None = None


class ImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 30
    seed: int | None = None


@app.function(
    image=image,
    gpu=GPU_TYPE,
    volumes={"/data/hf_cache": vol, "/data/outputs": OUTPUT_VOL},
    min_containers=0,  # Scale to zero when idle
    timeout=600,
)
@modal.fastapi_endpoint(method="POST")
def generate_video(data: dict):
    """Generate video using AnimateDiff + SD 1.5."""
    import torch
    from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler
    import imageio
    from pathlib import Path

    os.environ["HF_HOME"] = "/data/hf_cache"

    prompt = data.get("prompt", "")
    num_frames = int(data.get("num_frames", 16))
    seed = data.get("seed")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    start = time.time()

    # Load model
    adapter = MotionAdapter.from_pretrained(
        "guoyww/animatediff-motion-adapter-v1-5-2",
        torch_dtype=dtype,
        cache_dir="/data/hf_cache",
    )
    pipe = AnimateDiffPipeline.from_pretrained(
        "emilianJR/epiCRealism",
        motion_adapter=adapter,
        torch_dtype=dtype,
        cache_dir="/data/hf_cache",
    )
    pipe.scheduler = DDIMScheduler.from_config(
        pipe.scheduler.config,
        beta_schedule="linear",
        clip_sample=False,
        timestep_spacing="linspace",
        steps_offset=1,
    )
    pipe.to(device)

    # Generate
    gen_seed = int(seed) if seed is not None else int(time.time())
    generator = torch.Generator(device=device).manual_seed(gen_seed)

    output = pipe(
        prompt=prompt,
        num_frames=num_frames,
        guidance_scale=7.5,
        num_inference_steps=25,
        generator=generator,
        width=512,
        height=512,
    )

    video_frames = output.frames[0]
    gen_time = time.time() - start

    # Save to volume
    video_id = str(uuid.uuid4())
    output_path = Path(f"/data/outputs/{video_id}.mp4")
    writer = imageio.get_writer(str(output_path), fps=8, codec="libx264")
    for frame in video_frames:
        writer.append_data(np.array(frame))
    writer.close()

    OUTPUT_VOL.commit()

    return {
        "url": f"https://{WORKSPACE}--prachar-ai-gen-v2-get-video.modal.run?video_id={video_id}",
        "video_id": video_id,
        "model": "animatediff-sd15",
        "generation_time": round(gen_time, 1),
    }


@app.function(
    image=image,
    gpu=GPU_TYPE,
    volumes={"/data/hf_cache": vol, "/data/outputs": OUTPUT_VOL},
    min_containers=0,
    timeout=300,
)
@modal.fastapi_endpoint(method="POST")
def generate_image(data: dict):
    """Generate image using SDXL."""
    import torch
    from diffusers import DiffusionPipeline
    from pathlib import Path

    os.environ["HF_HOME"] = "/data/hf_cache"

    prompt = data.get("prompt", "")
    width = int(data.get("width", 1024))
    height = int(data.get("height", 1024))
    num_inference_steps = int(data.get("num_inference_steps", 30))
    seed = data.get("seed")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    start = time.time()

    pipe = DiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype,
        variant="fp16",
        cache_dir="/data/hf_cache",
    )
    pipe.to(device)

    gen_seed = int(seed) if seed is not None else int(time.time())
    generator = torch.Generator(device=device).manual_seed(gen_seed)

    output = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        generator=generator,
    )

    image = output.images[0]
    gen_time = time.time() - start

    image_id = str(uuid.uuid4())
    output_path = Path(f"/data/outputs/{image_id}.png")
    image.save(str(output_path))

    OUTPUT_VOL.commit()

    return {
        "url": f"https://{WORKSPACE}--prachar-ai-gen-v2-get-image.modal.run?image_id={image_id}",
        "image_id": image_id,
        "model": "sdxl-base-1.0",
        "generation_time": round(gen_time, 1),
    }


@app.function(
    image=image,
    gpu=GPU_TYPE,
    volumes={"/data/outputs": OUTPUT_VOL},
    min_containers=0,
)
@modal.fastapi_endpoint(method="GET")
def get_video(video_id: str):
    """Retrieve a generated video by ID."""
    from fastapi import Response
    from pathlib import Path

    path = Path(f"/data/outputs/{video_id}.mp4")
    if not path.exists():
        return {"error": "Video not found", "video_id": video_id}

    return Response(content=path.read_bytes(), media_type="video/mp4")


@app.function(
    image=image,
    volumes={"/data/outputs": OUTPUT_VOL},
    min_containers=0,
)
@modal.fastapi_endpoint(method="GET")
def get_image(image_id: str):
    """Retrieve a generated image by ID."""
    from fastapi import Response
    from pathlib import Path

    path = Path(f"/data/outputs/{image_id}.png")
    if not path.exists():
        return {"error": "Image not found", "image_id": image_id}

    return Response(content=path.read_bytes(), media_type="image/png")


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def health():
    """Health check endpoint."""
    return {"status": "ok", "platform": "modal.com", "gpu": GPU_TYPE}
