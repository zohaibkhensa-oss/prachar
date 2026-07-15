"""
RunPod GPU Manager — auto spin-up / shut-down for per-video billing.

Flow:
  1. User requests video generation
  2. Backend calls RunPodManager → spins up RTX 4090 with PyTorch image
  3. Installs AI gen service + downloads models on first boot (cached on volume)
  4. Sends generation request to the pod
  5. Returns result to user
  6. Auto-shuts down the pod — billing stops

Cost: ~$0.05 per video (5 min GPU time × $0.50/hr)
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"

GPU_TYPES = {
    "rtx4090": "NVIDIA GeForce RTX 4090",
    "rtx4000": "NVIDIA RTX 4000 Ada",
    "a6000": "NVIDIA RTX A6000",
    "a100": "NVIDIA A100 80GB PCIe",
}

# Use RunPod's PyTorch image — has CUDA + Python pre-installed
PYTORCH_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"

# The server.py content is embedded so it runs on the pod without needing a registry
# This is a simplified version that installs deps and starts the server
BOOTSTRAP_SCRIPT = """#!/bin/bash
set -e
export HF_HOME=/workspace/hf_cache
mkdir -p /workspace/hf_cache /app/outputs

# Install deps (cached on volume after first boot)
if [ ! -f "/workspace/.deps-installed" ]; then
    echo "Installing AI gen dependencies..."
    pip install --upgrade pip 2>&1 | tail -1
    pip install "diffusers>=0.32.0" "transformers>=4.45.0" accelerate safetensors sentencepiece "imageio[ffmpeg]" fastapi "uvicorn[standard]" pydantic huggingface-hub 2>&1 | tail -3
    touch /workspace/.deps-installed
    echo "Dependencies installed."
else
    echo "Dependencies already installed."
fi

# Write server.py
cat > /app/server.py << 'SERVEREOF'
import io, logging, os, time, uuid
from pathlib import Path
import torch
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prachar.ai-gen")
app = FastAPI(title="PRACHAR AI Gen")
OUTPUT_DIR = Path("/app/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_video_pipeline = None
_image_pipeline = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
log.info("Device: %s, Dtype: %s", DEVICE, DTYPE)

def get_video_pipeline():
    global _video_pipeline
    if _video_pipeline is not None:
        return _video_pipeline
    log.info("Loading Wan 2.1 T2V 1.3B model...")
    from diffusers import AutoencoderKLWan, WanPipeline
    from transformers import UMT5EncoderModel
    model_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=DTYPE)
    text_encoder = UMT5EncoderModel.from_pretrained(model_id, subfolder="text_encoder", torch_dtype=DTYPE)
    _video_pipeline = WanPipeline.from_pretrained(model_id, vae=vae, text_encoder=text_encoder, torch_dtype=DTYPE)
    _video_pipeline.to(DEVICE)
    _video_pipeline.enable_model_cpu_offload()
    log.info("Wan 2.1 loaded.")
    return _video_pipeline

def get_image_pipeline():
    global _image_pipeline
    if _image_pipeline is not None:
        return _image_pipeline
    log.info("Loading FLUX.1 Schnell...")
    from diffusers import FluxPipeline
    _image_pipeline = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=DTYPE)
    _image_pipeline.to(DEVICE)
    log.info("FLUX.1 loaded.")
    return _image_pipeline

class VideoReq(BaseModel):
    prompt: str
    duration: int = 5
    resolution: str = "480p"
    aspect_ratio: str = "16:9"
    num_frames: int = 81
    seed: int | None = None

