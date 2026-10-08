import { test, expect } from '@playwright/test';

/**
 * Mobile/responsive tests — verify the app works on mobile viewport.
 */

test.describe('Mobile responsive', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('login page is responsive', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible({ timeout: 10_000 });
    // No horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5); // 5px tolerance
  });

  test('app page is responsive', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-token');
      localStorage.setItem('user', JSON.stringify({
        id: 'test', email: 'test@curvai.org', role: 'owner', tenant_id: 'test',
      }));
    });
    await page.goto('/app');
    await page.waitForLoadState('networkidle');
    // No horizontal scroll on mobile
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5);
  });
});
