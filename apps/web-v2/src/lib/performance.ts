/**
 * Performance Intelligence API client.
 *
 * Wraps the `/performance/*` backend endpoints
 * (apps/api/prachar_api/routers/performance.py).
 *
 * Three endpoints:
 *  - `GET /performance/{campaign_id}`         → "What happened" summary
 *  - `GET /performance/{campaign_id}/why`     → "Why" analysis (likely causes)
 *  - `GET /performance/{campaign_id}/next`    → "What next" recommendations
 *
 * The why/next endpoints may not exist yet (built in parallel). The client
 * exposes them anyway and the UI degrades gracefully on 404.
 */
import { apiGet, ApiError } from "./api";

// ─── Types ────────────────────────────────────────────────────────────────

/** Aggregated totals / averages for the analysis window. */
export interface TopMetrics {
  impressions?: number;
  clicks?: number;
  conversions?: number;
  spend?: number;
  revenue?: number;
  avg_ctr?: number;
  avg_cpa?: number;
  avg_roas?: number;
  [key: string]: number | undefined;
}

/** A single notable day where a metric spiked or dropped >20% vs average. */
export interface NotableDay {
  date: string;
  metric: string;
  value: number;
  note: string;
}

/** Per-metric comparison to an industry benchmark. */
export interface BenchmarkEntry {
  actual: number;
  benchmark: number;
  difference: number;
  status: "better" | "worse" | "unknown";
}

/** "What happened" — the PerformanceSummary returned by the backend. */
export interface PerformanceSummary {
  campaign_id: string;
  summary: string;
  top_metrics: TopMetrics;
  trend: "up" | "down" | "flat" | string;
  notable_days: NotableDay[];
  benchmark_comparison: Record<string, BenchmarkEntry>;
}

/** A likely cause from the "Why" analysis. */
export interface LikelyCause {
  cause: string;
  evidence: string;
  confidence: "high" | "medium" | "low" | string;
}

/** Wrapper for the why endpoint — backend returns `{ likely_causes: [...] }`. */
export interface WhyAnalysis {
  likely_causes: LikelyCause[];
}

/** A recommendation from the "What next" analysis. */
export interface Recommendation {
  action: string;
  expected_impact: string;
  priority: "high" | "medium" | "low" | string;
}

/** Wrapper for the next endpoint — backend returns `{ recommendations: [...] }`. */
export interface NextRecommendations {
  recommendations: Recommendation[];
}

// ─── Story types (A.5.1) ──────────────────────────────────────────────────

/** A highlight callout card in the narrative story. */
export interface StoryHighlight {
  metric: string;
  value: string;
  insight: string;
}

/** A platform's share of the campaign's performance. */
export interface PlatformBreakdownEntry {
  platform: string;
  share: number;
  conversion_rate: number;
  conversions: number;
}

/** A time-based insight (e.g. weekend vs weekday). */
export interface TimeInsight {
  period: string;
  insight: string;
}

/** The narrative story returned by `GET /performance/{campaign_id}/story`. */
export interface PerformanceStory {
  campaign_id: string;
  headline: string;
  paragraphs: string[];
  highlights: StoryHighlight[];
  platform_breakdown: PlatformBreakdownEntry[];
  time_insights: TimeInsight[];
}

// ─── API client ───────────────────────────────────────────────────────────

export const performanceApi = {
  /** "What happened" — aggregated performance summary for a campaign. */
  async getSummary(campaignId: string, days = 30): Promise<PerformanceSummary> {
    return apiGet<PerformanceSummary>(
      `/performance/${campaignId}?days=${days}`,
    );
  },

  /** "Why" — likely causes for the observed performance. May 404 if not built yet. */
  async getWhy(campaignId: string): Promise<WhyAnalysis> {
    return apiGet<WhyAnalysis>(`/performance/${campaignId}/why`);
  },

  /** "What next" — recommended actions. May 404 if not built yet. */
  async getNext(campaignId: string): Promise<NextRecommendations> {
    return apiGet<NextRecommendations>(`/performance/${campaignId}/next`);
  },

  /** "Story" — narrative performance story (de-jargonised, human-readable). */
  async getStory(campaignId: string, days = 30): Promise<PerformanceStory> {
    return apiGet<PerformanceStory>(
      `/performance/${campaignId}/story?days=${days}`,
    );
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────

/** True when an error is a 404 from the API (endpoint not built yet). */
export function isNotFound(err: unknown): boolean {
  if (err instanceof ApiError) return err.status === 404;
  return false;
}