class ImageReq(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 4
    seed: int | None = None

class GenResp(BaseModel):
    url: str
    model: str
    generation_time: float

@app.get("/health")
async def health():
    return {"status": "ok", "device": DEVICE, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "vram": f"{torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB" if torch.cuda.is_available() else None, "models": {"video": _video_pipeline is not None, "image": _image_pipeline is not None}}

@app.post("/generate-video", response_model=GenResp)
async def gen_video(req: VideoReq):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")
    start = time.time()
    log.info("Video gen: %s", req.prompt[:60])
    try:
        pipe = get_video_pipeline()
        h, w = (720, 1280) if req.resolution == "720p" else (480, 832)
        if req.aspect_ratio == "9:16":
            w, h = h, w
        elif req.aspect_ratio == "1:1":
            w, h = 480, 480
        gen = torch.Generator(device=DEVICE).manual_seed(req.seed or int(time.time()))
        output = pipe(prompt=req.prompt, num_frames=req.num_frames, height=h, width=w, generator=gen, num_inference_steps=20)
        frames = output.frames[0]
        gt = time.time() - start
        vid = str(uuid.uuid4())
        path = OUTPUT_DIR / f"{vid}.mp4"
        import imageio
        writer = imageio.get_writer(str(path), fps=16, codec="libx264")
        for f in frames:
            writer.append_data(f)
        writer.close()
        return GenResp(url=f"/outputs/{vid}.mp4", model="wan-2.1-t2v-1.3b", generation_time=round(gt, 1))
    except Exception as e:
        log.error("Video gen failed: %s", str(e)[:300])
        raise HTTPException(500, str(e)[:200])

@app.post("/generate-image", response_model=GenResp)
async def gen_image(req: ImageReq):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")
    start = time.time()
    log.info("Image gen: %s", req.prompt[:60])
    try:
        pipe = get_image_pipeline()
        gen = torch.Generator(device=DEVICE).manual_seed(req.seed or int(time.time()))
        output = pipe(prompt=req.prompt, width=req.width, height=req.height, num_inference_steps=req.num_inference_steps, generator=gen)
        img = output.images[0]
        gt = time.time() - start
        iid = str(uuid.uuid4())
        path = OUTPUT_DIR / f"{iid}.png"
        img.save(str(path))
        return GenResp(url=f"/outputs/{iid}.png", model="flux-1-schnell", generation_time=round(gt, 1))
    except Exception as e:
        log.error("Image gen failed: %s", str(e)[:300])
        raise HTTPException(500, str(e)[:200])

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
SERVEREOF

echo "Starting AI gen service on port 8100..."
cd /app
exec python3 server.py
"""


class RunPodManager:
    """Manages RunPod GPU pods — spin up, check status, shut down."""

    def __init__(self, api_key: str, gpu_type: str = "rtx4090"):
        self.api_key = api_key
        self.gpu_type_id = GPU_TYPES.get(gpu_type, GPU_TYPES["rtx4090"])
        self._graphql_url = f"{RUNPOD_GRAPHQL}?api_key={api_key}"

    async def _graphql(self, query: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self._graphql_url,
                json={"query": query},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"RunPod GraphQL error: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(f"RunPod GraphQL errors: {data['errors']}")
            return data.get("data", {})

    async def list_pods(self) -> list[dict[str, Any]]:
        """List all pods."""
        data = await self._graphql("{ myself { pods { id name desiredStatus runtime { ports { ip isIpPublic privatePort publicPort } } } } }")
        return data.get("myself", {}).get("pods", [])

    async def find_ai_gen_pod(self) -> dict[str, Any] | None:
        """Find an existing PRACHAR AI gen pod."""
        pods = await self.list_pods()
        for pod in pods:
            if "prachar-ai-gen" in (pod.get("name") or "").lower():
                return pod
        return None

    async def create_pod(self) -> str:
        """Create and deploy a new GPU pod. Returns pod ID."""
        # Encode the bootstrap script as base64 so it survives JSON transport
        script_b64 = base64.b64encode(BOOTSTRAP_SCRIPT.encode()).decode()

        # Use GraphQL mutation to create pod
        # The dockerArgs will run our bootstrap script
        import json
        env_json = json.dumps([{"key": "HF_HOME", "value": "/workspace/hf_cache"}])

        mutation = '''
        mutation {
            podFindAndDeployOnDemand(input: {
                cloudType: ALL
                gpuCount: 1
                volumeInGb: 50
                containerDiskInGb: 80
                minVcpuCount: 4
                minMemoryInGb: 20
                gpuTypeId: "%s"
                name: "prachar-ai-gen"
                imageName: "%s"
                dockerArgs: ""
                ports: "8100/http"
                volumeMountPath: "/workspace"
                env: %s
                templateId: null
                startScript: "%s"
            }) {
                id
                imageName
                desiredStatus
                machineId
                machine { podHostId }
            }
        }
        ''' % (self.gpu_type_id, PYTORCH_IMAGE, env_json, script_b64)

        log.info("Creating RunPod pod with GPU: %s", self.gpu_type_id)
        data = await self._graphql(mutation)
        pod = data.get("podFindAndDeployOnDemand", {})
        pod_id = pod.get("id")
        if not pod_id:
            raise RuntimeError(f"RunPod did not return pod ID: {data}")
        log.info("Created pod: %s", pod_id)
        return pod_id

    async def stop_pod(self, pod_id: str) -> bool:
        """Stop a pod (releases GPU, stops billing). Volume data preserved."""
        mutation = 'mutation { podStop(input: {podId: "%s"}) { id desiredStatus } }' % pod_id
        try:
            await self._graphql(mutation)
            log.info("Stopped pod %s — GPU released, billing stopped", pod_id)
            return True
        except Exception as e:
            log.error("Failed to stop pod %s: %s", pod_id, str(e)[:200])
            return False

    async def terminate_pod(self, pod_id: str) -> bool:
        """Permanently delete a pod."""
        mutation = 'mutation { podTerminate(input: {podId: "%s"}) { id } }' % pod_id
        try:
            await self._graphql(mutation)
            log.info("Terminated pod %s", pod_id)
            return True
        except Exception:
            return False

    async def get_pod(self, pod_id: str) -> dict[str, Any] | None:
        """Get pod details including runtime/ports."""
        query = '{ pod(input: {podId: "%s"}) { id name desiredStatus runtime { ports { ip isIpPublic privatePort publicPort } } machine { podHostId } } }' % pod_id
        data = await self._graphql(query)
        return data.get("pod")

    async def wait_for_pod_ready(self, pod_id: str, timeout: int = 180) -> str | None:
        """Wait for pod to boot and return the service URL.
        RunPod uses proxy URLs: https://{pod_id}-{publicPort}.proxy.runpod.net
        """
        start = time.time()
        log.info("Waiting for pod %s to boot...", pod_id)

        while time.time() - start < timeout:
            try:
                pod = await self.get_pod(pod_id)
                if pod:
                    desired = pod.get("desiredStatus", "")
                    runtime = pod.get("runtime")
                    log.info("Pod status: desired=%s, runtime=%s", desired, "yes" if runtime else "no")

                    if runtime and runtime.get("ports"):
                        for port_info in runtime["ports"]:
                            if port_info.get("privatePort") == 8100:
                                public_port = port_info.get("publicPort", 8100)
                                # RunPod proxy URL format
                                url = f"https://{pod_id}-{public_port}.proxy.runpod.net"
                                log.info("Pod ready at %s (%.0fs)", url, time.time() - start)
                                return url
            except Exception as e:
                log.debug("Waiting for pod... %s", str(e)[:100])

            await asyncio.sleep(5)

        log.error("Pod %s not ready within %ds", pod_id, timeout)
        return None

    async def ensure_pod_running(self) -> tuple[str, str]:
        """Ensure a pod is running. Returns (pod_id, service_url)."""
        # Check for existing pod
        existing = await self.find_ai_gen_pod()
        if existing:
            pod_id = existing["id"]
            runtime = existing.get("runtime")
            if runtime and runtime.get("ports"):
                for p in runtime["ports"]:
                    if p.get("privatePort") == 8100:
                        public_port = p.get("publicPort", 8100)
                        url = f"https://{pod_id}-{public_port}.proxy.runpod.net"
                        log.info("Reusing running pod %s at %s", pod_id, url)
                        return pod_id, url
            # Pod exists but not running — resume it
            log.info("Resuming stopped pod %s...", pod_id)
            mutation = 'mutation { podResume(input: {podId: "%s"}) { id desiredStatus } }' % pod_id
            try:
                await self._graphql(mutation)
            except Exception as e:
                log.warning("Resume failed, creating new pod: %s", str(e)[:100])
                pod_id = await self.create_pod()

            url = await self.wait_for_pod_ready(pod_id)
            if url:
                return pod_id, url
            raise RuntimeError("Failed to resume pod")

        # Create new pod
        pod_id = await self.create_pod()
        url = await self.wait_for_pod_ready(pod_id)
        if not url:
            raise RuntimeError("Pod failed to boot")
        return pod_id, url

    async def generate_with_auto_shutdown(
        self,
        generate_fn,
        shutdown_after: bool = True,
    ) -> Any:
        """Full lifecycle: spin up → wait healthy → generate → shut down."""
        pod_id, url = await self.ensure_pod_running()

        try:
            # Wait for the AI gen service to be healthy
            # (first boot: installs deps + downloads models, can take 5-10 min)
            healthy = await self._wait_for_service_health(url, timeout=600)
            if not healthy:
                raise RuntimeError("AI gen service failed to start within 10 minutes")

            result = await generate_fn(url)
            return result
        finally:
            if shutdown_after:
                await asyncio.sleep(2)
                await self.stop_pod(pod_id)

    async def _wait_for_service_health(self, url: str, timeout: int = 600) -> bool:
        """Wait for the AI gen service to respond to /health."""
        start = time.time()
        log.info("Waiting for AI gen service at %s (timeout: %ds)...", url, timeout)
        async with httpx.AsyncClient(timeout=10) as client:
            while time.time() - start < timeout:
                try:
                    resp = await client.get(f"{url}/health", timeout=5)
                    if resp.status_code == 200:
                        elapsed = time.time() - start
                        log.info("AI gen service healthy (%.0fs)", elapsed)
                        return True
                except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
                    pass
                except Exception as e:
                    log.debug("Health check: %s", str(e)[:100])
                await asyncio.sleep(10)

        log.error("AI gen service not ready within %ds", timeout)
        return False
