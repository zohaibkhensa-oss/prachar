import { chromium } from "playwright";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

const BASE = "http://localhost:3000";
const SCREENSHOT_DIR = "./qa-screenshots";

mkdirSync(SCREENSHOT_DIR, { recursive: true });

// All routes from the Next.js build output
const ROUTES = [
  // Auth
  { path: "/login", name: "login", auth: false },
  { path: "/register", name: "register", auth: false },
  { path: "/auth/forgot-password", name: "forgot-password", auth: false },
  { path: "/auth/resend-verification", name: "resend-verification", auth: false },
  { path: "/auth/reset-password", name: "reset-password", auth: false },
  { path: "/auth/verify", name: "verify", auth: false },
  { path: "/onboarding", name: "onboarding", auth: false },
  // Public
  { path: "/privacy", name: "privacy", auth: false },
  { path: "/terms", name: "terms", auth: false },
  { path: "/support", name: "support", auth: false },
  // App (require auth — will redirect to /login if not authenticated)
  { path: "/app", name: "dashboard", auth: true },
  { path: "/app/campaigns", name: "campaigns", auth: true },
  { path: "/app/creative-studio", name: "creative-studio", auth: true },
  { path: "/app/review", name: "review", auth: true },
  { path: "/app/performance", name: "performance", auth: true },
  { path: "/app/timeline", name: "timeline", auth: true },
  { path: "/app/video", name: "video", auth: true },
  { path: "/app/images", name: "images", auth: true },
  { path: "/app/design", name: "design", auth: true },
  { path: "/app/brands", name: "brands", auth: true },
  { path: "/app/channels", name: "channels", auth: true },
  { path: "/app/calendar", name: "calendar", auth: true },
  { path: "/app/reviews", name: "reviews", auth: true },
  { path: "/app/settings", name: "settings", auth: true },
  { path: "/app/knowledge", name: "knowledge", auth: true },
  { path: "/app/integrations", name: "integrations", auth: true },
  { path: "/app/connections", name: "connections", auth: true },
  { path: "/app/reports", name: "reports", auth: true },
  { path: "/app/analytics", name: "analytics", auth: true },
  { path: "/app/creative", name: "creative", auth: true },
  { path: "/app/repurpose", name: "repurpose", auth: true },
  { path: "/app/runtime", name: "runtime", auth: true },
  { path: "/app/pricing", name: "pricing", auth: true },
  { path: "/app/shop", name: "shop", auth: true },
  { path: "/app/bio", name: "bio", auth: true },
  { path: "/app/listening", name: "listening", auth: true },
  { path: "/app/marketplace", name: "marketplace", auth: true },
  { path: "/app/influencers", name: "influencers", auth: true },
  { path: "/app/advocacy", name: "advocacy", auth: true },
  { path: "/app/audience", name: "audience", auth: true },
  { path: "/app/youtube-plan", name: "youtube-plan", auth: true },
];

async function loginIfNeeded(page, route) {
  if (!route.auth) return true;

  // Try to login via API
  try {
    const resp = await page.request.post(`${BASE}/api/auth/login`, {
      data: { email: "demo@prachar.app", password: "prachar123" },
      headers: { "Content-Type": "application/json" },
    });

    if (resp.ok()) {
      const data = await resp.json();
      // Set tokens in localStorage
      await page.evaluate((tokens) => {
        localStorage.setItem("prachar_token", tokens.access_token);
        localStorage.setItem("prachar_email", "demo@prachar.app");
        localStorage.setItem("prachar_onboarded", "1");
        if (tokens.refresh_token) {
          localStorage.setItem("prachar_refresh_token", tokens.refresh_token);
        }
      }, data);
      return true;
    }
  } catch (e) {
    // API might not be available — try localStorage approach
  }

  // Fallback: set localStorage directly (for client-side auth)
  await page.evaluate(() => {
    localStorage.setItem("prachar_token", "demo-token");
    localStorage.setItem("prachar_email", "demo@prachar.app");
    localStorage.setItem("prachar_onboarded", "1");
  });
  return true;
}

