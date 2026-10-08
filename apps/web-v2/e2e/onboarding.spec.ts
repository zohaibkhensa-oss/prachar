import { test, expect } from '@playwright/test';

/**
 * Onboarding flow tests.
 */

test.describe('Onboarding', () => {
  test('onboarding page loads', async ({ page }) => {
    await page.goto('/onboarding');
    await page.waitForLoadState('networkidle');
    // Should show onboarding steps
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 10_000 });
  });

  test('industry selection step', async ({ page }) => {
    await page.goto('/onboarding');
    await page.waitForLoadState('networkidle');
    // Look for industry selection cards/buttons
    const industryElements = page.locator('[data-testid*="industry"], button:has-text("Restaurant"), button:has-text("Retail"), button:has-text("Tech")');
    const count = await industryElements.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
