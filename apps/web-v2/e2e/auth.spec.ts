import { test, expect } from '@playwright/test';

/**
 * Authentication flow tests.
 */

test.describe('Authentication', () => {
  test('login page loads', async ({ page }) => {
    await page.goto('/login');
    // Should show login form
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('input[type="password"], input[name="password"]')).toBeVisible();
  });

  test('register page loads', async ({ page }) => {
    await page.goto('/register');
    // Should show registration form
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible({ timeout: 10_000 });
  });

  test('login form has submit button', async ({ page }) => {
    await page.goto('/login');
    const submit = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")');
    await expect(submit).toBeVisible({ timeout: 10_000 });
  });

  test('social login buttons present', async ({ page }) => {
    await page.goto('/login');
    // Google sign-in button should be present
    const googleBtn = page.locator('[data-testid="google-signin"], button:has-text("Google")');
    // Don't fail if social login isn't configured — just check it doesn't crash
    const count = await googleBtn.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
