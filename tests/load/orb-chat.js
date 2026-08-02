// k6 load test — Orb concurrent chat
// Target: 500 concurrent chats
// Run: k6 run tests/load/orb-chat.js --env BASE_URL=https://api.prachar.ai --env AUTH_TOKEN=...
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const BRAND_ID = __ENV.BRAND_ID || '';

const orbLatency = new Trend('orb_latency_ms');
const orbSuccess = new Rate('orb_success');

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // ramp up to 50 VUs
    { duration: '1m', target: 100 },   // ramp up to 100 VUs
    { duration: '2m', target: 250 },   // ramp up to 250 VUs
    { duration: '3m', target: 500 },   // ramp up to 500 VUs (target)
    { duration: '2m', target: 500 },   // hold at 500 VUs
    { duration: '30s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(99)<5000'],  // 99% of requests < 5s
    orb_success: ['rate>0.95'],          // 95% success rate
    http_req_failed: ['rate<0.05'],      // <5% errors
  },
};

const MESSAGES = [
  'How are my campaigns performing?',
  'Show me my latest report',
  'What plan am I on?',
  'Generate a video for my brand',
  'Show me recent creatives',
  'What are my top opportunities?',
  'Run an audit on my website',
  'What did you do this week?',
];

export default function () {
  const msg = MESSAGES[Math.floor(Math.random() * MESSAGES.length)];

  const payload = JSON.stringify({
    message: msg,
    brand_id: BRAND_ID,
    mode: 'text',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${AUTH_TOKEN}`,
    },
    timeout: '30s',
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/runtime/invoke`, payload, params);
  const latency = Date.now() - start;

  orbLatency.add(latency);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has session_id': (r) => {
      try { return !!r.json('session_id'); } catch { return false; }
    },
  });

  orbSuccess.add(ok);

  sleep(1 + Math.random() * 2); // 1-3s between requests (think time)
}
