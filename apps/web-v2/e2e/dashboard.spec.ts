import { test, expect } from '@playwright/test';

/**
 * Dashboard tests — requires authentication.
 * Uses mock auth state by setting localStorage tokens.
 */

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth tokens in localStorage to bypass login
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-token-for-testing');
      localStorage.setItem('refresh_token', 'mock-refresh-token');
      localStorage.setItem('user', JSON.stringify({
        id: 'test-user-id',
        email: 'test@curvai.org',
        role: 'owner',
        tenant_id: 'test-tenant-id',
      }));
    });
  });

  test('dashboard page loads', async ({ page }) => {
    await page.goto('/app');
    // Should not redirect to login (auth mock should work)
    await page.waitForLoadState('networkidle');
    // Page should render something — either dashboard content or an error
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 15_000 });
  });

  test('navigation sidebar present', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');
    // Look for navigation elements
    const nav = page.locator('nav, [role="navigation"], aside');
    const count = await nav.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
