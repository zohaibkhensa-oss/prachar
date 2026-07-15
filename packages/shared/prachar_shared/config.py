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

    jwt_secret: str = "change-me-jwt"
    jwt_refresh_secret: str = "change-me-refresh"
    jwt_ttl_min: int = 1440
    jwt_refresh_ttl_days: int = 30

    token_enc_key: str = "change-me-32-byte-hex-key-please"

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "prachar"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    fal_key: str = ""
    ai_gen_url: str = ""  # Self-hosted GPU service URL (always-on)
    runpod_api_key: str = ""  # RunPod API key for auto spin-up/shut-down
    runpod_gpu_type: str = "rtx4090"  # GPU type: rtx4090, rtx4000, a6000, a100
    ai_default_provider: str = "groq"
    ai_small_model: str = "llama-3.3-70b-versatile"
    ai_large_model: str = "llama-3.3-70b-versatile"
    ai_budget_starter_inr: int = 100
    ai_budget_growth_inr: int = 1000
    ai_budget_agency_inr: int = 100000

    # organic channel creds
    google_client_id: str = ""
    google_client_secret: str = ""
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

    # ads networks
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
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
