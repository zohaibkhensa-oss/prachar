# Load Testing

k6 load tests for PRACHAR AI.

## Prerequisites

```bash
# Install k6
brew install k6  # macOS
# or: https://k6.io/docs/getting-started/installation/

# Get an auth token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@prachar.app","password":"prachar123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get a brand ID
BRAND=$(curl -s http://localhost:8000/brands \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
```

## Running Tests

### Orb concurrent chat (target: 500 concurrent)

```bash
k6 run tests/load/orb-chat.js \
  --env BASE_URL=http://localhost:8000 \
  --env AUTH_TOKEN=$TOKEN \
  --env BRAND_ID=$BRAND
```

### API baseline (target: 500 TPS, p99 < 500ms)

```bash
k6 run tests/load/api-baseline.js \
  --env BASE_URL=http://localhost:8000 \
  --env AUTH_TOKEN=$TOKEN
```

### Campaign Brain (target: 200 concurrent generations)

```bash
k6 run tests/load/campaign-brain.js \
  --env BASE_URL=http://localhost:8000 \
  --env AUTH_TOKEN=$TOKEN \
  --env BRAND_ID=$BRAND
```

## Targets (from LAUNCH_PROGRAM.md Phase B)

| Subsystem | Target | Test |
|-----------|--------|------|
| Orb (concurrent chats) | 500 | orb-chat.js |
| Campaign Brain (concurrent) | 200 | campaign-brain.js |
| API (TPS) | 500 | api-baseline.js |
| Context Builder (latency) | <100ms | measured via /metrics |
| Runtime (response time) | <2s avg | measured via orb-chat.js |

## Interpreting Results

k6 outputs:
- `http_req_duration` — latency percentiles (p50, p90, p95, p99)
- `http_req_failed` — error rate
- `orb_success` / `api_success` / `brain_success` — custom success rates
- `vus` — virtual users
- `iterations` — total requests made

If thresholds fail, k6 exits with non-zero code (useful for CI).
