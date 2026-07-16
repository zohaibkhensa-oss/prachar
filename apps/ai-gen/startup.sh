#!/bin/bash
# Startup script for RunPod auto-spin-up pods.
# The pod's dockerArgs clones the repo to /app/prachar, then runs this script.
# Models are cached in /workspace/hf_cache (persistent volume) so subsequent boots are fast.

set -e

echo "=== PRACHAR AI Gen Service — Starting ==="

# Repo was cloned to /app/prachar by dockerArgs
REPO_DIR="/app/prachar/apps/ai-gen"
SERVER_PY="$REPO_DIR/server.py"

if [ ! -f "$SERVER_PY" ]; then
    echo "ERROR: server.py not found at $SERVER_PY"
    echo "Contents of /app:"
    ls -la /app/ 2>/dev/null || true
    exit 1
fi

# Install dependencies (only needed on first boot, cached after)
if [ ! -f "/workspace/.ai-gen-installed" ]; then
    echo "First boot — installing dependencies..."
    pip install --upgrade pip 2>&1 | tail -1
    pip install \
        "diffusers>=0.32.0" \
        "transformers>=4.45.0" \
        accelerate safetensors sentencepiece \
        "imageio[ffmpeg]" \
        fastapi "uvicorn[standard]" pydantic huggingface-hub 2>&1 | tail -3
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
