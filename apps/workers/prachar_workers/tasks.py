"""Celery task for async video generation.

Dispatched by POST /video/generate-async. Stores results in Redis for
the GET /video/jobs/{job_id} status endpoint to read.
"""
from __future__ import annotations

import logging
import time

from .celery_app import app

log = logging.getLogger(__name__)


@app.task(name="prachar_workers.tasks.generate_video_task", bind=True, max_retries=0)
def generate_video_task(self, job_id: str, tenant_id: str, user_id: str, **kwargs) -> dict:
    """Generate a video asynchronously and store the result in Redis.

    kwargs: prompt, quality, duration, resolution, aspect_ratio,
            video_type, with_audio, image_base64, model
    """
    import redis as _redis
    from prachar_shared.config import get_settings
    from prachar_shared.redis_utils import normalize_redis_url

    s = get_settings()
    r = _redis.from_url(normalize_redis_url(s.redis_url), decode_responses=True)
    job_key = f"video_job:{job_id}"

    # Mark as running
    r.hset(job_key, mapping={
        "status": "running",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "started_at": str(int(time.time())),
    })
    r.expire(job_key, 3600)  # 1 hour TTL

    try:
        # Import the sync generation logic and call it
        # We run the async function via asyncio.run since Celery tasks are sync
        import asyncio


        # Build a minimal request object matching VideoGenRequest
        class _Req:
            pass
        req = _Req()
        for k, v in kwargs.items():
            setattr(req, k, v)
        # Ensure defaults
        if not hasattr(req, 'quality'):
            req.quality = "lite"
        if not hasattr(req, 'with_audio'):
            req.with_audio = True
        if not hasattr(req, 'image_base64'):
            req.image_base64 = ""
        if not hasattr(req, 'model'):
            req.model = ""

        # Call the video generation logic
        # We import here to avoid circular imports at module load time
        from prachar_api.routers.video_gen import (
            ASPECT_RATIOS,
            _call_fal_video,
            _call_gemini_veo,
            _get_gemini_api_key,
            _get_settings,
            _normalize_quality,
        )

        quality = _normalize_quality(req)
        aspect = ASPECT_RATIOS.get(getattr(req, 'video_type', 'landscape'), getattr(req, 'aspect_ratio', '16:9'))
        enhanced_prompt = kwargs.get('prompt', '').strip()

        result = None
        fal_key = _get_settings().fal_key.strip()
        if fal_key:
            try:
                result = asyncio.run(_call_fal_video(fal_key, req, enhanced_prompt, aspect))
            except Exception as e:
                log.error("fal.ai async video failed: %s", str(e)[:200])

        if not result:
            gemini_key = _get_gemini_api_key()
            if gemini_key:
                try:
                    duration_sec = int(str(kwargs.get('duration', '5')).replace('s', ''))
                    result = asyncio.run(_call_gemini_veo(
                        api_key=gemini_key,
                        prompt=enhanced_prompt,
                        quality=quality,
                        duration_sec=duration_sec,
                        aspect_ratio=aspect,
                        with_audio=kwargs.get('with_audio', True),
                    ))
                except Exception as e:
                    log.error("Gemini Veo async video failed: %s", str(e)[:200])

        if not result:
            r.hset(job_key, mapping={
                "status": "failed",
                "error": "No video generation service succeeded",
            })
            return {"status": "failed"}

        # Store result
        r.hset(job_key, mapping={
            "status": "completed",
            "video_url": result.video_url,
            "model": result.model,
            "duration": result.duration,
            "resolution": result.resolution,
            "generation_time": str(result.generation_time),
            "completed_at": str(int(time.time())),
        })
        return {"status": "completed", "video_url": result.video_url}

    except Exception as e:
        log.error("Async video generation failed: %s", str(e)[:300])
        r.hset(job_key, mapping={
            "status": "failed",
            "error": str(e)[:500],
        })
        return {"status": "failed", "error": str(e)[:500]}
