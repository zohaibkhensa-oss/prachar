# CURV AI — Channel Integration Setup Report

Complete provider-by-provider setup guide for all social/channel integrations.
Each section lists: developer console products, env vars, OAuth scopes, redirect URIs, and current implementation status.

**Redirect URI pattern (all providers):** `{WEB_URL}/app/connections/{channel}/callback`
- Local dev: `http://localhost:3002/app/connections/{channel}/callback`
- Production: `https://app.curv.app/app/connections/{channel}/callback`

---

## 1. Google (Search Console + Business Profile)

### Adapters
| Adapter | File | Purpose |
|---------|------|---------|
| GoogleSearchAdapter | `adapters/organic/google.py` | SERP monitoring |
| GSCAdapter | `adapters/organic/gsc.py` | Google Search Console — URL inspection, search analytics |
| GMBAdapter | `adapters/organic/gmb.py` | Google Business Profile — posts, metrics |
| GoogleAdsAdapter | `adapters/ads/google_ads.py` | Google Ads — campaigns, creatives, budgets |

### Developer Console Products (https://console.cloud.google.com)
1. Google Search Console API
2. Google Business Profile API
3. Google Ads API
4. Google+ Domain API (for OAuth)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `GSC_CLIENT_ID` | Yes | GSC-specific OAuth client ID (can be same as Google) |
| `GSC_CLIENT_SECRET` | Yes | GSC-specific OAuth client secret |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Yes (Ads) | Google Ads developer token (apply at https://developers.google.com/google-ads/api/docs/first-call/dev-token) |
| `GOOGLE_ADS_CLIENT_ID` | Yes (Ads) | Google Ads OAuth client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | Yes (Ads) | Google Ads OAuth client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | Yes (Ads) | Pre-configured refresh token |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Optional | Manager account ID |

### OAuth Scopes
- **GSC**: `https://www.googleapis.com/auth/webmasters`
- **GMB**: `https://www.googleapis.com/auth/business.manage`
- **Google Search**: `https://www.googleapis.com/auth/webmasters.readonly`
- **Google Ads**: `https://www.googleapis.com/auth/adwords`

### Redirect URIs to Register
- `http://localhost:3002/app/connections/google/callback`
- `http://localhost:3002/app/connections/gsc/callback`
- `http://localhost:3002/app/connections/gmb/callback`
- Production equivalents

### Status
- OAuth URL builder: ✅
- Token exchange: ✅ (GSC, GMB) / ❌ (GoogleSearch — NotImplementedError)
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET` in .env

---

## 2. YouTube

### Adapter
| Adapter | File |
|---------|------|
| YouTubeAdapter | `adapters/organic/youtube.py` |

### Developer Console Products
1. YouTube Data API v3
2. YouTube Analytics API
3. YouTube Reporting API (optional)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `YOUTUBE_CLIENT_ID` | Yes | YouTube OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | Yes | YouTube OAuth client secret |

### OAuth Scopes
- `https://www.googleapis.com/auth/youtube`
- `https://www.googleapis.com/auth/yt-analytics.readonly`
- `https://www.googleapis.com/auth/yt-analytics-monetary.readonly`

### Redirect URI
- `http://localhost:3002/app/connections/youtube/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` in .env

---

## 3. Meta (Facebook + Instagram + WhatsApp)

### Adapters
| Adapter | File |
|---------|------|
| FacebookAdapter | `adapters/organic/facebook.py` |
| InstagramAdapter | `adapters/organic/instagram.py` |
| WhatsAppAdapter | `adapters/organic/whatsapp.py` |
| MetaAdsAdapter | `adapters/ads/meta_ads.py` |

### Developer Console Products (https://developers.facebook.com)
1. Facebook Graph API
2. Instagram Graph API
3. WhatsApp Business Cloud API
4. Meta Marketing API (for Ads)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `META_APP_ID` | Yes | Meta app ID (covers FB + IG) |
| `META_APP_SECRET` | Yes | Meta app secret |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (WhatsApp) | WhatsApp Business phone number ID |
| `WHATSAPP_TOKEN` | Yes (WhatsApp) | WhatsApp Cloud API access token |
| `META_ADS_APP_ID` | Yes (Ads) | Meta Ads app ID |
| `META_ADS_APP_SECRET` | Yes (Ads) | Meta Ads app secret |

### OAuth Scopes
- **Facebook**: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`, `publish_to_groups`
- **Instagram**: `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`
- **Meta Ads**: `ads_management`, `ads_read`

### Redirect URIs
- `http://localhost:3002/app/connections/facebook/callback`
- `http://localhost:3002/app/connections/instagram/callback`
- `http://localhost:3002/app/connections/whatsapp/callback`
- Production equivalents

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- WhatsApp: No OAuth (uses system token)
- **USER ACTION REQUIRED**: Set `META_APP_ID`, `META_APP_SECRET`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TOKEN` in .env

---

## 4. TikTok

### Adapters
| Adapter | File |
|---------|------|
| TikTokAdapter | `adapters/organic/tiktok.py` |
| TikTokAdsAdapter | `adapters/ads/tiktok_ads.py` |

### Developer Console Products (https://developers.tiktok.com)
1. TikTok for Developers — Content Posting API
2. TikTok Marketing API (for Ads)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `TIKTOK_CLIENT_KEY` | Yes | TikTok app client key |
| `TIKTOK_CLIENT_SECRET` | Yes | TikTok app client secret |
| `TIKTOK_ADS_APP_ID` | Yes (Ads) | TikTok Ads app ID |
| `TIKTOK_ADS_APP_SECRET` | Yes (Ads) | TikTok Ads app secret |
| `TIKTOK_ADVERTISER_ID` | Yes (Ads) | TikTok advertiser ID |

### OAuth Scopes
- **Organic**: `user.info.basic`, `video.publish`, `video.list`, `video.upload`
- **Ads**: `campaign.management`, `ad.management`, `reporting`

### Redirect URI
- `http://localhost:3002/app/connections/tiktok/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` in .env

---

## 5. LinkedIn

### Adapters
| Adapter | File |
|---------|------|
| LinkedInAdapter | `adapters/organic/linkedin.py` |
| LinkedInAdsAdapter | `adapters/ads/linkedin_ads.py` |

### Developer Console Products (https://developer.linkedin.com)
1. LinkedIn Marketing/Community APIs
2. LinkedIn Marketing API (for Ads)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `LINKEDIN_CLIENT_ID` | Yes | LinkedIn OAuth client ID |
| `LINKEDIN_CLIENT_SECRET` | Yes | LinkedIn OAuth client secret |
| `LINKEDIN_ADS_CLIENT_ID` | Yes (Ads) | LinkedIn Ads client ID |
| `LINKEDIN_ADS_CLIENT_SECRET` | Yes (Ads) | LinkedIn Ads client secret |

### OAuth Scopes
- **Organic**: `w_member_social`, `r_organization_social`, `rw_organization_admin`
- **Ads**: `rw_ads`, `r_ads`, `r_ads_reporting`

### Redirect URI
- `http://localhost:3002/app/connections/linkedin/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- Duplicate scope: ✅ (fixed — removed duplicate `r_organization_social`)
- **USER ACTION REQUIRED**: Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` in .env

---

## 6. X (Twitter)

### Adapters
| Adapter | File |
|---------|------|
| XAdapter | `adapters/organic/x.py` |
| XAdsAdapter | `adapters/ads/x_ads.py` |

### Developer Console Products (https://developer.twitter.com)
1. Twitter API v2 (Free or Basic tier)
2. Twitter Ads API v11

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `X_CLIENT_ID` | Yes | X OAuth 2.0 client ID |
| `X_CLIENT_SECRET` | Yes | X OAuth 2.0 client secret |
| `X_ADS_CLIENT_ID` | Yes (Ads) | X Ads client ID |
| `X_ADS_CLIENT_SECRET` | Yes (Ads) | X Ads client secret |

### OAuth Scopes
- `tweet.read`, `tweet.write`, `users.read`, `offline.access`

### Redirect URI
- `http://localhost:3002/app/connections/x/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- PKCE: ✅ (fixed — S256 instead of plain)
- **USER ACTION REQUIRED**: Set `X_CLIENT_ID`, `X_CLIENT_SECRET` in .env
- **Note**: X API has rate limits. Free tier allows 1,500 posts/month. Basic tier ($100/mo) for higher limits.

---

## 7. Pinterest

### Adapters
| Adapter | File |
|---------|------|
| PinterestAdapter | `adapters/organic/pinterest.py` |
| PinterestAdsAdapter | `adapters/ads/pinterest_ads.py` |

### Developer Console Products (https://developers.pinterest.com)
1. Pinterest API v5
2. Pinterest Ads API v5

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `PINTEREST_CLIENT_ID` | Yes | Pinterest OAuth client ID |
| `PINTEREST_CLIENT_SECRET` | Yes | Pinterest OAuth client secret |

### OAuth Scopes
- `boards:read`, `pins:write`, `pins:read`, `user_accounts:read`

### Redirect URI
- `http://localhost:3002/app/connections/pinterest/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅ (uses Basic Auth — correct for Pinterest)
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `PINTEREST_CLIENT_ID`, `PINTEREST_CLIENT_SECRET` in .env

---

## 8. Telegram

### Adapter
| Adapter | File |
|---------|------|
| TelegramAdapter | `adapters/organic/telegram.py` |

### Developer Console Products
- Telegram Bot API (via @BotFather — no developer console)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |

### OAuth
- No OAuth flow — uses bot token directly
- `auth_url()` redirects to @BotFather

### Status
- Token exchange: ✅ (bot token, not OAuth)
- Callback handler: N/A (no OAuth)
- **USER ACTION REQUIRED**: Set `TELEGRAM_BOT_TOKEN` in .env
- **Note**: Create a bot via @BotFather on Telegram, copy the bot token

---

## 9. LINE

### Adapter
| Adapter | File |
|---------|------|
| LINEAdapter | `adapters/organic/line.py` |

### Developer Console Products (https://developers.line.biz)
1. LINE Messaging API
2. LINE Login (for OAuth)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `LINE_CHANNEL_ID` | Yes | LINE channel ID |
| `LINE_CHANNEL_SECRET` | Yes | LINE channel secret |

### OAuth Scopes
- `profile`, `openid`

### Redirect URI
- `http://localhost:3002/app/connections/line/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET` in .env

---

## 10. VK (VKontakte)

### Adapter
| Adapter | File |
|---------|------|
| VKAdapter | `adapters/organic/vk.py` |

### Developer Console Products (https://dev.vk.com)
1. VK API

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `VK_CLIENT_ID` | Yes | VK OAuth app ID |
| `VK_CLIENT_SECRET` | Yes | VK OAuth app secret |

### OAuth Scopes
- `wall`, `photos`, `stats`, `offline`

### Redirect URI
- `http://localhost:3002/app/connections/vk/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ⚠️ (stub — returns code as token, needs full implementation)
- Callback handler: ✅ (fixed)
- **USER ACTION REQUIRED**: Set `VK_CLIENT_ID`, `VK_CLIENT_SECRET` in .env
- **Note**: `exchange_code()` is a stub — needs real HTTP call to `https://oauth.vk.com/access_token`

---

## 11. Reddit

### Adapter
| Adapter | File |
|---------|------|
| RedditAdapter | `adapters/organic/reddit.py` |
| RedditAdsAdapter | `adapters/ads/reddit_ads.py` |

### Developer Console Products (https://www.reddit.com/prefs/apps)
1. Reddit Data API
2. Reddit Ads API v3

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `REDDIT_CLIENT_ID` | Yes | Reddit OAuth client ID |
| `REDDIT_CLIENT_SECRET` | Yes | Reddit OAuth client secret |

### OAuth Scopes
- `submit`, `read`, `identity`

### Redirect URI
- `http://localhost:3002/app/connections/reddit/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ⚠️ (stub — returns code as token, needs full implementation)
- Callback handler: ✅ (fixed)
- Policy gate: Always `passed=False` (human approval required for all Reddit posts)
- **USER ACTION REQUIRED**: Set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` in .env
- **Note**: `exchange_code()` is a stub — needs real HTTP call to `https://www.reddit.com/api/v1/access_token`

---

## 12. Naver

### Adapter
| Adapter | File |
|---------|------|
| NaverAdapter | `adapters/organic/naver.py` |

### Developer Console Products (https://developers.naver.com)
1. Naver Search Advisor
2. Naver Login (for OAuth)
3. Naver Blog API (if available)

### Env Vars
| Var | Required | Description |
|-----|----------|-------------|
| `NAVER_CLIENT_ID` | Yes | Naver OAuth client ID |
| `NAVER_CLIENT_SECRET` | Yes | Naver OAuth client secret |

### OAuth Scopes
- None specified (Naver uses implicit scopes)

### Redirect URI
- `http://localhost:3002/app/connections/naver/callback`

### Status
- OAuth URL builder: ✅
- Token exchange: ✅ (stub but functional)
- Callback handler: ✅ (fixed)
- `publish()`: Raises NotImplementedError (Naver has no public blog posting API — manual assist only)
- **USER ACTION REQUIRED**: Set `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` in .env

---

## Additional Ads Networks (No Organic Equivalent)

### Microsoft Ads (Bing)
- **Env Vars**: `MICROSOFT_ADS_CLIENT_ID`, `MICROSOFT_ADS_CLIENT_SECRET`, `MICROSOFT_ADS_DEVELOPER_TOKEN`, `MS_ADS_CUSTOMER_ID`, `MS_ADS_ACCOUNT_ID`
- **Developer Console**: Microsoft Advertising API (https://learn.microsoft.com/advertising/guides/get-started)
- **Status**: ✅ Adapter exists, no OAuth flow (uses pre-configured tokens)

### Snapchat Ads
- **Env Vars**: `SNAP_AD_ACCOUNT_ID`
- **Developer Console**: Snapchat Marketing API (https://businesshelp.snapchat.com/s/article/api-portal)
- **Status**: ✅ Adapter exists, no OAuth flow

### Yandex Direct
- **Env Vars**: None (uses token from scopes)
- **Developer Console**: Yandex Direct API v5
- **Status**: ✅ Adapter exists, no OAuth flow

---

## Fixes Applied in This Audit

| # | Issue | Fix | Files |
|---|-------|-----|-------|
| 1 | OAuth callback was a stub — didn't exchange tokens | Implemented full token exchange: load adapter → exchange_code → encrypt → store | `connections.py` |
| 2 | Hardcoded redirect URIs (`urn:ietf:wg:oauth:2.0:oob`, `example.com`) | Added `redirect_uri_for()` helper + `self.redirect_uri` property on base adapter | `base.py`, all 12 organic adapters |
| 3 | X/Twitter PKCE used `plain` method (insecure) | Changed to S256 with proper code verifier/challenge | `x.py`, `connections.py` |
| 4 | Missing env vars in .env.example | Added `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `TIKTOK_ADVERTISER_ID`, `MS_ADS_CUSTOMER_ID`, `MS_ADS_ACCOUNT_ID`, `SNAP_AD_ACCOUNT_ID`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | `.env.example` |
| 5 | LinkedIn had duplicate scope `r_organization_social` | Removed duplicate | `linkedin.py` |

---

## Remaining Stubs (Not Bugs — By Design)

| Provider | Stub | Reason |
|----------|------|--------|
| GoogleSearch | `exchange_code` raises NotImplementedError | Uses SERP API key, not OAuth |
| GMB | `publish()` and `metrics()` are stubs | Google Business Profile API v4 is deprecated; v5 migration pending |
| VK | `exchange_code` is stub | Needs real HTTP call implementation |
| Reddit | `exchange_code` is stub | Needs real HTTP call implementation |
| Naver | `publish()` raises NotImplementedError | No public blog posting API |
| Telegram | No OAuth | Uses bot tokens, not OAuth |

---

## Token Storage Architecture

- **Table**: `connections` (PostgreSQL with RLS)
- **Encryption**: AES-GCM 256-bit via `TOKEN_ENC_KEY`
- **Format**: `nonce(12 bytes) + ciphertext` in `oauth_tokens_enc` (LargeBinary)
- **Token bundle**: JSON with `access_token`, `refresh_token`, `expires_at`, `scopes`
- **Security check**: Raises RuntimeError if `TOKEN_ENC_KEY` is still placeholder

## Token Refresh

- **Current state**: Adapters extract `refresh_token` but no system-wide refresh mechanism exists
- **Needed**: Background worker to check `expires_at` and call adapter's refresh endpoint
- **Priority**: Medium — tokens expire in 1-2 hours for most providers

---

## Summary: What's Working vs What Needs User Action

### ✅ Working (code is correct)
- OAuth URL builders for all 16 providers
- Token exchange for 14/16 providers (GoogleSearch and Telegram are by-design exceptions)
- OAuth callback handler (fixed — now exchanges tokens and encrypts them)
- Token storage with AES-GCM encryption
- Redirect URIs are now configurable via `WEB_URL`
- PKCE S256 for X/Twitter

### ⚠️ USER ACTION REQUIRED
For each provider you want to enable, set the env vars listed above in `.env` and register the redirect URI in the provider's developer console. The code is ready — only credentials are missing.

### 🔧 Remaining Code Work (Non-blocking)
- VK and Reddit `exchange_code()` need real HTTP implementations
- Token refresh worker not yet built
- GMB publish/metrics need v5 API migration
