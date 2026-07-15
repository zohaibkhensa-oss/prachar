from __future__ import annotations

from enum import StrEnum


class Plan(StrEnum):
    starter = "starter"
    growth = "growth"
    agency = "agency"


class Role(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class Channel(StrEnum):
    google = "google"
    gsc = "gsc"
    gmb = "gmb"
    youtube = "youtube"
    instagram = "instagram"
    facebook = "facebook"
    tiktok = "tiktok"
    x = "x"
    linkedin = "linkedin"
    pinterest = "pinterest"
    snapchat = "snapchat"
    reddit = "reddit"
    whatsapp = "whatsapp"
    telegram = "telegram"
    line = "line"
    kakao = "kakao"
    vk = "vk"
    yandex = "yandex"
    naver = "naver"
    amazon = "amazon"


class AdsNetwork(StrEnum):
    google_ads = "google_ads"
    meta_ads = "meta_ads"
    tiktok_ads = "tiktok_ads"
    x_ads = "x_ads"
    linkedin_ads = "linkedin_ads"
    pinterest_ads = "pinterest_ads"
    snap_ads = "snap_ads"
    reddit_ads = "reddit_ads"
    microsoft_ads = "microsoft_ads"
    spotify_ads = "spotify_ads"
    taboola = "taboola"
    outbrain = "outbrain"
    amazon_ads = "amazon_ads"
    yandex_direct = "yandex_direct"
    kakao_moment = "kakao_moment"
    line_ads = "line_ads"


class AssetType(StrEnum):
    product = "product"
    video = "video"
    page = "page"
    post = "post"
    creative = "creative"


class AssetStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class PolicyStatus(StrEnum):
    pending = "pending"
    passed = "passed"
    blocked = "blocked"


class CampaignObjective(StrEnum):
    awareness = "awareness"
    traffic = "traffic"
    leads = "leads"
    conversions = "conversions"
    app_installs = "app_installs"
    video_views = "video_views"


class CampaignStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"
    ended = "ended"


class ConnectionStatus(StrEnum):
    pending = "pending"
    active = "active"
    expired = "expired"
    revoked = "revoked"


class Actor(StrEnum):
    user = "user"
    system = "system"
    ai = "ai"


class BillingProvider(StrEnum):
    razorpay = "razorpay"
    stripe = "stripe"


class BillingStatus(StrEnum):
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    trialing = "trialing"


class CreativeType(StrEnum):
    copy = "copy"
    image = "image"
    video = "video"
    thumbnail = "thumbnail"
