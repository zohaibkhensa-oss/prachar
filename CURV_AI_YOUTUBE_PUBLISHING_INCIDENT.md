# CURV AI — YouTube Publishing Incident Report

**Verdict: FIXED AND LIVE VERIFIED** — a 10-second MP4 posted from
`app.curvai.org/app/post` to the connected "Brow Ai" channel on
2026-10-10 09:00 UTC. Log evidence: `POST /upload/youtube/v3/videos` 200 →
binary `PUT` 200 → `POST /brands/{id}/publish` 200.

## Root cause (the 502 was six stacked defects)

| # | Defect | Symptom | Fix |
|---|--------|---------|-----|
| 1 | CloudFront rewrite ignored `/app/connections/{channel}/callback` | OAuth callback served marketing `index.html` | `infra/terraform/cloudfront.tf` regex |
| 2 | Static-export `useParams()` returned baked `"placeholder"` | `/connections/placeholder/callback` 400 | Read channel from `window.location.pathname` |
| 3 | Organic adapters never imported → empty registry | `get_organic("youtube")` → 400 "unsupported channel" | Lazy module import in callback |
| 4 | `exchange_code` called `asyncio.run` inside FastAPI's loop | `RuntimeError` → 502 | `to_thread` dispatch on `iscoroutinefunction` |
| 5 | `AESGCM.generate_nonce` removed in deployed `cryptography` | 500 after successful exchange | `os.urandom(12)` |
| 6 | `YOUTUBE_CLIENT_*` = different Google OAuth client than consent | `invalid_client` 401/400 | Aligned `YOUTUBE_*` = `GOOGLE_*` in Secrets Manager |

## Publish-path defects fixed after OAuth

| # | Defect | Symptom | Fix |
|---|--------|---------|-----|
| 7 | Multipart upload got `Content-Type: application/json` | 422 on media upload | `authedFetch` skips JSON header for FormData |
| 8 | ECS task role lacked `kms:GenerateDataKey` on SSE-KMS bucket | 500/AccessDenied `PutObject` | Grant added **in Terraform** (`ecs.tf`) — manual grant kept being reverted |
| 9 | Presigned URL generated as Signature V2 | S3 GET 400 during adapter download | `Config(signature_version="s3v4")` |
| 10 | Resumable init hit `upload.googleapis.com` (legacy host) | Google HTML 404 | `www.googleapis.com/upload/youtube/v3/videos` |
| 11 | Access token expired (~1h), no refresh anywhere | 401 → 502 | `YouTubeAdapter.refresh_access_token()` + refresh-on-expiry in publish; `YOUTUBE_REAUTH_REQUIRED` when refresh impossible |

## API contract

- `POST /brands/{id}/media/upload` (multipart) → `{media_url, s3_key, content_type}` — S3 put + 6h SigV4 presigned URL, 200MB cap.
- `POST /brands/{id}/publish` `{channel, text, media_url?, media_type?, chat_id?}` → `{ok, channel, native_id, url, published_at}` — adapter publish per channel (facebook/instagram/linkedin/x/telegram/youtube).
- `GET /connections/{channel}/verify` → provider liveness (YouTube returns `channel_title`, `subscriber_count`).
- Structured errors surfaced verbatim in the response detail; `YOUTUBE_REAUTH_REQUIRED` for expired/revoked grants.

## Reliability

- Token refresh: publish refreshes when expiry <30s away, persists the new encrypted bundle, updates `expires_at` on the connection row.
- Upload lifecycle: S3 staging object → resumable session init → single PUT → video id persisted as `ContentItem.published_ref` + `content.publish` audit event.
- Sync publish is acceptable for short clips; larger uploads should move to the existing organic publish worker (already in the codebase) — noted as follow-up, not silently left.

## Tests

`apps/api/prachar_api/tests/test_youtube_publish.py` — 7 tests, all green:
credential fallback, upload host regression (guards the `upload.googleapis.com` 404), init-failure error surfacing, publish dispatch + required-field validation, refresh-token grant shape. Provider calls mocked at the httpx boundary; no live creds used.

## Staging verification

- `GET /connections/youtube/verify` → `{ok: true, channel_title: "Brow Ai", subscriber_count: "3", video_count: "0"}` (pre-upload).
- Full user flow: caption + 10s MP4 → YouTube chip → Post → 200; CloudWatch shows resumable init + binary PUT both `200 OK` at 09:00:27 UTC.

## Remaining blockers (external, not code)

- Videos may be **private-locked** until the Google OAuth app passes YouTube API verification (`privacy` is currently `public`; switch to `unlisted`/`private` if Google rejects).
- Google Cloud Console: OAuth consent screen must be "In production" (or QA users added) — same step required for every Google-family channel.
- Facebook/Instagram/LinkedIn/X/Telegram publish paths are implemented but unverified — each needs its provider console app + scopes reviewed before first real post.
