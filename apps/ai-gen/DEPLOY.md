# PRACHAR AI Gen Service — Deployment Guide

## Option 1: Auto Spin-Up / Shut-Down (recommended — pay per video, ~$0.05/video)

The backend automatically spins up a GPU pod when you generate a video, then shuts it down when done. You only pay for the minutes the GPU is active.

### Step 1: Get RunPod API key
1. Go to https://www.runpod.io
2. Create account, add $5-10 billing credit
3. Go to Console → Settings → API Keys
4. Create an API key

### Step 2: Configure PRACHAR
Add to your `.env`:
```bash
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_GPU_TYPE=rtx4090  # or rtx4000 (cheaper), a6000, a100
```

### Step 3: That's it!
When a user clicks "Generate Video":
1. Backend calls RunPod API to spin up an RTX 4090 pod (~60s boot)
2. Installs AI models on first boot (~5 min, cached on volume for next time)
3. Generates the video using Wan 2.1 (~4 min)
4. Returns the video to the user
5. Auto-shuts down the pod — billing stops

**Cost per video:** ~$0.04-0.06 (5 min GPU time × $0.50/hr)
**First video:** ~$0.10 (extra time for model download, one-time only)

### GPU type options

| GPU | VRAM | Cost/hr | Boot time | Good for |
|---|---|---|---|---|
| `rtx4090` | 24 GB | ~$0.50 | ~60s | Fastest generation |
| `rtx4000` | 20 GB | ~$0.25 | ~60s | Cheapest, still fast |
| `a6000` | 48 GB | ~$0.45 | ~60s | Larger models |
| `a100` | 80 GB | ~$1.10 | ~60s | Best quality, expensive |

---

## Option 2: Always-On GPU (for heavy use)

If you generate 50+ videos/day, keep a pod running 24/7.

### Step 1: Deploy on RunPod
1. Go to https://runpod.io → Deploy → GPU Pods
2. Select RTX 4090 (~$0.50/hr, ~$360/month) or RTX 4000 Ada (~$0.25/hr, ~$180/month)
3. Use template: PyTorch 2.1+ CUDA 12.1
4. Add volume: 50GB at /workspace
5. Deploy

### Step 2: Install the service
```bash
ssh root@<POD_IP>
git clone <your-repo> /app/ai-gen
cd /app/ai-gen
bash startup.sh
```

### Step 3: Configure PRACHAR
Add to `.env`:
```bash
AI_GEN_URL=http://<POD_IP>:8100
```

---

## Option 3: fal.ai API (no GPU management, pay per video)

Simplest but costs more per video.

### Step 1: Get fal.ai API key
1. Go to https://fal.ai
2. Sign up, add billing credits ($5+)
3. Go to Dashboard → API Keys
4. Create a key

### Step 2: Configure PRACHAR
```bash
FAL_KEY=your_fal_api_key_here
```

**Cost:** ~$0.05-0.25 per video

---

## Priority order

The backend tries services in this order:
1. **AI_GEN_URL** — static always-on GPU (if set and running)
2. **RUNPOD_API_KEY** — auto spin-up/shut-down (if set)
3. **FAL_KEY** — fal.ai API fallback (if set)

You can set multiple — it will fall back gracefully.

---

## Models Used

| Task | Model | VRAM | Quality | Open Source |
|---|---|---|---|---|
| Text-to-Video | Wan 2.1 T2V 1.3B | 8 GB | 480P, 5s clips | Apache 2.0 |
| Text-to-Image | FLUX.1 Schnell | 10 GB | 1024x1024, 4 steps | Apache 2.0 |

No API costs, no rate limits, unlimited generations. You only pay for GPU rental.

## Cost comparison

| Method | 10 videos/month | 100 videos/month | 1000 videos/month |
|---|---|---|---|
| RunPod auto spin-up | ~$0.50 | ~$5 | ~$50 |
| fal.ai API | ~$0.50-2.50 | ~$5-25 | ~$50-250 |
| Always-on RTX 4090 | ~$360 | ~$360 | ~$360 |
| Always-on RTX 4000 | ~$180 | ~$180 | ~$180 |

**Break-even:** Always-on becomes cheaper at ~700-1000 videos/month.
