#!/bin/bash
# Startup script for RunPod auto-spin-up pods.
# Installs the AI gen service on first boot, then starts it.
# Models are cached in /workspace/hf_cache (persistent volume) so subsequent boots are fast.

set -e

echo "=== PRACHAR AI Gen Service — Starting ==="

# Install dependencies (only needed on first boot, cached after)
if [ ! -f "/workspace/.ai-gen-installed" ]; then
    echo "First boot — installing dependencies..."
    pip install --upgrade pip
    pip install \
        torch torchvision --index-url https://download.pytorch.org/whl/cu121 \
        "diffusers>=0.32.0" \
        "transformers>=4.45.0" \
        accelerate safetensors sentencepiece \
        "imageio[ffmpeg]" \
        fastapi "uvicorn[standard]" pydantic huggingface-hub

    # Copy server.py to /workspace for persistence
    cp /app/server.py /workspace/server.py
    touch /workspace/.ai-gen-installed
    echo "Dependencies installed."
else
    echo "Dependencies already installed (cached)."
fi

# Use cached server.py
cp /workspace/server.py /app/server.py 2>/dev/null || true

# Set HF cache to persistent volume
export HF_HOME=/workspace/hf_cache

echo "Starting AI gen service on port 8100..."
exec python3 /app/server.py
