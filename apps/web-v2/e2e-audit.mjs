import { chromium } from "playwright";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

const BASE = "http://localhost:3000";
const API_BASE = "http://localhost:8000";
const SHOTS = "./e2e-screenshots";
mkdirSync(SHOTS, { recursive: true });

const results = [];
const bugs = [];

function log(msg) { console.log(msg); }
function bug(phase, description, severity = "medium") {
  bugs.push({ phase, description, severity });
  console.log(`  🐛 BUG [${severity}]: ${description}`);
}
function pass(msg) { console.log(`  ✅ ${msg}`); }
function fail(msg) { console.log(`  ❌ ${msg}`); }
function info(msg) { console.log(`  ℹ️  ${msg}`); }

async function screenshot(page, name) {
  await page.screenshot({ path: join(SHOTS, `${name}.png`) });
}

// ─── Helper: Login via API and set tokens ───
async function loginAndSetTokens(page, email = "demo@prachar.app", password = "prachar123") {
  const resp = await page.request.post(`${API_BASE}/auth/login`, {
    data: { email, password },
    headers: { "Content-Type": "application/json" },
  });
  if (!resp.ok()) {
    fail(`Login API failed: ${resp.status()}`);
    return null;
  }
  const data = await resp.json();
  await page.evaluate((tokens) => {
    localStorage.setItem("prachar_token", tokens.access_token);
    localStorage.setItem("prachar_email", "demo@prachar.app");
    localStorage.setItem("prachar_onboarded", "1");
    localStorage.setItem("prachar_password", "prachar123");
    if (tokens.refresh_token) localStorage.setItem("prachar_refresh_token", tokens.refresh_token);
  }, data);
  return data;
}

// ─── Helper: Navigate with auth ───
async function authedGoto(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);
}

