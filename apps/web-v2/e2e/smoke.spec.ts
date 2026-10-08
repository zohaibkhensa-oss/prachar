import { test, expect } from '@playwright/test';

/**
 * Smoke tests — verify all major routes load without crashing.
 * Based on the e2e-audit.mjs script.
 */

const ROUTES = [
  '/',
  '/login',
  '/register',
  '/app',
  '/onboarding',
];

test.describe('Route smoke tests', () => {
  for (const route of ROUTES) {
    test(`${route} loads without error`, async ({ page }) => {
      const errors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') errors.push(msg.text());
      });
      page.on('pageerror', err => errors.push(err.message));

      await page.goto(route);
      await page.waitForLoadState('networkidle');

      // Page should not be blank
      const bodyText = await page.locator('body').innerText();
      expect(bodyText.length).toBeGreaterThan(0);

      // Filter out expected errors (API connection failures in test env)
      const criticalErrors = errors.filter(e =>
        !e.includes('fetch') &&
        !e.includes('NetworkError') &&
        !e.includes('Failed to fetch') &&
        !e.includes('ECONNREFUSED')
      );
      expect(criticalErrors).toEqual([]);
    });
  }
});
