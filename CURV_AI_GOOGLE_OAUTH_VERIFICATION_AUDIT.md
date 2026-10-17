# CURV AI — Google OAuth Verification Readiness Audit

**Date:** 2026-10-17 · **Status:** Diagnosis only — no code/config changed.

## 1. Scopes actually requested in production code

| Scope | Where requested | API it unlocks | Classification |
|---|---|---|---|
| `…/auth/youtube` | `connections.py:118` `_build_youtube_oauth`; `youtube.py:29` | YouTube Data API v3 — upload (`videos.insert`), metadata update (`videos.update`), `channels.list` | **Sensitive** |
| `…/auth/yt-analytics.readonly` | `connections.py:103,118`; `youtube.py:31` | YouTube Analytics `v2/reports` — views, likes, comments, watch-time, subscribers | **Sensitive** |
| `…/auth/yt-analytics-monetary.readonly` | `youtube.py:32` (`_YT_SCOPES` only — the adapter's own `auth_url`, not the live router URL) | Monetary analytics (ad revenue) | **RESTRICTED — unused** |
| `…/auth/webmasters` | `connections.py:103` `_build_google_oauth`; `gsc.py:31` | Search Console: `sites.list`, `searchAnalytics/query`, `urlInspection/index:inspect` | **Sensitive** |
| `…/auth/business.manage` | `connections.py:103`; `gmb.py:22` | Google Business Profile (`mybusiness.googleapis.com/v4`) | **Sensitive, needs prior GMB API enablement** |
| `profile openid email` | Google Sign-In (`auth.py:399` tokeninfo) + `GOOGLE_SIGN_IN_CLIENT_ID` | Identity sign-in only | Non-sensitive |

Live consent currently shows only `youtube` + `yt-analytics.readonly` — the stored token confirms.

## 2. Scope → feature map (truth check)

| Scope | Feature that uses it | File evidence |
|---|---|---|
| `youtube` | "Create Post → YouTube" video upload (resumable `videos.insert`); metadata update path | `youtube.py:52 _upload_video`, `youtube.py:266 publish`, `brands.py` `/publish` |
| `yt-analytics.readonly` | Dashboard/Analytics metrics sync (`POST /brands/{id}/metrics/sync` → `youtubeanalytics v2/reports`) | `youtube.py:421 metrics`, `brands.py` sync endpoint |
| `webmasters` | GSC sites list, search-analytics queries (metrics), **URL Inspection `index:inspect`** (publish path calls it) | `gsc.py:222-260`, `performance.py` |
| `business.manage` | GMB local posts — **stub only** (`gmb.py:113` "Stub: real implementation POSTs localPosts") | `gmb.py` |
| `yt-analytics-monetary.readonly` | **Nothing** — revenue metrics were removed because the scope is ungranted | `youtube.py:428` (metrics_str excludes revenue) |

## 3. Narrowest viable scope per feature

| Current | Can narrow to? | Verdict |
|---|---|---|
| `youtube` (full) | `youtube.upload` + `youtube.readonly` | **Could narrow** — upload covered by `youtube.upload`; `channels.list` covered by `youtube.readonly`. BUT the metadata-update path (`videos.update`) is implemented and would break — keep `youtube` *if* metadata edits ship, else narrow |
| `yt-analytics.readonly` | none narrower | Keep |
| `webmasters` | `webmasters.readonly` | **Cannot narrow while `index:inspect` is used** — URL Inspection requires full scope. If inspect dropped, readonly suffices for searchAnalytics |
| `business.manage` | none | Keep only when GMB posts actually ship; currently dead weight on the consent screen |
| `yt-analytics-monetary.readonly` | **REMOVE** | Unused + **restricted class** — its presence forces the heaviest verification tier for zero benefit |

## 4. Restricted-scope findings

- `yt-analytics-monetary.readonly` is the only **restricted** scope in the codebase → triggers Tier-3/CASS-style security assessment. **Action: strip it from `_YT_SCOPES`** before submitting.
- Everything else is sensitive → standard verification + demo video.
- `business.manage` additionally requires the Business Profile Management API enabled + Google's own product approval — independent of OAuth verification.

## 5. Consistency check (homepage/consent/legal)

| Item | Value | Status |
|---|---|---|
| Homepage | `curvai.org` — "CURV AI — Your Autonomous Marketing Team" | ✅ |
| Privacy | `curvai.org/privacy` (200) | ✅ |
| Terms | `curvai.org/terms` (200) | ✅ |
| Domain ownership | TXT `google-site-verification` live in Route53 zone `Z05391603QFNKF4X5ZILE` | ✅ |
| Redirect URIs | `app.curvai.org/app/connections/{youtube,google,gsc,gmb}/callback` — must all be registered on the OAuth client | ⚠ verify each in console |
| Authorized domain | `curvai.org` | ✅ |
| Logo | `curvai.org/curv-logo.png` | ✅ |

## 6. Demo-video storyboard (~3 min)

1. **Homepage** → brand "CURV AI" visible, link to `/privacy` + `/terms`.
2. **App** → Channels page → click **Connect** on YouTube.
3. **Consent screen** — show app name "Curv AI", the OAuth **client ID**, both scopes listed.
4. **Continue** → lands on Connections showing **Connected / Brow Ai**.
5. **Scope 1 proof** — `/app/post` → caption → attach 10s MP4 → tick YouTube → Post → open `youtube.com/watch?v=…` — video on the channel.
6. **Scope 2 proof** — `/app/analytics` → click **Sync** → People Reached + Customer actions populate from YouTube Analytics.
7. **Revoke path** — Connections → ⋯ → Disconnect (shows data deletion handling).

## 7. Draft justification text (per scope)

**`auth/youtube`** — "CURV AI lets business owners publish marketing videos they create to their own YouTube channel from one composer. The scope is used solely for `videos.insert` uploads and metadata updates on the user's own channel — no reading of other users' data, no deletion. `youtube.upload` alone cannot update titles/descriptions on previously uploaded videos; `youtube.readonly` cannot upload."

**`auth/yt-analytics.readonly`** — "Powers the Reach/Engagement metrics on the user's Results dashboard — read-only aggregation of their own channel's views, likes, comments and watch time. Never used to access other channels' data."

**`auth/webmasters`** — "Reads the user's own Search Console search-analytics and runs URL Inspection to show their site's search visibility inside CURV AI. `webmasters.readonly` is insufficient because URL Inspection (`index:inspect`) is a write action."

**`auth/business.manage`** — *(include only if GMB ships)* "Lets users publish local-business updates to their own Google Business Profile locations."

## 8. Recommended next actions (approval needed)

1. Remove `yt-analytics-monetary.readonly` from `_YT_SCOPES` (code change, ~2 lines) — eliminates the restricted-scope requirement.
2. Decide: keep `youtube` (justified if metadata-update ships) or narrow to `youtube.upload` + `youtube.readonly`.
3. Decide: keep `business.manage` in the Google OAuth URL only if GMB local-posts is a launch feature — else strip until S8 ships it.
4. Register all four callback URIs on the OAuth client.
5. Record the demo video per storyboard §6, then submit.
