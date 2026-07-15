# PRACHAR AI Generation Service — GPU Dockerfile
# Deploy on RunPod, Lambda Labs, or any NVIDIA GPU server
#
# Build:  docker build -t prachar-ai-gen .
# Run:    docker run --gpus all -p 8100:8100 -v ai-outputs:/app/outputs prachar-ai-gen

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf_cache

# System deps
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3.10-dev \
    ffmpeg libsm6 libxext6 libxrender-dev libgl1 \
    git curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip3 install --upgrade pip && pip3 install \
    torch torchvision --index-url https://download.pytorch.org/whl/cu121 \
    "diffusers>=0.32.0" \
    "transformers>=4.45.0" \
    accelerate \
    safetensors \
    sentencepiece \
    imageio[ffmpeg] \
    fastapi \
    uvicorn[standard] \
    pydantic \
    huggingface-hub

WORKDIR /app

COPY server.py .

# Pre-create output directory
RUN mkdir -p /app/outputs /app/hf_cache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

EXPOSE 8100

# Models download on first request (lazy loading)
# First video generation will take ~5 min extra for model download
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"]