async function auditRoute(browser, route) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const networkErrors = [];

  // Collect console errors
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  page.on("pageerror", (err) => {
    pageErrors.push(err.message);
  });

  page.on("requestfailed", (request) => {
    const url = request.url();
    // Ignore favicon, Next.js HMR, and analytics
    if (
      !url.includes("favicon") &&
      !url.includes("_next/webpack-hmr") &&
      !url.includes("google-analytics") &&
      !url.includes("accounts.google.com") &&
      !url.includes("appleid.cdn-apple.com")
    ) {
      networkErrors.push(`${request.method()} ${url} - ${request.failure()?.errorText}`);
    }
  });

  try {
    // Navigate to the route
    await page.goto(`${BASE}${route.path}`, {
      waitUntil: "networkidle",
      timeout: 15000,
    });

    // Wait for page to settle
    await page.waitForTimeout(1500);

    // Login if needed (set localStorage, then reload)
    if (route.auth) {
      await loginIfNeeded(page, route);
      await page.goto(`${BASE}${route.path}`, {
        waitUntil: "networkidle",
        timeout: 15000,
      });
      await page.waitForTimeout(1500);
    }

    // Check for horizontal overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    const hasOverflow = scrollWidth > clientWidth + 5;

    // Check for visible text content
    const bodyText = await page.evaluate(() => document.body?.innerText?.slice(0, 200) || "");
    const hasContent = bodyText.length > 10;

    // Check for yellow theme remnants (check computed styles)
    const yellowCheck = await page.evaluate(() => {
      const elements = document.querySelectorAll("*");
      let yellowFound = false;
      for (let i = 0; i < Math.min(elements.length, 200); i++) {
        const el = elements[i];
        const styles = window.getComputedStyle(el);
        const color = styles.color;
        const bg = styles.backgroundColor;
        // Check for #FFD400 or rgb(255, 212, 0)
        if (
          color.includes("255, 212, 0") ||
          bg.includes("255, 212, 0") ||
          color === "rgb(255, 212, 0)" ||
          bg === "rgb(255, 212, 0)"
        ) {
          yellowFound = true;
          break;
        }
      }
      return yellowFound;
    });

    // Take desktop screenshot
    await page.screenshot({
      path: join(SCREENSHOT_DIR, `${route.name}-desktop.png`),
      fullPage: false,
    });

    // Mobile screenshot
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    await page.screenshot({
      path: join(SCREENSHOT_DIR, `${route.name}-mobile.png`),
      fullPage: false,
    });

    // Check mobile overflow
    const mobileScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const mobileClientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    const hasMobileOverflow = mobileScrollWidth > mobileClientWidth + 5;

    // Count buttons
    const buttonCount = await page.locator("button, a[role='button'], a.btn-primary, .btn-primary").count();

    const status = consoleErrors.length === 0 && pageErrors.length === 0 && hasContent ? "PASS" : "FAIL";

    const result = {
      route: route.path,
      name: route.name,
      status,
      hasContent,
      hasOverflow,
      hasMobileOverflow,
      yellowRemnant: yellowCheck,
      buttonCount,
      consoleErrors: consoleErrors.slice(0, 3),
      pageErrors: pageErrors.slice(0, 2),
      networkErrors: networkErrors.slice(0, 3),
    };

    console.log(
      `[${status}] ${route.name.padEnd(20)} buttons=${String(buttonCount).padStart(3)} ` +
        `overflow=${hasOverflow ? "Y" : "N"} mobileOverflow=${hasMobileOverflow ? "Y" : "N"} ` +
        `yellow=${yellowCheck ? "Y" : "N"} ` +
        `errors=${consoleErrors.length + pageErrors.length}`,
    );

    return result;
  } catch (err) {
    console.log(`[ERROR] ${route.name.padEnd(20)} ${err.message.slice(0, 80)}`);
    return {
      route: route.path,
      name: route.name,
      status: "ERROR",
      error: err.message,
    };
  } finally {
    await context.close();
  }
}

async function main() {
  console.log("PRACHAR AI — Playwright QA Audit");
  console.log("=" .repeat(60));
  console.log(`Auditing ${ROUTES.length} routes...\n`);

  const browser = await chromium.launch({ headless: true });

  const results = [];
  for (const route of ROUTES) {
    const result = await auditRoute(browser, route);
    results.push(result);
  }

  await browser.close();

  // Summary
  const passed = results.filter((r) => r.status === "PASS").length;
  const failed = results.filter((r) => r.status === "FAIL").length;
  const errored = results.filter((r) => r.status === "ERROR").length;
  const totalButtons = results.reduce((sum, r) => sum + (r.buttonCount || 0), 0);
  const overflowIssues = results.filter((r) => r.hasOverflow).length;
  const mobileOverflowIssues = results.filter((r) => r.hasMobileOverflow).length;
  const yellowRemnants = results.filter((r) => r.yellowRemnant).length;

  console.log("\n" + "=" .repeat(60));
  console.log("SUMMARY");
  console.log("=" .repeat(60));
  console.log(`Routes audited:     ${results.length}`);
  console.log(`Passed:             ${passed}`);
  console.log(`Failed:             ${failed}`);
  console.log(`Errored:            ${errored}`);
  console.log(`Total buttons:      ${totalButtons}`);
  console.log(`Desktop overflow:   ${overflowIssues}`);
  console.log(`Mobile overflow:    ${mobileOverflowIssues}`);
  console.log(`Yellow remnants:    ${yellowRemnants}`);
  console.log(`\nScreenshots saved to: ${SCREENSHOT_DIR}/`);

  // Save results as JSON
  writeFileSync(
    join(SCREENSHOT_DIR, "audit-results.json"),
    JSON.stringify(results, null, 2),
  );

  // List failures
  if (failed > 0 || errored > 0) {
    console.log("\n--- FAILURES ---");
    results
      .filter((r) => r.status !== "PASS")
      .forEach((r) => {
        console.log(`  ${r.name}: ${r.error || r.consoleErrors?.join("; ") || r.pageErrors?.join("; ")}`);
      });
  }

  process.exit(0);
}

main().catch(console.error);
