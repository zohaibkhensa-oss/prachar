import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for CURV AI web-v2.
 *
 * Tests run against a local dev server (http://localhost:3002) by default.
 * Set BASE_URL env to test against a deployed environment.
 *
 * Run: pnpm exec playwright test
 * UI:  pnpm exec playwright test --ui
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3002',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: process.env.CI ? undefined : {
    command: 'pnpm dev',
    url: 'http://localhost:3002',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
