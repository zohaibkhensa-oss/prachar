from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "local"
    app_name: str = "prachar"
    log_level: str = "INFO"

    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    # DB connection pool — tuned for production. When using PgBouncer, lower
    # pool_size to 10 (PgBouncer multiplexes, so the app pool just covers
    # concurrent requests, not concurrent DB sessions).
    db_pool_size: int = 25
    db_max_overflow: int = 50

    jwt_secret: str = "change-me-jwt"
    jwt_refresh_secret: str = "change-me-refresh"
    jwt_ttl_min: int = 1440
    jwt_refresh_ttl_days: int = 30

    token_enc_key: str = "change-me-32-byte-hex-key-please"

    # Email service (Resend API or SMTP fallback)
    resend_api_key: str = ""  # Get from https://resend.com/apikeys
    email_from: str = "noreply@curv.ai"
    email_from_name: str = "CURV AI"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Frontend URL for email links (verify, reset)
    web_url: str = "http://localhost:3000"
    # Rate limiting (requests per window per IP)
    rate_limit_register_per_hour: int = 5
    rate_limit_login_per_min: int = 10
    rate_limit_password_reset_per_hour: int = 3
    # Master switch — set RATE_LIMIT_ENABLED=false to disable everywhere (tests)
    rate_limit_enabled: bool = True

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "prachar"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ─── Celery worker scaling (10K users) ────────────────────────────────
    # Number of shard queues for the weekly loop. Brands are distributed across
    # these queues by hash(brand_id) % N so multiple workers can process loops
    # in parallel without overlap. At 10K brands: 8 shards × 4 concurrency = 32
    # parallel loops → weekly loop completes in ~5 hours (vs 19h with 1 worker).
    celery_loop_shards: int = 8
    # Per-queue worker concurrency (processes per worker container). Tune to
    # CPU cores: 4 for a 4-vCPU box, 8 for 8-vCPU. Higher = more parallel tasks
    # but more memory pressure (each Celery process ~100-200MB).
    celery_concurrency_loop: int = 4
    celery_concurrency_ingest: int = 2
    celery_concurrency_organic: int = 4
    celery_concurrency_ads: int = 2
    celery_concurrency_measure: int = 2
    celery_concurrency_creative: int = 2
    # Max tasks per worker child before restart (memory leak protection).
    # Lower = more restarts (safer) but more startup overhead.
    celery_max_tasks_per_child: int = 100
    # Batch size for dispatch_due — how many brands to enqueue per Redis pipeline.
    # 100 is a good balance: avoids Redis spike, keeps dispatch fast.
    celery_dispatch_batch_size: int = 100
    # Prefetch multiplier — 1 is correct for long-running tasks (prevents one
    # worker from hogging the queue). For short tasks, increase to 4-8.
    celery_prefetch_multiplier: int = 1
    s3_region: str = "us-east-1"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    fal_key: str = ""
    ai_gen_url: str = ""  # Self-hosted GPU service URL (always-on)
    runpod_api_key: str = ""  # RunPod API key for auto spin-up/shut-down
    runpod_gpu_type: str = "rtx4090"  # GPU type: rtx4090, rtx4000, a6000, a100
    modal_video_url: str = ""  # Modal.com serverless GPU endpoint for video
    modal_image_url: str = ""  # Modal.com serverless GPU endpoint for image
    ai_default_provider: str = "groq"
    ai_small_model: str = "llama-3.3-70b-versatile"
    ai_large_model: str = "llama-3.3-70b-versatile"
    ai_budget_starter_inr: int = 50000
    ai_budget_growth_inr: int = 200000
    ai_budget_agency_inr: int = 1000000

    # organic channel creds
    google_client_id: str = ""
    google_client_secret: str = ""

    # social login (Google Sign-In, Apple Sign-In)
    google_sign_in_client_id: str = ""
    apple_sign_in_client_id: str = ""
    gsc_client_id: str = ""
    gsc_client_secret: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    pinterest_client_id: str = ""
    pinterest_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_token: str = ""
    telegram_bot_token: str = ""
    line_channel_id: str = ""
    line_channel_secret: str = ""
    kakao_rest_api_key: str = ""
    vk_client_id: str = ""
    vk_client_secret: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # ads networks
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    # Gemini / Veo video generation (Google AI Studio API)
    gemini_api_key: str = ""  # Get from https://aistudio.google.com/apikey
    veo_default_tier: str = "lite"  # lite | fast | standard
    meta_ads_app_id: str = ""
    meta_ads_app_secret: str = ""
    tiktok_ads_app_id: str = ""
    tiktok_ads_app_secret: str = ""
    microsoft_ads_client_id: str = ""
    microsoft_ads_client_secret: str = ""
    microsoft_ads_developer_token: str = ""
    linkedin_ads_client_id: str = ""
    linkedin_ads_client_secret: str = ""
    x_ads_client_id: str = ""
    x_ads_client_secret: str = ""

    # billing
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # Plan prices (env-driven — change without code edits)
    plan_starter_price_inr: int = 999
    plan_growth_price_inr: int = 2999
    plan_agency_price_inr: int = 9999
    plan_starter_price_usd: int = 12
    plan_growth_price_usd: int = 36
    plan_agency_price_usd: int = 120
    # Stripe product/price IDs (created in Stripe dashboard)
    stripe_price_starter_id: str = ""
    stripe_price_growth_id: str = ""
    stripe_price_agency_id: str = ""
    # Razorpay plan IDs (created in Razorpay dashboard)
    razorpay_plan_starter_id: str = ""
    razorpay_plan_growth_id: str = ""
    razorpay_plan_agency_id: str = ""

    # helpers
    serp_api_key: str = ""
    page_speed_api_key: str = ""

    # web
    next_public_api_base: str = "http://localhost:8000"

    def plan_budget(self, plan: str) -> int:
        return {
            "starter": self.ai_budget_starter_inr,
            "growth": self.ai_budget_growth_inr,
            "agency": self.ai_budget_agency_inr,
        }.get(plan, self.ai_budget_starter_inr)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
