/**
 * Analytics — lightweight event tracking.
 *
 * Tracks user interactions and sends them to the backend audit log.
 * No third-party scripts (no GA, no PostHog) — all data stays in-house.
 *
 * Usage:
 *   import { track } from "@/lib/analytics";
 *   track("campaign_created", { brand_id: "123", budget: 5000 });
 */

type EventName =
  | "page_view"
  | "campaign_created"
  | "campaign_approved"
  | "campaign_rejected"
  | "creative_generated"
  | "council_reviewed"
  | "onboarding_completed"
  | "plan_upgraded"
  | "plan_downgraded"
  | "channel_connected"
  | "channel_disconnected"
  | "export_downloaded"
  | "tool_invoked"
  | "artefact_rendered"
  | "search_performed"
  | "feature_used"
  | "error_occurred";

interface EventPayload {
  [key: string]: string | number | boolean | null | undefined;
}

const BATCH_SIZE = 10;
const BATCH_TIMEOUT_MS = 5000;
let batch: { name: string; payload: EventPayload; timestamp: string }[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleFlush(): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = setTimeout(flush, BATCH_TIMEOUT_MS);
}

async function flush(): Promise<void> {
  if (batch.length === 0) return;
  const events = [...batch];
  batch = [];
  try {
    await fetch("/api/analytics/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events }),
      keepalive: true,
    });
  } catch {
    // Silently fail — analytics should never break the app
  }
}

export function track(name: EventName, payload: EventPayload = {}): void {
  if (typeof window === "undefined") return;

  batch.push({
    name,
    payload: {
      ...payload,
      path: window.location.pathname,
      referrer: document.referrer || undefined,
    },
    timestamp: new Date().toISOString(),
  });

  if (batch.length >= BATCH_SIZE) {
    flush();
  } else {
    scheduleFlush();
  }
}

export function trackPageView(path?: string): void {
  track("page_view", { path: path || (typeof window !== "undefined" ? window.location.pathname : "") });
}

export function trackToolInvocation(toolName: string, durationMs?: number): void {
  track("tool_invoked", { tool_name: toolName, duration_ms: durationMs });
}

export function trackArtefactRender(kind: string): void {
  track("artefact_rendered", { kind });
}

export function trackError(error: string, context?: EventPayload): void {
  track("error_occurred", { error, ...context });
}

// Flush on page unload
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", flush);
  window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
}