async function main() {
  log("\n" + "=".repeat(70));
  log("PRACHAR AI — END-TO-END AUDIT");
  log("=".repeat(70) + "\n");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console errors globally
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (err) => pageErrors.push(err.message));

  // ═══════════════════════════════════════════════════════════════
  // PHASE B: AUTH FLOW
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE B: AUTH FLOW ──");

  // B1: Login page loads
  log("\nB1: Login page loads");
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  const loginForm = await page.locator('input[type="email"]').count();
  const loginBtn = await page.locator('button[type="submit"]').count();
  if (loginForm > 0 && loginBtn > 0) pass("Login form rendered with email input + submit button");
  else bug("B1", "Login form missing email input or submit button", "high");
  await screenshot(page, "B1-login-page");

  // B2: Login with demo credentials
  log("\nB2: Login with demo credentials");
  await page.fill('input[type="email"]', "demo@prachar.app");
  await page.fill('input[type="password"]', "prachar123");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);
  const afterLoginUrl = page.url();
  if (afterLoginUrl.includes("/app") || afterLoginUrl.includes("/onboarding")) {
    pass(`Login redirected to ${afterLoginUrl}`);
  } else {
    bug("B2", `Login did not redirect to /app or /onboarding, stayed at ${afterLoginUrl}`, "high");
  }
  await screenshot(page, "B2-after-login");

  // B3: Verify token is stored
  log("\nB3: Verify token stored in localStorage");
  const hasToken = await page.evaluate(() => !!localStorage.getItem("prachar_token"));
  if (hasToken) pass("Token stored in localStorage");
  else bug("B3", "No token in localStorage after login", "high");

  // B4: Session persistence — reload page
  log("\nB4: Session persistence (reload)");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const afterReloadUrl = page.url();
  if (afterReloadUrl.includes("/app") || afterReloadUrl.includes("/onboarding")) {
    pass(`Session persisted, stayed at ${afterReloadUrl}`);
  } else {
    bug("B4", `Session lost after reload, redirected to ${afterReloadUrl}`, "medium");
  }

  // B5: Logout
  log("\nB5: Logout flow");
  // Look for logout button in sidebar (may need to expand sidebar first)
  const logoutBtn = page.locator('button:has-text("Logout"), button[title="Logout"]').first();
  if (await logoutBtn.count() > 0) {
    await logoutBtn.click();
    await page.waitForTimeout(2000);
    const afterLogoutUrl = page.url();
    if (afterLogoutUrl.includes("/login")) pass("Logout redirected to /login");
    else bug("B5", `Logout did not redirect to /login, at ${afterLogoutUrl}`, "medium");
  } else {
    info("Logout button not found (sidebar may be collapsed) — testing via API");
    // Clear tokens manually
    await page.evaluate(() => {
      localStorage.removeItem("prachar_token");
      localStorage.removeItem("prachar_refresh_token");
      localStorage.removeItem("prachar_email");
      localStorage.removeItem("prachar_onboarded");
    });
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    const afterClearUrl = page.url();
    if (afterClearUrl.includes("/login")) pass("Token removal redirects to /login");
    else bug("B5", `Token removal did not redirect to /login, at ${afterClearUrl}`, "medium");
  }

  // B6: Login again for subsequent tests
  log("\nB6: Re-login for subsequent tests");
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "demo@prachar.app");
  await page.fill('input[type="password"]', "prachar123");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  // B7: Register page loads
  log("\nB7: Register page loads");
  const registerPage = await browser.newPage();
  await registerPage.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await registerPage.waitForTimeout(1000);
  const regInputs = await registerPage.locator('input').count();
  if (regInputs >= 3) pass(`Register form has ${regInputs} inputs (name, email, password)`);
  else bug("B7", `Register form only has ${regInputs} inputs, expected 3+`, "medium");
  await screenshot(registerPage, "B7-register-page");
  await registerPage.close();

  // B8: Forgot password page
  log("\nB8: Forgot password page");
  const forgotPage = await browser.newPage();
  await forgotPage.goto(`${BASE}/auth/forgot-password`, { waitUntil: "networkidle" });
  await forgotPage.waitForTimeout(500);
  const forgotInput = await forgotPage.locator('input[type="email"]').count();
  if (forgotInput > 0) pass("Forgot password page has email input");
  else bug("B8", "Forgot password page missing email input", "medium");
  await forgotPage.close();

  results.push({ phase: "B", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE C: ONBOARDING (skip if already onboarded)
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE C: ONBOARDING ──");

  // Check if demo user has brands
  const token = await page.evaluate(() => localStorage.getItem("prachar_token"));
  const brandsResp = await page.request.get(`${API_BASE}/brands`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  let brandCount = 0;
  if (brandsResp.ok()) {
    const brandsData = await brandsResp.json();
    brandCount = Array.isArray(brandsData) ? brandsData.length : (brandsData.items?.length || 0);
  }
  info(`Demo user has ${brandCount} brand(s)`);

  if (brandCount === 0) {
    log("Testing onboarding flow (no brands yet)...");
    // This would require going through the full onboarding flow
    // For now, just verify the page loads
    const onboardingPage = await browser.newPage();
    await onboardingPage.goto(`${BASE}/onboarding`, { waitUntil: "networkidle" });
    await onboardingPage.waitForTimeout(1000);
    const onboardingContent = await onboardingPage.locator("text=/business|creator|industry/i").count();
    if (onboardingContent > 0) pass("Onboarding page renders with business/creator options");
    else bug("C", "Onboarding page missing business/creator options", "medium");
    await onboardingPage.close();
  } else {
    pass("Demo user already has brands — onboarding already completed");
  }
  results.push({ phase: "C", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE D: DASHBOARD
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE D: DASHBOARD ──");

  await authedGoto(page, "/app");
  await screenshot(page, "D-dashboard");

  // D1: Dashboard has content
  log("\nD1: Dashboard content check");
  const dashText = await page.locator("h1, h2, h3").first().textContent();
  if (dashText) pass(`Dashboard has heading: "${dashText.slice(0, 40)}"`);
  else bug("D1", "Dashboard has no headings", "medium");

  // D2: AI Orb is present
  log("\nD2: AI Orb presence");
  const orbButton = page.locator('[aria-label*="PRACHAR"], [aria-label*="chat"], [aria-label*="Chat"]').first();
  if (await orbButton.count() > 0) {
    pass("AI Orb button found in dock");
  } else {
    // Check for the orb by other means
    const orbElement = await page.locator(".fixed.bottom-0 button").count();
    if (orbElement > 0) pass("Orb button found in bottom dock");
    else bug("D2", "AI Orb button not found", "medium");
  }

  // D3: Click orb to open panel
  log("\nD3: Open AI Orb panel");
  try {
    const dockButton = page.locator(".fixed.bottom-0 button").first();
    if (await dockButton.count() > 0) {
      await dockButton.click();
      await page.waitForTimeout(1500);
      const orbPanel = await page.locator("[class*='glass'], [class*='panel']").count();
      if (orbPanel > 0) pass("Orb panel opened");
      else info("Orb panel may have opened but not detected by selector");
      await screenshot(page, "D3-orb-panel");
      // Close it
      await page.keyboard.press("Escape");
      await page.waitForTimeout(500);
    }
  } catch (e) {
    info(`Orb interaction: ${e.message.slice(0, 60)}`);
  }

  // D4: Navigation links work
  log("\nD4: Navigation links");
  const navLinks = await page.locator("nav a, aside a").count();
  if (navLinks > 0) pass(`${navLinks} navigation links found`);
  else bug("D4", "No navigation links found", "medium");

  results.push({ phase: "D", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE E: CAMPAIGNS
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE E: CAMPAIGNS ──");

  await authedGoto(page, "/app/campaigns");
  await screenshot(page, "E-campaigns");
  const campaignsText = await page.locator("h1, h2").first().textContent();
  if (campaignsText) pass(`Campaigns page loaded: "${campaignsText?.slice(0, 40)}"`);
  else bug("E", "Campaigns page has no heading", "low");

  // Check for "Create Campaign" button
  const createBtn = page.locator('a:has-text("Create"), a:has-text("New Campaign"), button:has-text("Create")').first();
  if (await createBtn.count() > 0) {
    pass("Create Campaign button found");
    await createBtn.click();
    await page.waitForTimeout(2000);
    await screenshot(page, "E-create-campaign");
    const createPageUrl = page.url();
    if (createPageUrl.includes("/new") || createPageUrl.includes("/create")) {
      pass(`Navigated to campaign creation: ${createPageUrl}`);
    } else {
      info(`Create button navigated to: ${createPageUrl}`);
    }
  } else {
    info("No Create Campaign button found (may need brand selection first)");
  }

  results.push({ phase: "E", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE F: CREATIVE STUDIO
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE F: CREATIVE STUDIO ──");

  await authedGoto(page, "/app/creative-studio");
  await screenshot(page, "F-creative-studio");
  const csText = await page.locator("h1, h2, label").first().textContent();
  if (csText) pass(`Creative Studio loaded: "${csText?.slice(0, 40)}"`);
  else bug("F", "Creative Studio page has no content", "low");

  // Check for prompt textarea
  const promptArea = page.locator("textarea").first();
  if (await promptArea.count() > 0) pass("Prompt textarea found");
  else info("No textarea found (may need campaign selection first)");

  results.push({ phase: "F", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE G: PERFORMANCE
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE G: PERFORMANCE ──");

  await authedGoto(page, "/app/performance");
  await screenshot(page, "G-performance");
  const perfText = await page.locator("h1, h2").first().textContent();
  if (perfText) pass(`Performance page loaded: "${perfText?.slice(0, 40)}"`);
  else bug("G", "Performance page has no heading", "low");

  // Check for empty state or data
  const hasEmptyState = await page.locator("text=/no data|no campaigns|empty|get started/i").count();
  const hasData = await page.locator("table, .recharts-wrapper, [class*='metric']").count();
  if (hasEmptyState > 0) info("Performance page shows empty state");
  else if (hasData > 0) pass("Performance page shows data/metrics");
  else info("Performance page state unclear");

  results.push({ phase: "G", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE H: KNOWLEDGE HUB
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE H: KNOWLEDGE HUB ──");

  await authedGoto(page, "/app/knowledge");
  await screenshot(page, "H-knowledge");
  const knowledgeText = await page.locator("h1, h2").first().textContent();
  if (knowledgeText) pass(`Knowledge Hub loaded: "${knowledgeText?.slice(0, 40)}"`);
  else bug("H", "Knowledge page has no heading", "low");

  // Check for upload/add button
  const addBtn = page.locator('button:has-text("Add"), button:has-text("Upload"), button:has-text("Source"), a:has-text("Add")').first();
  if (await addBtn.count() > 0) pass("Add/Upload source button found");
  else info("No Add/Upload button found");

  results.push({ phase: "H", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE I: INTEGRATIONS
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE I: INTEGRATIONS ──");

  await authedGoto(page, "/app/integrations");
  await screenshot(page, "I-integrations");
  const intText = await page.locator("h1, h2").first().textContent();
  if (intText) pass(`Integrations page loaded: "${intText?.slice(0, 40)}"`);
  else bug("I", "Integrations page has no heading", "low");

  // Check for integration cards
  const intCards = await page.locator("[class*='card'], [class*='integration']").count();
  if (intCards > 0) pass(`${intCards} integration cards/items found`);
  else info("No integration cards found");

  // Also check connections page
  await authedGoto(page, "/app/connections");
  await screenshot(page, "I-connections");
  const connText = await page.locator("h1, h2").first().textContent();
  if (connText) pass(`Connections page loaded: "${connText?.slice(0, 40)}"`);
  else bug("I", "Connections page has no heading", "low");

  results.push({ phase: "I", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE J: SETTINGS + BILLING
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE J: SETTINGS + BILLING ──");

  await authedGoto(page, "/app/settings");
  await screenshot(page, "J-settings");

  // J1: Profile tab
  log("\nJ1: Profile tab");
  const profileText = await page.locator("text=/profile|email|account/i").first().textContent();
  if (profileText) pass(`Profile section found: "${profileText?.slice(0, 30)}"`);
  else bug("J1", "Profile section not found", "medium");

  // J2: Billing tab
  log("\nJ2: Billing tab");
  const billingTab = page.locator('button:has-text("Billing"), [role="tab"]:has-text("Billing")').first();
  if (await billingTab.count() > 0) {
    await billingTab.click();
    await page.waitForTimeout(1500);
    await screenshot(page, "J2-billing");
    const billingText = await page.locator("text=/plan|subscription|invoice|billing/i").count();
    if (billingText > 0) pass(`Billing tab shows ${billingText} billing-related elements`);
    else bug("J2", "Billing tab clicked but no billing content found", "medium");
  } else {
    info("Billing tab not found — checking if billing content is on page");
    const billingContent = await page.locator("text=/plan|subscription|invoice/i").count();
    if (billingContent > 0) pass("Billing content found on settings page");
    else bug("J2", "No billing tab or billing content found", "medium");
  }

  // J3: API tokens tab
  log("\nJ3: API Access tab");
  const apiTab = page.locator('button:has-text("API"), [role="tab"]:has-text("API")').first();
  if (await apiTab.count() > 0) {
    await apiTab.click();
    await page.waitForTimeout(1000);
    pass("API Access tab found and clickable");
  } else {
    info("API Access tab not found (may require Agency plan)");
  }

  // J4: Notifications tab
  log("\nJ4: Notifications tab");
  const notifTab = page.locator('button:has-text("Notification"), [role="tab"]:has-text("Notification")').first();
  if (await notifTab.count() > 0) {
    await notifTab.click();
    await page.waitForTimeout(1000);
    pass("Notifications tab found and clickable");
  } else {
    info("Notifications tab not found");
  }

  results.push({ phase: "J", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE K: TIMELINE + REVIEWS
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE K: TIMELINE + REVIEWS ──");

  await authedGoto(page, "/app/timeline");
  await screenshot(page, "K-timeline");
  const timelineText = await page.locator("h1, h2").first().textContent();
  if (timelineText) pass(`Timeline page loaded: "${timelineText?.slice(0, 40)}"`);
  else bug("K", "Timeline page has no heading", "low");

  await authedGoto(page, "/app/reviews");
  await screenshot(page, "K-reviews");
  const reviewsText = await page.locator("h1, h2").first().textContent();
  if (reviewsText) pass(`Reviews page loaded: "${reviewsText?.slice(0, 40)}"`);
  else bug("K", "Reviews page has no heading", "low");

  await authedGoto(page, "/app/review");
  await screenshot(page, "K-review-queue");
  const reviewText = await page.locator("h1, h2").first().textContent();
  if (reviewText) pass(`Review queue loaded: "${reviewText?.slice(0, 40)}"`);
  else bug("K", "Review queue page has no heading", "low");

  results.push({ phase: "K", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // PHASE L: LABS PAGES
  // ═══════════════════════════════════════════════════════════════
  log("\n── PHASE L: LABS PAGES ──");

  const labsPages = [
    { path: "/app/video", name: "AI Video" },
    { path: "/app/images", name: "AI Images" },
    { path: "/app/design", name: "Design AI" },
    { path: "/app/influencers", name: "Influencers" },
    { path: "/app/marketplace", name: "Marketplace" },
    { path: "/app/shop", name: "E-Commerce" },
    { path: "/app/bio", name: "Link-in-Bio" },
    { path: "/app/listening", name: "Social Listening" },
    { path: "/app/advocacy", name: "Employee Advocacy" },
    { path: "/app/audience", name: "Audience Builder" },
    { path: "/app/repurpose", name: "Repurpose" },
    { path: "/app/youtube-plan", name: "YouTube Plan" },
    { path: "/app/pricing", name: "Pricing" },
    { path: "/app/analytics", name: "Analytics" },
    { path: "/app/reports", name: "Reports" },
    { path: "/app/brands", name: "Brands" },
    { path: "/app/channels", name: "Channels" },
    { path: "/app/calendar", name: "Calendar" },
    { path: "/app/runtime", name: "Runtime" },
  ];

  let labsPassed = 0;
  for (const lab of labsPages) {
    await authedGoto(page, lab.path);
    const hasContent = await page.locator("h1, h2, h3, p").first().count();
    const hasComingSoon = await page.locator("text=/coming|upcoming|in development/i").count();
    if (hasContent > 0) {
      pass(`${lab.name} page loaded`);
      labsPassed++;
    } else {
      bug("L", `${lab.name} page has no content`, "low");
    }
    if (hasComingSoon > 0) info(`  ${lab.name} shows "coming soon" state (honest disabled)`);
  }
  info(`Labs pages: ${labsPassed}/${labsPages.length} loaded with content`);

  results.push({ phase: "L", status: "done" });

  // ═══════════════════════════════════════════════════════════════
  // API ENDPOINT AUDIT
  // ═══════════════════════════════════════════════════════════════
  log("\n── API ENDPOINT AUDIT ──");

  const apiEndpoints = [
    { method: "GET", path: "/health", auth: false, expect: 200 },
    { method: "GET", path: "/auth/me", auth: true, expect: 200 },
    { method: "GET", path: "/brands", auth: true, expect: 200 },
    { method: "GET", path: "/campaigns", auth: true, expect: 200 },
    { method: "GET", path: "/billing/subscription", auth: true, expect: [200, 404] },
    { method: "GET", path: "/billing/invoices", auth: true, expect: [200, 404] },
    { method: "GET", path: "/billing/plans", auth: true, expect: 200 },
    { method: "GET", path: "/knowledge/sources", auth: true, expect: [200, 404] },
    { method: "GET", path: "/integrations", auth: true, expect: 200 },
    { method: "GET", path: "/connections", auth: true, expect: 200 },
    { method: "GET", path: "/performance/summary", auth: true, expect: [200, 404] },
    { method: "GET", path: "/review/queue", auth: true, expect: [200, 404] },
    { method: "GET", path: "/proactive/messages", auth: true, expect: [200, 404] },
    { method: "GET", path: "/timeline", auth: true, expect: [200, 404] },
  ];

  let apiPassed = 0;
  let apiFailed = 0;
  for (const ep of apiEndpoints) {
    try {
      const headers = ep.auth ? { Authorization: `Bearer ${token}` } : {};
      const resp = await page.request.fetch(`${API_BASE}${ep.path}`, { method: ep.method, headers });
      const expected = Array.isArray(ep.expect) ? ep.expect : [ep.expect];
      if (expected.includes(resp.status())) {
        pass(`${ep.method} ${ep.path} → ${resp.status()}`);
        apiPassed++;
      } else {
        bug("API", `${ep.method} ${ep.path} → ${resp.status()} (expected ${expected.join("/")})`, "medium");
        apiFailed++;
      }
      // Delay to avoid rate limiting (300 req/min limit = 5 req/s)
      await page.waitForTimeout(300);
    } catch (e) {
      bug("API", `${ep.method} ${ep.path} → error: ${e.message.slice(0, 50)}`, "high");
      apiFailed++;
    }
  }
  info(`API endpoints: ${apiPassed} passed, ${apiFailed} failed`);

  // ═══════════════════════════════════════════════════════════════
  // SUMMARY
  // ═══════════════════════════════════════════════════════════════
  log("\n" + "=".repeat(70));
  log("AUDIT SUMMARY");
  log("=".repeat(70));
  log(`\nPhases completed: ${results.length}`);
  log(`Bugs found: ${bugs.length}`);
  log(`Console errors: ${consoleErrors.length}`);
  log(`Page errors: ${pageErrors.length}`);
  log(`API endpoints: ${apiPassed} passed, ${apiFailed} failed`);

  if (bugs.length > 0) {
    log("\n--- BUGS ---");
    bugs.forEach((b, i) => {
      log(`  ${i + 1}. [${b.severity}] ${b.phase}: ${b.description}`);
    });
  }

  if (consoleErrors.length > 0) {
    log("\n--- CONSOLE ERRORS (unique) ---");
    const unique = [...new Set(consoleErrors)].slice(0, 10);
    unique.forEach(e => log(`  - ${e.slice(0, 100)}`));
  }

  if (pageErrors.length > 0) {
    log("\n--- PAGE ERRORS ---");
    pageErrors.forEach(e => log(`  - ${e.slice(0, 100)}`));
  }

  // Save results
  writeFileSync(join(SHOTS, "e2e-results.json"), JSON.stringify({
    bugs,
    consoleErrors: [...new Set(consoleErrors)],
    pageErrors,
    apiResults: { passed: apiPassed, failed: apiFailed },
    phases: results,
  }, null, 2));

  await browser.close();
  process.exit(0);
}

main().catch(console.error);
