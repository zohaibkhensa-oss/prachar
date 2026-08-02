const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = 'http://localhost:3002';
const OUT = '/Users/appple/Projects/prachar/screenshots';

const PAGES = [
  { path: '/', name: 'landing' },
  { path: '/login', name: 'login' },
  { path: '/register', name: 'register' },
  { path: '/onboarding', name: 'onboarding' },
  { path: '/app', name: 'dashboard' },
  { path: '/app/brands', name: 'brands' },
  { path: '/app/campaigns', name: 'campaigns' },
  { path: '/app/channels', name: 'channels' },
  { path: '/app/connections', name: 'connections' },
  { path: '/app/integrations', name: 'integrations' },
  { path: '/app/review', name: 'review' },
  { path: '/app/reviews', name: 'reviews' },
  { path: '/app/reports', name: 'reports' },
  { path: '/app/knowledge', name: 'knowledge' },
  { path: '/app/calendar', name: 'calendar' },
  { path: '/app/settings', name: 'settings' },
  { path: '/app/analytics', name: 'analytics' },
  { path: '/app/performance', name: 'performance' },
  { path: '/app/creative', name: 'creative' },
  { path: '/app/creative-studio', name: 'creative-studio' },
  { path: '/app/video', name: 'video' },
  { path: '/app/images', name: 'images' },
  { path: '/app/design', name: 'design' },
  { path: '/app/audience', name: 'audience' },
  { path: '/app/influencers', name: 'influencers' },
  { path: '/app/advocacy', name: 'advocacy' },
  { path: '/app/marketplace', name: 'marketplace' },
  { path: '/app/shop', name: 'shop' },
  { path: '/app/bio', name: 'bio' },
  { path: '/app/listening', name: 'listening' },
  { path: '/app/timeline', name: 'timeline' },
  { path: '/app/runtime', name: 'runtime' },
  { path: '/app/repurpose', name: 'repurpose' },
  { path: '/app/youtube-plan', name: 'youtube-plan' },
  { path: '/app/pricing', name: 'pricing' },
  { path: '/audit', name: 'audit' },
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  // Login first to get a token
  const loginPage = await context.newPage();
  await loginPage.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await loginPage.waitForTimeout(1000);
  await loginPage.fill('input[type="email"]', 'demo@prachar.app');
  await loginPage.fill('input[type="password"]', 'prachar123');
  await loginPage.click('button[type="submit"]');
  await loginPage.waitForTimeout(3000);

  // Extract the token from localStorage
  const token = await loginPage.evaluate(() => window.localStorage.getItem('prachar_token'));
  console.log('Token:', token ? 'found' : 'NOT FOUND');
  await loginPage.close();

  // Set localStorage on the context so all pages have the token + onboarding flag
  await context.addInitScript(({ t }) => {
    window.localStorage.setItem('prachar_token', t);
    window.localStorage.setItem('prachar_onboarded', 'true');
    window.localStorage.setItem('prachar_email', 'demo@prachar.app');
  }, { t: token });

  const results = [];

  for (const page of PAGES) {
    const p = await context.newPage();
    try {
      // Navigate and wait for DOM content
      await p.goto(`${BASE}${page.path}`, { waitUntil: 'domcontentloaded', timeout: 20000 });

      // Wait for network to settle
      await p.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});

      // Wait for actual text content to appear (not just loading skeleton)
      // The app renders text like "Good evening", "Campaigns", "Channels", etc.
      try {
        await p.waitForFunction(
          () => {
            const text = document.body.innerText;
            // Check if we have real content (not just "PRACHAR AI")
            return text.length > 100 && !text.match(/^PRACHAR AI/);
          },
          { timeout: 10000 }
        );
      } catch {
        // If we can't detect content, just wait a bit more
        await p.waitForTimeout(3000);
      }

      // Extra wait for animations to settle
      await p.waitForTimeout(1500);

      const filename = `${page.name}.png`;
      await p.screenshot({ path: path.join(OUT, filename), fullPage: false });

      // Get page title for verification
      const title = await p.title();
      const bodyText = await p.evaluate(() => document.body.innerText.substring(0, 100));

      results.push({ ...page, status: 'ok', file: filename, title, preview: bodyText });
      console.log(`✅ ${page.name} (${page.path}) — ${bodyText.substring(0, 60)}...`);
    } catch (e) {
      const status = 'error: ' + e.message.substring(0, 80);
      results.push({ ...page, status });
      console.log(`❌ ${page.name} (${page.path}): ${status}`);
    }
    await p.close();
  }

  await browser.close();

  // Write results
  fs.writeFileSync(
    path.join(OUT, 'results.json'),
    JSON.stringify(results, null, 2)
  );
  console.log(`\n${results.length} pages captured → ${OUT}`);
})();
