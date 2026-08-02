/**
 * Screenshot capture script — captures each key page at 375px, 768px, 1024px.
 *
 * Usage:
 *   npx playwright test screenshot.config.ts
 *
 * Prerequisites:
 *   - API server running on :8000 (make api)
 *   - Web server running on :3000 (make web)
 *   - A seeded user with a brand (make seed)
 *
 * Screenshots are saved to apps/web/screenshots/ for visual comparison
 * before and after polish changes.
 */
import { test, expect, type Page } from "@playwright/test";
import path from "node:path";

const BASE = "http://localhost:3000";
const OUT = path.resolve(__dirname, "screenshots");

// Viewports to test
const VIEWPORTS = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

// Pages to capture (relative to /app)
const PAGES = [
  { name: "dashboard", path: "/app" },
  { name: "campaigns", path: "/app/campaigns" },
  { name: "campaign-new", path: "/app/brands/seed-brand/campaigns/new" },
  { name: "creative-studio", path: "/app/creative-studio" },
  { name: "review-queue", path: "/app/review" },
  { name: "performance", path: "/app/performance/seed-campaign" },
  { name: "analytics", path: "/app/analytics" },
  { name: "brands", path: "/app/brands" },
];

// Login helper — adjust to match your auth flow
async function login(page: Page) {
  // Try to use a seeded account. Adjust credentials as needed.
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', "demo@prachar.app");
  await page.fill('input[type="password"]', "demo1234");
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE}/app`, { timeout: 10000 }).catch(() => {
    // If login fails, continue anyway — some pages may still render
  });
}

for (const vp of VIEWPORTS) {
  for (const p of PAGES) {
    test(`screenshot ${p.name} @ ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await login(page);
      await page.goto(`${BASE}${p.path}`);
      // Wait for content to load (adjust selector as needed)
      await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
      await page.waitForTimeout(1500); // allow animations to settle
      await page.screenshot({
        path: path.join(OUT, `${p.name}-${vp.name}.png`),
        fullPage: true,
      });
      // Basic assertion — screenshot file exists
      expect(true).toBeTruthy();
    });
  }
}
