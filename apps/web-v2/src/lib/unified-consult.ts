/**
 * Unified Consult API client — ONE client for ALL domains.
 *
 * Replaces the duplicated `consultApi` and `creatorApi` clients. The domain is
 * selected by the `domain` parameter, which loads the appropriate Domain Pack
 * on the backend.
 *
 * Adding a new domain requires ZERO changes here. The backend registry handles it.
 */
import { apiGet, apiPost } from "./api";

// ─── Types (domain-agnostic) ──────────────────────────────────────────────

export interface DomainSubtype {
  id: string;
  label: string;
  emoji: string;
  blurb: string;
}

export interface DomainSummary {
  id: string;
  label: string;
  emoji: string;
  customer_type: "business" | "creator";
  subtypes: DomainSubtype[];
}

export interface NavItem {
  label: string;
  path: string;
  icon: string;
}

export interface NavSection {
  section: string;
  items: NavItem[];
}

export interface KpiCardSpec {
  key: string;
  label: string;
  icon: string;
  hint: string;
  /** Optional trend indicator. When absent, a graceful "connect channels" fallback is shown. */
  trend_direction?: "up" | "down" | "flat" | "new";
  /** Percentage change (e.g. 18 for "+18%"). Only shown when trend_direction is present. */
  trend_pct?: number;
  /** One-line context explaining what the number means and why it matters. */
  context?: string;
  /** Link href for a "See why" call-to-action. Shown only when the card is actionable. */
  see_why_href?: string;
}

export interface WidgetSpec {
  kind: string;
  title: string;
  props: Record<string, unknown>;
}

export interface ActionCardSpec {
  title: string;
  description: string;
  href: string;
  icon: string;
  accent: string;
}

export interface ToolSummary {
  id: string;
  label: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface DomainConfig {
  domain: string;
  label: string;
  emoji: string;
  nav_sections: NavSection[];
  kpi_cards: KpiCardSpec[];
  dashboard_widgets: WidgetSpec[];
  quick_actions: ActionCardSpec[];
  tools: ToolSummary[];
}

export interface ConsultRequest {
  message: string;
  domain: string;
  subtype_id?: string;
  brand_id?: string;
}

export interface ConsultResponse {
  reply: string;
  understanding: Record<string, unknown>;
  opportunities: Array<Record<string, unknown>>;
  plan: Array<Record<string, unknown>>;
  extracted: Record<string, unknown>;
  brand_id: string;
  brand_name: string;
  confidence: number;
  tokens_used: number;
  model: string;
  domain: string;
}

export interface CampaignRequest {
  brand_id: string;
  goal: string;
  budget: string;
  domain: string;
}

export interface CampaignResponse {
  reply: string;
  preview: Record<string, unknown>;
  campaign_plan_id: string;
  confidence: number;
  tokens_used: number;
  model: string;
  domain: string;
}

// ─── Strategy types (B.1.1 + B.1.2) ───────────────────────────────────────

/** A single marketing strategy proposed by the StrategyEngine. */
export interface Strategy {
  /** Short, memorable name (e.g. "Signature Dish Hero"). */
  name: string;
  /** 2-3 sentences describing the strategic approach. */
  approach: string;
  /** 1-2 sentences explaining why this approach is effective. */
  why_it_works: string;
  /** 2-3 specific risks of this approach. */
  risks: string[];
  /** 1 sentence on the expected result if executed well. */
  expected_outcome: string;
  /** "primary" | "alternative" | "contrarian". */
  strategy_type: "primary" | "alternative" | "contrarian";
}

/** The "why A not B" explanation for the chosen primary strategy. */
export interface StrategyExplanation {
  /** The name of the chosen (primary) strategy. */
  chosen_strategy: string;
  /** 2-3 sentences explaining why this is the best choice. */
  reasoning: string;
  /** 1-2 sentences explaining why the alternative was not chosen. */
  why_not_alternative: string;
  /** 1-2 sentences explaining why the contrarian was not chosen. */
  why_not_contrarian: string;
  /** 3-5 specific factors that decided the choice. */
  key_factors: string[];
}

export interface ToolRequest {
  domain: string;
  inputs: Record<string, unknown>;
}

export interface ToolResponse {
  reply: string;
  output: Record<string, unknown>;
  tokens_used: number;
  model: string;
  tool_id: string;
}

// ─── API client ───────────────────────────────────────────────────────────

export const unifiedConsultApi = {
  /** List all available domains + subtypes (for onboarding UI). */
  async domains(): Promise<DomainSummary[]> {
    const res = await apiGet<{ domains: DomainSummary[] }>("/consult/domains");
    return res.domains;
  },

  /** Get the full config for a domain (nav, KPIs, widgets, tools). */
  async config(domain: string): Promise<DomainConfig> {
    return apiGet(`/consult/nav/${domain}`);
  },

  /** Universal consult — works for any domain. */
  async consult(req: ConsultRequest): Promise<ConsultResponse> {
    return apiPost("/consult", req);
  },

  /** Universal campaign generation — works for any domain. */
  async campaign(req: CampaignRequest): Promise<CampaignResponse> {
    return apiPost("/consult/campaign", req);
  },

  /** Invoke a domain-specific tool (e.g. repurpose, youtube_plan). */
  async tool(toolId: string, req: ToolRequest): Promise<ToolResponse> {
    return apiPost(`/consult/tool/${toolId}`, req);
  },
};
