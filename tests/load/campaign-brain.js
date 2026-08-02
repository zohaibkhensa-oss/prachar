// k6 load test — Campaign Brain concurrent generation
// Target: 200 concurrent generations
// Run: k6 run tests/load/campaign-brain.js --env BASE_URL=https://api.prachar.ai --env AUTH_TOKEN=... --env BRAND_ID=...
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const BRAND_ID = __ENV.BRAND_ID || '';

const brainLatency = new Trend('brain_latency_ms');
const brainSuccess = new Rate('brain_success');

export const options = {
  stages: [
    { duration: '30s', target: 25 },
    { duration: '1m', target: 50 },
    { duration: '2m', target: 100 },
    { duration: '3m', target: 200 },  // target
    { duration: '2m', target: 200 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<30000'],  // AI generation can take up to 30s
    brain_success: ['rate>0.90'],
    http_req_failed: ['rate<0.10'],
  },
};

export default function () {
  const payload = JSON.stringify({
    brand_id: BRAND_ID,
    objective: 'increase_awareness',
    budget_monthly: 50000,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${AUTH_TOKEN}`,
    },
    timeout: '60s',
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/campaign-brain/generate`, payload, params);
  const latency = Date.now() - start;

  brainLatency.add(latency);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has campaign data': (r) => {
      try { return !!r.json('campaign'); } catch { return false; }
    },
  });

  brainSuccess.add(ok);

  sleep(2 + Math.random() * 3); // 2-5s think time
}
