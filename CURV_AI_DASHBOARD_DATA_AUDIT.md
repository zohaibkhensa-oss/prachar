# CURV AI — Dashboard Data Rendering & Analytics Forensic Audit

**Verdict: BACKEND/DATA PIPELINE FIXED, PROVIDER DATA PENDING**
Every empty widget had a real root cause — none were cosmetic. Fixes are
deployed; whether numbers appear now depends on what the connected
providers actually expose (YouTube Analytics returns real rows; the others
need connections or approvals that don't exist yet).

## Root causes found (per widget)

| Widget | Root cause | Fix |
|---|---|---|
| **All KPIs + chart** | `metrics/summary` → 500: Postgres `ORDER BY date_trunc($6)` didn't match the `GROUP BY` expression ($5). No event rows existed anyway because no sync had ever run | Order by SELECT alias; new `/metrics/sync` endpoint |
| **Recent Content** | **Publish never persisted** — `publish` did `session.add(ContentItem)` + `log_audit` with NO `session.commit()` → rolled back at request end. Both published posts (incl. the YouTube upload that *did* reach YouTube) left no DB record | `await session.commit()` after add+audit; same fix for the refreshed-token bundle (`flush`→`commit`) |
| **Engagements** | YouTube `metrics()` never requested `likes/comments/shares` | Added to the Analytics API metrics string |
| **All metrics** | Metric-name mismatch: adapters emit `views`/`likes`/`comments`; dashboard looked for `impressions`/`engagements`/`clicks`/`spend` | Canonical bucket map in `metrics/summary`: `views+impressions`→reached, `likes+comments+shares+saves+engagements`→engagements, `clicks+website_visits`→visits, `spend+cost`→spend (documented in code) |
| **Worker sync** | `ingest_youtube_metrics` loaded tokens for `GBP_CHANNEL` → always `tokens_unavailable` skip | `YOUTUBE_CHANNEL` |
| **Post-publish refresh** | Nothing invalidated queries or triggered sync; the post could only appear after a manual reload *if* it had been persisted | Composer invalidates `brand-content` + `metrics-summary` and fire-and-forgets `POST /metrics/sync` |
| **Sync state** | No way to tell whether data was missing vs never fetched | `last_synced` in summary; dashboard Sync button + tooltip |

## Data-flow (as deployed)

```
Composer post ──► POST /brands/{id}/media/upload ──► S3 (SigV4)
        │
        └──► POST /brands/{id}/publish ──► adapter.publish
              │                               │ provider API
              │                               ▼
              │                          native_id + url
              ▼
        ContentItem (COMMITTED) + AuditEvent("content.publish")
              │
              ├──► invalidate brand-content ──► Recent Content shows post
              └──► POST /metrics/sync ──► adapter.metrics(tokens, 30d)
                        │ writes MetricEvent rows (idempotent per channel+day)
                        ▼
              GET /metrics/summary ──► canonical buckets → KPI cards + chart
```

## What the user must do to recover the lost posts

The YouTube video published successfully to "Brow Ai" but **no CURV record
exists** (rolled-back write predates the fix). Reposting once via
`/app/post` is the clean way to create a durable record; the video itself
is live on the channel.

## Remaining honest limitations

- **Website Visits** stays empty until a GA4/website-analytics connection exists — no source, correctly shown as "no data", not fabricated.
- **Ad Spend** stays empty until an ads account connects and runs spend — correctly absent.
- **People Reached / Engagements** populate only after `metrics/sync` runs and the provider exposes them; YouTube Analytics can lag new uploads by hours — a brand-new video may truthfully show few/zero metrics on day one.
- Metric sync also runs via the existing `performance.py` ingest workers on the `measure` queue (bug-fixed); the HTTP sync endpoint is the interactive path.

## Files changed

- `apps/api/prachar_api/routers/brands.py` — commit publish+refresh, metrics sync endpoint, canonical buckets, last_synced, order-by fix
- `packages/shared/prachar_shared/adapters/organic/youtube.py` — likes/comments/shares metrics
- `apps/workers/prachar_workers/performance.py` — YOUTUBE_CHANNEL token lookup
- `apps/web-v2/src/app/app/post/page.tsx` — query invalidation + post-publish sync
- `apps/web-v2/src/app/app/dashboard/page.tsx` — Sync button, last-synced tooltip

## Tests / build

- `test_youtube_publish.py` (7) + `test_api_contracts.py` + `test_architecture_freeze.py` — 28 green
- `tsc --noEmit` clean; production build + S3 deploy done

## Staging verification

- `GET /brands/{id}/content` → published items persist after repost
- `POST /brands/{id}/metrics/sync` → `{"ok":true,"synced":[{"channel":"youtube","status":"ok",...}]}`
- `GET /brands/{id}/metrics/summary` → 200 with canonical totals + `last_synced`
