# CURV AI — AWS Service Map

| CURV AI Component | Current Technology | AWS Target | Required? | Cost Risk | Notes |
|---|---|---|---|---|---|
| **API (FastAPI)** | Python 3.12, uvicorn, port 8000 | ECS Fargate behind ALB | Yes | Medium | Stateless; SSE needs ALB idle timeout ≥120s; in-memory rate limiting won't scale >1 replica |
| **Frontend (Next.js 15)** | Node 20, port 3002, CSR SPA with API proxy | ECS Fargate behind ALB (NOT S3+CF) | Yes | Medium | Requires running Node server for `/api` rewrite proxy + 30-min `proxyTimeout`; `output: "export"` not set |
| **Celery Workers** | Celery 5.4, Redis broker, 8 queue shards | ECS Fargate (separate service per queue group) | Yes | Medium | Worker image must include `prachar-shared` + `prachar-api` (loop.py imports API runtime) |
| **Celery Beat** | celery-beat scheduler | EventBridge Scheduler or singleton Fargate task | Yes | Low | Must never run >1 replica; weekly loop is the core product |
| **PostgreSQL** | PG 16, SQLAlchemy 2 async, 38 tables, RLS | RDS PostgreSQL 16 (db.t3.small) | Yes | High | Multi-AZ doubles cost; 11 tables missing RLS policies; no pgvector needed yet |
| **Redis** | Celery broker+backend, idempotency, progress, DLQ | ElastiCache Redis 7.1 (cache.t3.small) | Yes | High | 2 nodes with failover = ~$50/mo at t3.small; could use single-node for dev |
| **Object Storage** | MinIO (local), S3 (prod), reports + knowledge docs | S3 (1 bucket, KMS, lifecycle) | Yes | Low | ~$2/mo for 20GB; currently only PDF reports use S3; video/images use fal.ai URLs |
| **CDN / HTTPS** | Render TLS (automatic) | CloudFront + ACM + Route53 | Yes | Low | PriceClass_100; SPA fallback configured; OAI (should upgrade to OAC) |
| **Load Balancer** | Render proxy | ALB (internet-facing) | Yes | Medium | ~$25/mo base + LCUs; HTTPS listener needs regional cert (not us-east-1) |
| **NAT Gateway** | N/A (Render) | 1 NAT gateway | Yes | Medium | ~$35/mo; SPOF if single-AZ; cross-AZ charges if multi-AZ |
| **WAF** | N/A | AWS WAF on ALB | Optional | Low | $5/mo + $1/rule; rate limit 2000/5min, SQLi, XSS rules |
| **Secrets** | `.env` file | Secrets Manager + Parameter Store | Yes | Low | ~$0.40/secret/mo; DB creds, JWT, OAuth tokens, API keys |
| **Container Registry** | N/A | ECR (3 repos: api, web, worker) | Yes | Low | ~$1/mo for stored images; lifecycle keep-10 |
| **Monitoring** | stdout logs, `/metrics` (Prometheus), in-memory | CloudWatch Logs + Alarms + Dashboard | Yes | Low | 5 alarms exist; SNS topic has NO subscription; no Sentry/OTel |
| **CI/CD** | GitHub Actions (ci.yml, deploy.yml) | GitHub Actions → OIDC → IAM role | Yes | Low | deploy.yml has broken Dockerfile paths; no OIDC (uses long-lived keys) |
| **AI/LLM Providers** | Groq, Anthropic, OpenAI, Gemini, fal.ai | External (no AWS service) | Yes | N/A | Keys in Secrets Manager; calls go to external APIs |
| **Payments** | Stripe, Razorpay | External (webhooks via ALB) | Yes | N/A | Webhook signature verification already implemented |
| **Email** | Resend + SMTP fallback | External (or Amazon SES) | Yes | N/A | RESEND_API_KEY in Secrets Manager; SES is cheaper alternative |
| **Webhooks** | Stripe, Razorpay, platform adapters | ALB → API (inline processing) | Yes | N/A | HMAC verification implemented; no SQS buffering |
| **SSE / Realtime** | In-memory EventBus, `StreamingResponse` | ALB (sticky sessions or Redis pub/sub) | Yes | Low | Per-process EventBus breaks with >1 API replica; needs Redis pub/sub for multi-replica |
| **Vector / Embeddings** | In-memory VectorStore, JSONB embeddings | RDS pgvector (future) | Optional | Low | Currently uses hash pseudo-embeddings without OpenAI key; pgvector recommended post-launch |
| **GPU Video Gen** | fal.ai (Wan 3.0), external | External (no AWS GPU needed) | Optional | N/A | All video generation via fal.ai API; no GPU instances needed |
| **PgBouncer** | Configured in docker-compose | RDS Proxy or PgBouncer on ECS | Optional | Medium | Already PgBouncer-aware in code; RDS Proxy adds ~$18/mo |

---

## Cost Summary by Tier

| Tier | Monthly Cost | What's Included |
|---|---|---|
| **$25 budget** | ❌ Not achievable on AWS | Single EC2 VM with Docker (~$15-30) or free-tier external services |
| **Dev/Staging (minimal AWS)** | ~$130-160/mo | 1 Fargate task, db.t3.micro single-AZ, cache.t3.micro, ALB, NAT |
| **Small Production** | ~$275-310/mo | 1 API + 1 worker, db.t3.small Multi-AZ, cache.t3.small ×2, ALB, NAT, WAF, CloudFront |
| **Growth Production** | ~$1,220-1,280/mo | 2 API + 2 worker, db.r6g.large Multi-AZ, cache.r6g.large ×3, full WAF, CloudFront |
