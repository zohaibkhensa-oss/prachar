#!/bin/bash
# Startup script for RunPod auto-spin-up pods.
# The pod's dockerArgs clones the repo to /root/prachar, then runs this script.
# Models are cached in /workspace/hf_cache (persistent volume) so subsequent boots are fast.

set -e

echo "=== PRACHAR AI Gen Service — Starting ==="

# Clone repo if not already present
REPO_DIR="/root/prachar/apps/ai-gen"
SERVER_PY="$REPO_DIR/server.py"

if [ ! -f "$SERVER_PY" ]; then
    echo "Cloning repo..."
    cd /root
    git clone --depth 1 https://github.com/zohaibkhensa-oss/prachar.git
fi

# Install dependencies (only needed on first boot, cached after)
if [ ! -f "/workspace/.ai-gen-installed" ]; then
    echo "First boot — installing dependencies..."
    pip install --upgrade pip 2>&1 | tail -1
    # Install torch 2.6.0 with CUDA 12.4 support first
    pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -3
    # Then install the rest (pinned versions for compatibility)
    pip install \
        "diffusers==0.32.2" \
        "transformers==4.44.2" \
        accelerate safetensors sentencepiece \
        imageio imageio-ffmpeg \
        fastapi "uvicorn[standard]" pydantic huggingface-hub 2>&1 | tail -3
    # Remove torchaudio (incompatible, not needed)
    pip uninstall -y torchaudio 2>/dev/null || true
    touch /workspace/.ai-gen-installed
    echo "Dependencies installed."
else
    echo "Dependencies already installed (cached)."
fi

# Set HF cache to persistent volume
export HF_HOME=/workspace/hf_cache
mkdir -p /workspace/hf_cache /app/outputs

echo "Starting AI gen service on port 8100..."
cd "$REPO_DIR"
exec python3 server.py
