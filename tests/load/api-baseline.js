// k6 load test — API baseline (non-AI endpoints)
// Target: 500 TPS, p99 < 500ms
// Run: k6 run tests/load/api-baseline.js --env BASE_URL=https://api.prachar.ai --env AUTH_TOKEN=...
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

const apiLatency = new Trend('api_latency_ms');
const apiSuccess = new Rate('api_success');

export const options = {
  stages: [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 250 },
    { duration: '2m', target: 500 },
    { duration: '2m', target: 500 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<500'],
    api_success: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
  },
};

const ENDPOINTS = [
  { method: 'GET', path: '/brands' },
  { method: 'GET', path: '/campaigns' },
  { method: 'GET', path: '/reports' },
  { method: 'GET', path: '/knowledge/sources' },
  { method: 'GET', path: '/connections' },
  { method: 'GET', path: '/review' },
  { method: 'GET', path: '/billing/subscription' },
  { method: 'GET', path: '/health/ready' },
];

export default function () {
  const endpoint = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];

  const params = {
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
    },
    timeout: '10s',
  };

  const start = Date.now();
  const res = http.request(endpoint.method, `${BASE_URL}${endpoint.path}`, null, params);
  const latency = Date.now() - start;

  apiLatency.add(latency);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  apiSuccess.add(ok);

  sleep(0.1 + Math.random() * 0.2); // 100-300ms between requests
}
