"use client";

/**
 * Shared Presentation Layer — domain-agnostic components for the consult flow.
 *
 * These components replace the duplicated Business* and Creator* components
 * in onboarding/page.tsx. They are driven by domain-supplied data, not
 * hard-coded for a specific domain.
 *
 * Adding a new domain requires ZERO changes here. The domain pack supplies
 * the data; these components render it.
 */
import { ReactNode, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Target,
  TrendingUp,
  Zap,
  Sparkles,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types (domain-agnostic) ──────────────────────────────────────────────

export interface InsightSection {
  title: string;
  items: string[];
  accent: "success" | "warning" | "info" | "danger";
  icon: "check" | "alert" | "target" | "trend";
}

export interface Opportunity {
  title: string;
  description: string;
  business_impact?: string;
  impact?: string;
  difficulty?: string;
  timeframe?: string;
}

export interface PlanWeek {
  week: number;
  theme: string;
  // Business weeks
  objectives?: string[];
  content?: string[];
  offers?: string[];
  channels?: string[];
  // Creator weeks
  videos?: string[];
  shorts?: string[];
  community_posts?: string[];
  collaborations?: string[];
  seo?: string[];
  newsletter?: string;
  live_sessions?: string;
  // Universal
  kpis?: string[];
  // Domain-specific extras
  [key: string]: unknown;
}

export interface CampaignPreview {
  title: string;
  hero_image_concept?: string;
  video_concept?: string;
  post_ideas?: string[];
  estimated_reach?: string;
  expected_enquiries?: string;
  budget_estimate?: string;
  why_this_campaign?: string;
  why?: string;
  confidence?: number;
  expected_benefit?: string;
  risks?: string[];
  alternative?: string;
  // Creator campaign fields
  content_plan?: PlanWeek[];
  publishing_schedule?: string;
  expected_growth?: string;
  // 3 creative directions (P1.1)
  creative_directions?: CreativeDirection[];
  // 5 hook patterns (P1.2)
  hooks?: Hook[];
  // Audience psychology (P1.3)
  audience_psychology?: AudiencePsychology;
  // 3 engineered offers (P1.4)
  offers?: Offer[];
  // 3 pricing presentations (P1.5)
  pricing_psychology?: PricingPresentation[];
  // Seasonal ideas (P1.6)
  seasonal_ideas?: SeasonalIdea[];
  // Local marketing ideas (P1.7)
  local_ideas?: LocalIdea[];
  // Competitor differentiation (P1.8)
  differentiation?: DifferentiationEntry[];
  // A/B concepts (P1.9)
  ab_concepts?: ABConcept[];
  // 3 strategies + "why A not B" explanation (B.1.1 + B.1.2)
  strategies?: Strategy[];
  strategy_explanation?: StrategyExplanation;
  // Domain-specific extras
  [key: string]: unknown;
}

export interface CreativeDirection {
  id: string;
  hook: string;
  angle: string;
  tone: string;
  sample_headline: string;
  sample_cta: string;
}

export interface Hook {
  pattern: string;
  copy: string;
  why_it_works: string;
}

export interface AudiencePsychology {
  motivations: string[];
  objections: string[];
  emotional_triggers: string[];
  decision_style: string;
}

export interface Offer {
  structure: string;
  copy: string;
  psychology_lever: string;
  expected_conversion_lift: string;
}

export interface PricingPresentation {
  technique: string;
  copy: string;
  rationale: string;
}

export interface SeasonalIdea {
  month: string;
  occasion: string;
  idea: string;
  copy: string;
}

export interface LocalIdea {
  type: string;
  idea: string;
  copy: string;
}

export interface DifferentiationEntry {
  competitor_claim: string;
  our_counter: string;
  evidence: string;
}

export interface ABConcept {
  direction_id: string;
  variant_label: string;
  what_changed: string;
  why: string;
  expected_audience_segment: string;
  hook: string;
  headline: string;
  cta: string;
}

export interface Strategy {
  name: string;
  approach: string;
  why_it_works: string;
  risks: string[];
  expected_outcome: string;
  strategy_type: "primary" | "alternative" | "contrarian";
}

export interface StrategyExplanation {
  chosen_strategy: string;
  reasoning: string;
  why_not_alternative: string;
  why_not_contrarian: string;
  key_factors: string[];
}

export type WeekFieldSpec =
  | { key: string; label: string; kind: "list" }
  | { key: string; label: string; kind: "text" };

export interface DomainPresentationConfig {
  /** The fields to render for each week of the 30-day plan. */
  weekFields: WeekFieldSpec[];
  /** The sections to render in the understanding cards. */
  understandingSections: InsightSection[];
  /** Whether to show marketing maturity. */
  showMaturity?: boolean;
  /** Label for the understanding summary ("business" | "creator profile"). */
  understandingLabel?: string;
  /** Label for the opportunities section. */
  opportunitiesLabel?: string;
  /** Label for the plan section. */
  planLabel?: string;
}

// ─── Icon helper ──────────────────────────────────────────────────────────

function SectionIcon({ name, className }: { name: string; className?: string }) {
  switch (name) {
    case "check":
      return <CheckCircle2 className={className} />;
    case "alert":
      return <AlertCircle className={className} />;
    case "target":
      return <Target className={className} />;
    case "trend":
      return <TrendingUp className={className} />;
    default:
      return <Sparkles className={className} />;
  }
}

// ─── WhyExplanation (subtle muted "why" text under section titles) ─────────

/**
 * Renders a 1-2 line "why" explanation in a subtle muted style.
 * Shown under section titles to explain the reasoning behind each recommendation.
 */
function WhyExplanation({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p className="text-xs text-text-muted mt-1.5 leading-relaxed">{children}</p>
  );
}

/**
 * Data-driven "why" text generators.
 * These use the campaign preview data to explain the reasoning behind each section.
 * Falls back to industry-general reasoning when data is unavailable.
 */

function whyBudgetSplit(preview: CampaignPreview): string {
  // Data-driven: mention the budget estimate if available
  if (preview.budget_estimate) {
    return `Why this budget? ${preview.budget_estimate} is split across the channels that deliver the best return for your industry — not spread thin everywhere.`;
  }
  return "Why this budget? It's split across the channels that deliver the best return for your industry — not spread thin everywhere.";
}

function whyPosts(preview: CampaignPreview): string {
  // Data-driven: use hook patterns to explain why these posts
  if (preview.hooks && preview.hooks.length > 0) {
    const patterns = preview.hooks
      .slice(0, 2)
      .map((h) => h.pattern)
      .join(" and ");
    return `Why these posts? Because your audience responds to ${patterns} hooks — these patterns consistently capture attention in your industry.`;
  }
  return "Why these posts? Because your audience responds to proven attention patterns that work in your industry.";
}

function whyCreativeDirections(): string {
  return "Why these directions? Different angles resonate with different segments of your audience — testing reveals what actually converts.";
}

function whyHookPatterns(): string {
  return "Why these hooks? These attention patterns are proven to stop the scroll for audiences like yours.";
}

function whyAudiencePsychology(): string {
  return "Why this matters? Understanding what drives and blocks your audience leads to messaging that converts — not guesses.";
}

function whyOffers(): string {
  return "Why these offers? Psychological levers like scarcity and anchoring drive action — they make the offer feel urgent and valuable.";
}

function whyPricingPsychology(): string {
  return "Why this pricing? How you present price shapes perception more than the price itself — these techniques make it feel fair and attractive.";
}

function whySeasonalIdeas(): string {
  return "Why seasonal? Timing your message to occasions and events increases relevance and urgency — people buy when the moment feels right.";
}

function whyLocalIdeas(): string {
  return "Why local? Nearby customers convert faster and at lower cost — local marketing captures demand from people who can actually walk in.";
}

function whyDifferentiation(): string {
  return "Why differentiate? Standing out from competitors wins attention in a crowded market — your unique angle is your strongest asset.";
}

function whyABConcepts(): string {
  return "Why A/B test? Testing variants against each other reveals what actually converts with your audience — no guessing, just evidence.";
}

function whyHeroImage(): string {
  return "Why this image? Visual first impressions determine whether people read on — the right image stops the scroll instantly.";
}

function whyVideoConcept(): string {
  return "Why video? Video captures attention and drives higher engagement than static posts — it's the most effective format for your audience.";
}

function whyPublishingSchedule(): string {
  return "Why this schedule? Posting when your audience is most active maximizes reach — timing matters as much as content.";
}

function whyMetrics(): string {
  return "Why these numbers? Based on industry benchmarks and your budget level — realistic expectations, not inflated promises.";
}

function whyConfidence(): string {
  return "Why this confidence? Based on your industry data, historical campaign performance, and how well the strategy fits your goals.";
}

function whyRisks(): string {
  return "Why flag these? Knowing risks upfront lets us mitigate them before they cost you — transparency over false promises.";
}

function whyAlternative(): string {
  return "Why have a backup? No campaign is guaranteed — a Plan B ensures momentum continues if results underperform.";
}

function whyActions(): string {
  return "Why these actions? Approving now gets your campaign live while momentum is high — every day you wait is a day without reaching customers.";
}

function whyExecutiveSummary(preview: CampaignPreview): string {
  // Data-driven: use the why_this_campaign field if available
  if (preview.why_this_campaign || preview.why) {
    const whyText = (preview.why_this_campaign || preview.why) as string;
    // Truncate if too long — keep it to 1-2 lines
    if (whyText.length <= 160) return `Why this campaign? ${whyText}`;
    return `Why this campaign? ${whyText.slice(0, 157)}…`;
  }
  return "Why this campaign? It's built around your goal and targets your ideal customer where they already spend time.";
}

// ─── UnderstandingCards (replaces BusinessUnderstandingCards + CreatorUnderstandingCards) ─

export function UnderstandingCards({
  understanding,
  config,
  onContinue,
  continueLabel = "See growth opportunities",
}: {
  understanding: Record<string, unknown>;
  config: DomainPresentationConfig;
  onContinue: () => void;
  continueLabel?: string;
}) {
  const summary = (understanding.summary as string) || (understanding.niche as string) || "";
  const maturity = (understanding.marketing_maturity as string) || (understanding.growth_stage as string) || "";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        Here&apos;s what I see
      </div>

      {/* Summary */}
      {summary && (
        <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
          <p className="text-sm text-text leading-relaxed">{summary}</p>
        </div>
      )}

      {/* Insight sections (2x2 grid) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {config.understandingSections.map((section) => {
          const key = section.title.toLowerCase().replace(/[^a-z]/g, "_");
          const items = (understanding[key] as string[]) || [];
          if (!items || items.length === 0) return null;
          return (
            <InsightCard
              key={section.title}
              title={section.title}
              items={items}
              accent={section.accent}
              icon={<SectionIcon name={section.icon} className={cn("w-4 h-4", accentClass(section.accent))} />}
            />
          );
        })}
      </div>

      {/* Maturity / growth stage */}
      {config.showMaturity && maturity && (
        <div className="glass rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
            <Zap className="w-5 h-5 text-accent" />
          </div>
          <div>
            <div className="label-field">{config.understandingLabel === "creator" ? "Growth stage" : "Marketing maturity"}</div>
            <div className="text-sm text-text mt-0.5">{maturity}</div>
          </div>
        </div>
      )}

      {/* Continue */}
      <div className="flex justify-end pt-2">
        <button onClick={onContinue} className="btn-primary group">
          {continueLabel}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

// ─── InsightCard (shared — was already shared, now formalised) ────────────

function accentClass(accent: "success" | "warning" | "info" | "danger"): string {
  return { success: "text-success", warning: "text-warning", info: "text-info", danger: "text-danger" }[accent];
}

export function InsightCard({
  title,
  items,
  accent,
  icon,
}: {
  title: string;
  items: string[];
  accent: "success" | "warning" | "info" | "danger";
  icon: ReactNode;
}) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className={accentClass(accent)}>{icon}</span>
        <span className="label-field">{title}</span>
      </div>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <div className={cn("w-1.5 h-1.5 rounded-full mt-2 shrink-0", accentClass(accent).replace("text-", "bg-"))} />
            <span className="text-sm text-text-secondary">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── OpportunityCards (replaces OpportunityCards + CreatorOpportunityCards) ─

export function OpportunityCards({
  opportunities,
  onContinue,
  continueLabel = "See your 30-day plan",
}: {
  opportunities: Opportunity[];
  onContinue: () => void;
  continueLabel?: string;
}) {
  if (opportunities.length === 0) return null;
  const isStructured = opportunities[0]?.title && (opportunities[0]?.business_impact || opportunities[0]?.impact);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <TrendingUp className="w-3.5 h-3.5 text-accent" />
        Growth opportunities
      </div>

      <div className="space-y-3">
        {opportunities.map((opp, i) => (
          <div key={i} className="glass rounded-xl p-4 flex gap-4">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 font-mono text-sm text-accent">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text">{opp.title}</div>
              <div className="text-sm text-text-secondary mt-1">{opp.description}</div>
              {isStructured && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {(opp.business_impact || opp.impact) && (
                    <Badge label="Impact" value={opp.business_impact || opp.impact || ""} />
                  )}
                  {opp.difficulty && <Badge label="Difficulty" value={opp.difficulty} />}
                  {opp.timeframe && (
                    <Badge label="Timeframe" value={opp.timeframe} icon={<Clock className="w-3 h-3" />} />
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end pt-2">
        <button onClick={onContinue} className="btn-primary group">
          {continueLabel}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function Badge({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  const color =
    value.toLowerCase().includes("high") || value.toLowerCase().includes("hard")
      ? "text-danger bg-danger/10"
      : value.toLowerCase().includes("medium")
        ? "text-warning bg-warning/10"
        : "text-success bg-success/10";
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono", color)}>
      {icon}
      {label}: {value}
    </span>
  );
}

// ─── PlanTimeline (replaces PlanTimeline + CreatorPlanTimeline) ───────────

export function PlanTimeline({
  weeks,
  config,
  onContinue,
  continueLabel = "Build my campaign",
}: {
  weeks: PlanWeek[];
  config: DomainPresentationConfig;
  onContinue: () => void;
  continueLabel?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Clock className="w-3.5 h-3.5 text-accent" />
        Your 30-day plan
      </div>

      <div className="relative pl-6">
        <div className="absolute left-2 top-2 bottom-2 w-px bg-border" />
        {weeks.map((week, i) => (
          <PlanWeekCard key={i} week={week} fields={config.weekFields} isLast={i === weeks.length - 1} />
        ))}
      </div>

      <div className="flex justify-end pt-2">
        <button onClick={onContinue} className="btn-primary group">
          {continueLabel}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function PlanWeekCard({ week, fields, isLast }: { week: PlanWeek; fields: WeekFieldSpec[]; isLast: boolean }) {
  return (
    <div className={cn("relative", isLast ? "" : "pb-6")}>
      <div className="absolute -left-[18px] top-1 w-3 h-3 rounded-full bg-accent ring-4 ring-accent/10" />
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-xs text-text-muted">Week {week.week}</span>
          <span className="text-sm font-medium text-text">{week.theme}</span>
        </div>
        <div className="space-y-3">
          {fields.map((field) => {
            const value = week[field.key];
            if (field.kind === "list") {
              const items = (value as string[]) || [];
              if (items.length === 0) return null;
              return (
                <div key={field.key}>
                  <div className="label-field mb-1">{field.label}</div>
                  <ul className="space-y-1">
                    {items.map((item, j) => (
                      <li key={j} className="text-sm text-text-secondary flex items-start gap-2">
                        <div className="w-1 h-1 rounded-full bg-text-muted mt-2 shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            }
            // text
            const text = (value as string) || "";
            if (!text) return null;
            return (
              <div key={field.key}>
                <div className="label-field mb-1">{field.label}</div>
                <p className="text-sm text-text-secondary">{text}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── StrategySection (B.2.1 + B.2.2: 3 strategies + "why" + comparison) ─────

const STRATEGY_TYPE_STYLES: Record<string, string> = {
  primary: "bg-accent/15 text-accent border-accent/40",
  alternative: "bg-info/10 text-info border-info/30",
  contrarian: "bg-warning/10 text-warning border-warning/30",
};

const STRATEGY_TYPE_LABEL: Record<string, string> = {
  primary: "Primary",
  alternative: "Alternative",
  contrarian: "Contrarian",
};

/**
 * StrategySection — the strategic foundation of the campaign preview.
 *
 * Shows the 3 strategies (primary highlighted, alternative + contrarian
 * muted) as cards, followed by the "Why I chose {chosen}" explanation.
 * A "Compare strategies" toggle reveals a side-by-side comparison table.
 *
 * Placed ABOVE the tabbed insight sections so it's the first thing the
 * user sees — the strategy is the foundation everything else builds on.
 */
export function StrategySection({
  strategies,
  explanation,
}: {
  strategies: Strategy[];
  explanation?: StrategyExplanation;
}) {
  const [showComparison, setShowComparison] = useState(false);

  if (!strategies || strategies.length === 0) return null;

  const primary = strategies.find((s) => s.strategy_type === "primary");
  const alternative = strategies.find((s) => s.strategy_type === "alternative");
  const contrarian = strategies.find((s) => s.strategy_type === "contrarian");
  const secondary = strategies.filter((s) => s.strategy_type !== "primary");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
          <Target className="w-3.5 h-3.5 text-accent" />
          Strategy foundation
        </div>
        {strategies.length > 1 && (
          <button
            onClick={() => setShowComparison((v) => !v)}
            className={cn(
              "shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors",
              showComparison
                ? "bg-accent text-white"
                : "glass text-text-secondary hover:text-text"
            )}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            {showComparison ? "Hide comparison" : "Compare strategies"}
          </button>
        )}
      </div>

      {/* ─── Strategy cards (B.2.1) ─────────────────────────────────────── */}
      {!showComparison && (
        <div className="space-y-3">
          {/* Primary — prominent, accent border, larger */}
          {primary && <StrategyCard strategy={primary} prominent />}

          {/* Alternative + Contrarian — secondary, muted, smaller */}
          {secondary.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {secondary.map((s, i) => (
                <StrategyCard key={i} strategy={s} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── Comparison table (B.2.2) ───────────────────────────────────── */}
      {showComparison && (
        <StrategyComparison
          primary={primary}
          alternative={alternative}
          contrarian={contrarian}
        />
      )}

      {/* ─── "Why I chose {chosen}" explanation (B.2.1) ─────────────────── */}
      {explanation && (explanation.reasoning || explanation.why_not_alternative || explanation.why_not_contrarian) && (
        <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50 space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            <h4 className="text-sm font-semibold text-text">
              Why I chose {explanation.chosen_strategy || primary?.name || "this strategy"}
            </h4>
          </div>

          {explanation.reasoning && (
            <p className="text-sm text-text-secondary leading-relaxed">
              {explanation.reasoning}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {alternative && explanation.why_not_alternative && (
              <div className="glass rounded-xl p-3 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono bg-info/10 text-info">
                    {STRATEGY_TYPE_LABEL.alternative}
                  </span>
                  <span className="text-xs text-text-muted">Why not {alternative.name}?</span>
                </div>
                <p className="text-sm text-text-secondary">{explanation.why_not_alternative}</p>
              </div>
            )}
            {contrarian && explanation.why_not_contrarian && (
              <div className="glass rounded-xl p-3 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono bg-warning/10 text-warning">
                    {STRATEGY_TYPE_LABEL.contrarian}
                  </span>
                  <span className="text-xs text-text-muted">Why not {contrarian.name}?</span>
                </div>
                <p className="text-sm text-text-secondary">{explanation.why_not_contrarian}</p>
              </div>
            )}
          </div>

          {explanation.key_factors && explanation.key_factors.length > 0 && (
            <div className="space-y-2">
              <div className="label-field">Key factors</div>
              <div className="flex flex-wrap gap-2">
                {explanation.key_factors.map((factor, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono bg-accent/10 text-accent"
                  >
                    {factor}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** A single strategy card. Prominent = primary (accent border, larger). */
function StrategyCard({
  strategy,
  prominent = false,
}: {
  strategy: Strategy;
  prominent?: boolean;
}) {
  const badgeStyle = STRATEGY_TYPE_STYLES[strategy.strategy_type] || STRATEGY_TYPE_STYLES.primary;
  const typeLabel = STRATEGY_TYPE_LABEL[strategy.strategy_type] || strategy.strategy_type;

  return (
    <div
      className={cn(
        "rounded-2xl p-5 space-y-3",
        prominent
          ? "glass-strong border-l-2 border-l-accent/60"
          : "glass"
      )}
    >
      {/* Header: name + type badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {prominent && (
            <div className="text-xs text-text-muted uppercase tracking-wider font-mono mb-1">
              Recommended
            </div>
          )}
          <h4 className={cn("font-semibold text-text", prominent ? "text-base" : "text-sm")}>
            {strategy.name}
          </h4>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono border",
            badgeStyle
          )}
        >
          {typeLabel}
        </span>
      </div>

      {/* Approach */}
      {strategy.approach && (
        <div>
          <div className="label-field mb-1">Approach</div>
          <p className="text-sm text-text-secondary leading-relaxed">{strategy.approach}</p>
        </div>
      )}

      {/* Why it works */}
      {strategy.why_it_works && (
        <div>
          <div className="label-field mb-1">Why it works</div>
          <p className="text-sm text-text-secondary leading-relaxed">{strategy.why_it_works}</p>
        </div>
      )}

      {/* Risks */}
      {strategy.risks && strategy.risks.length > 0 && (
        <div>
          <div className="label-field mb-1">Risks</div>
          <ul className="space-y-1">
            {strategy.risks.map((risk, i) => (
              <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-warning mt-0.5 shrink-0" />
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Expected outcome */}
      {strategy.expected_outcome && (
        <div className="flex items-start gap-2 pt-1 border-t border-border/30">
          <TrendingUp className="w-3.5 h-3.5 text-success mt-0.5 shrink-0" />
          <div>
            <span className="label-field mr-1">Expected outcome:</span>
            <span className="text-sm text-text-secondary">{strategy.expected_outcome}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * StrategyComparison — side-by-side comparison table of the 3 strategies.
 * Rows: Approach, Why it works, Risks, Expected outcome.
 * Columns: Primary, Alternative, Contrarian.
 * Responsive: stacked on mobile, side-by-side on desktop.
 */
function StrategyComparison({
  primary,
  alternative,
  contrarian,
}: {
  primary?: Strategy;
  alternative?: Strategy;
  contrarian?: Strategy;
}) {
  const allColumns = [
    { strategy: primary, label: "Primary", accent: "text-accent" },
    { strategy: alternative, label: "Alternative", accent: "text-info" },
    { strategy: contrarian, label: "Contrarian", accent: "text-warning" },
  ];
  const columns = allColumns.filter(
    (c): c is { strategy: Strategy; label: string; accent: string } => Boolean(c.strategy)
  );

  if (columns.length === 0) return null;

  const rows: { label: string; key: keyof Strategy }[] = [
    { label: "Approach", key: "approach" },
    { label: "Why it works", key: "why_it_works" },
    { label: "Expected outcome", key: "expected_outcome" },
  ];

  return (
    <div className="glass-strong rounded-2xl p-4 sm:p-5 overflow-x-auto">
      {/* Desktop: table layout (md+) */}
      <div className="hidden md:grid md:grid-cols-[140px_repeat(var(--cols),1fr)] gap-3"
           style={{ ["--cols" as string]: columns.length }}>
        {/* Header row */}
        <div className="text-xs text-text-muted uppercase tracking-wider font-mono self-end pb-2 border-b border-border/40">
          Strategy
        </div>
        {columns.map((col, i) => (
          <div key={i} className="pb-2 border-b border-border/40">
            <div className={cn("text-xs font-mono uppercase tracking-wider mb-0.5", col.accent)}>
              {col.label}
            </div>
            <div className="text-sm font-semibold text-text">{col.strategy!.name}</div>
          </div>
        ))}

        {/* Text rows */}
        {rows.map((row) => (
          <RowGroup key={row.key} label={row.label} columns={columns} field={row.key} />
        ))}

        {/* Risks row (list) */}
        <div className="text-xs text-text-muted uppercase tracking-wider font-mono pt-3 border-t border-border/30">
          Risks
        </div>
        {columns.map((col, i) => (
          <div key={i} className="pt-3 border-t border-border/30">
            <ul className="space-y-1">
              {(col.strategy!.risks || []).map((risk, j) => (
                <li key={j} className="text-sm text-text-secondary flex items-start gap-1.5">
                  <AlertCircle className="w-3 h-3 text-warning mt-1 shrink-0" />
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Mobile: stacked cards */}
      <div className="md:hidden space-y-3">
        {columns.map((col, i) => (
          <div key={i} className="glass rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className={cn("text-xs font-mono uppercase tracking-wider", col.accent)}>
                {col.label}
              </span>
              <span className="text-sm font-semibold text-text">{col.strategy!.name}</span>
            </div>
            {rows.map((row) => {
              const value = col.strategy![row.key];
              if (!value || (typeof value === "string" && !value.trim())) return null;
              return (
                <div key={row.key}>
                  <div className="label-field mb-0.5">{row.label}</div>
                  <p className="text-sm text-text-secondary">{value as string}</p>
                </div>
              );
            })}
            {(col.strategy!.risks || []).length > 0 && (
              <div>
                <div className="label-field mb-1">Risks</div>
                <ul className="space-y-1">
                  {col.strategy!.risks.map((risk, j) => (
                    <li key={j} className="text-sm text-text-secondary flex items-start gap-1.5">
                      <AlertCircle className="w-3 h-3 text-warning mt-1 shrink-0" />
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Helper: renders a label cell + one value cell per column for a text field. */
function RowGroup({
  label,
  columns,
  field,
}: {
  label: string;
  columns: { strategy: Strategy; label: string; accent: string }[];
  field: keyof Strategy;
}) {
  return (
    <>
      <div className="text-xs text-text-muted uppercase tracking-wider font-mono pt-3 border-t border-border/30">
        {label}
      </div>
      {columns.map((col, i) => {
        const value = col.strategy[field];
        return (
          <div key={i} className="pt-3 border-t border-border/30">
            <p className="text-sm text-text-secondary leading-relaxed">
              {(value as string) || "—"}
            </p>
          </div>
        );
      })}
    </>
  );
}

// ─── CampaignDeck (replaces CampaignPreviewDeck + CreatorCampaignPreview) ──

export function CampaignDeck({
  preview,
  domain,
  onApprove,
  onRegenerate,
  generating,
}: {
  preview: CampaignPreview;
  domain: string;
  onApprove: () => void;
  onRegenerate: () => void;
  generating?: boolean;
}) {
  const isCreator = domain === "creator";

  // ─── Tabbed strategy sections (A.6.1) ────────────────────────────────────
  // Group the 9 insight sections into 3 tabs to create visual hierarchy.
  type TabKey = "strategy" | "creative" | "context";
  const [activeTab, setActiveTab] = useState<TabKey>("strategy");

  const tabs: { key: TabKey; label: string; hint: string }[] = [
    { key: "strategy", label: "Strategy", hint: "Directions, psychology & differentiation" },
    { key: "creative", label: "Creative", hint: "Hooks, offers, pricing & A/B tests" },
    { key: "context", label: "Context", hint: "Seasonal & local opportunities" },
  ];

  // Determine which tabs have content (so we only show relevant ones)
  const hasStrategy = Boolean(
    (preview.creative_directions && preview.creative_directions.length > 0) ||
      preview.audience_psychology ||
      (preview.differentiation && preview.differentiation.length > 0)
  );
  const hasCreative = Boolean(
    (preview.hooks && preview.hooks.length > 0) ||
      (preview.offers && preview.offers.length > 0) ||
      (preview.pricing_psychology && preview.pricing_psychology.length > 0) ||
      (preview.ab_concepts && preview.ab_concepts.length > 0)
  );
  const hasContext = Boolean(
    (preview.seasonal_ideas && preview.seasonal_ideas.length > 0) ||
      (preview.local_ideas && preview.local_ideas.length > 0)
  );
  const tabHasContent: Record<TabKey, boolean> = {
    strategy: hasStrategy,
    creative: hasCreative,
    context: hasContext,
  };
  const visibleTabs = tabs.filter((t) => tabHasContent[t.key]);
  // If the active tab has no content, fall back to the first visible tab
  const effectiveTab: TabKey = tabHasContent[activeTab]
    ? activeTab
    : visibleTabs[0]?.key ?? "strategy";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        Your campaign
      </div>

      <div className="glass-strong rounded-2xl p-6 space-y-5">
        {/* Title — Executive Summary */}
        <div>
          <div className="label-field mb-1">Campaign title</div>
          <h3 className="text-xl font-semibold text-text">{preview.title}</h3>
          <WhyExplanation>{whyExecutiveSummary(preview)}</WhyExplanation>
        </div>

        {/* ─── Strategy foundation (B.2.1 + B.2.2) — ABOVE the tabs ─────── */}
        {preview.strategies && preview.strategies.length > 0 && (
          <StrategySection
            strategies={preview.strategies}
            explanation={preview.strategy_explanation}
          />
        )}

        {/* ─── Tabbed insight sections (A.6.1) ──────────────────────────── */}
        {visibleTabs.length > 0 && (
          <div className="space-y-4">
            {/* Tab bar — horizontally scrollable on mobile */}
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none border-b border-border/40">
              {visibleTabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    "shrink-0 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors border-b-2 -mb-px",
                    effectiveTab === tab.key
                      ? "text-accent border-accent"
                      : "text-text-secondary border-transparent hover:text-text"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Strategy tab: CreativeDirections (prominent), AudiencePsychology, Differentiation */}
            {effectiveTab === "strategy" && (
              <div className="space-y-5">
                {preview.creative_directions && preview.creative_directions.length > 0 && (
                  <CreativeDirections
                    directions={preview.creative_directions}
                    why={whyCreativeDirections()}
                    prominent
                  />
                )}
                {preview.audience_psychology && (
                  <AudiencePsychologySection
                    psychology={preview.audience_psychology}
                    why={whyAudiencePsychology()}
                  />
                )}
                {preview.differentiation && preview.differentiation.length > 0 && (
                  <DifferentiationSection
                    entries={preview.differentiation}
                    why={whyDifferentiation()}
                  />
                )}
              </div>
            )}

            {/* Creative tab: HookPatterns (prominent), Offers, Pricing, A/B */}
            {effectiveTab === "creative" && (
              <div className="space-y-5">
                {preview.hooks && preview.hooks.length > 0 && (
                  <HookPatterns hooks={preview.hooks} why={whyHookPatterns()} prominent />
                )}
                {preview.offers && preview.offers.length > 0 && (
                  <OfferSection offers={preview.offers} why={whyOffers()} />
                )}
                {preview.pricing_psychology && preview.pricing_psychology.length > 0 && (
                  <PricingPsychologySection
                    presentations={preview.pricing_psychology}
                    why={whyPricingPsychology()}
                  />
                )}
                {preview.ab_concepts && preview.ab_concepts.length > 0 && (
                  <ABConceptsSection concepts={preview.ab_concepts} why={whyABConcepts()} />
                )}
              </div>
            )}

            {/* Context tab: SeasonalIdeas (prominent), LocalIdeas */}
            {effectiveTab === "context" && (
              <div className="space-y-5">
                {preview.seasonal_ideas && preview.seasonal_ideas.length > 0 && (
                  <SeasonalIdeasSection
                    ideas={preview.seasonal_ideas}
                    why={whySeasonalIdeas()}
                    prominent
                  />
                )}
                {preview.local_ideas && preview.local_ideas.length > 0 && (
                  <LocalIdeasSection ideas={preview.local_ideas} why={whyLocalIdeas()} />
                )}
              </div>
            )}
          </div>
        )}

        {/* Hero + video concepts (business) */}
        {!isCreator && preview.hero_image_concept && (
          <div>
            <div className="label-field mb-1">Hero image</div>
            <p className="text-sm text-text-secondary">{preview.hero_image_concept}</p>
            <WhyExplanation>{whyHeroImage()}</WhyExplanation>
          </div>
        )}
        {!isCreator && preview.video_concept && (
          <div>
            <div className="label-field mb-1">Video concept</div>
            <p className="text-sm text-text-secondary">{preview.video_concept}</p>
            <WhyExplanation>{whyVideoConcept()}</WhyExplanation>
          </div>
        )}

        {/* Post ideas (business) — "What we'll post" */}
        {!isCreator && preview.post_ideas && preview.post_ideas.length > 0 && (
          <div>
            <div className="label-field mb-1">Post ideas</div>
            <WhyExplanation>{whyPosts(preview)}</WhyExplanation>
            <ul className="space-y-1 mt-2">
              {preview.post_ideas.map((idea, i) => (
                <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                  <div className="w-1 h-1 rounded-full bg-text-muted mt-2 shrink-0" />
                  {idea}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Publishing schedule (creator) */}
        {isCreator && preview.publishing_schedule && (
          <div>
            <div className="label-field mb-1">Publishing schedule</div>
            <p className="text-sm text-text-secondary">{preview.publishing_schedule}</p>
            <WhyExplanation>{whyPublishingSchedule()}</WhyExplanation>
          </div>
        )}

        {/* Expected growth / reach — Budget breakdown */}
        {(preview.estimated_reach || preview.expected_growth) && (
          <div className="space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {preview.estimated_reach && (
                <Metric label="Estimated reach" value={preview.estimated_reach} />
              )}
              {preview.expected_enquiries && (
                <Metric label="Expected enquiries" value={preview.expected_enquiries} />
              )}
              {preview.expected_growth && (
                <Metric label="Expected growth" value={preview.expected_growth} />
              )}
              {preview.budget_estimate && (
                <Metric label="Budget" value={preview.budget_estimate} />
              )}
            </div>
            <WhyExplanation>{preview.budget_estimate ? whyBudgetSplit(preview) : whyMetrics()}</WhyExplanation>
          </div>
        )}

        {/* Why */}
        {(preview.why_this_campaign || preview.why) && (
          <div>
            <div className="label-field mb-1">Why this campaign</div>
            <p className="text-sm text-text-secondary">{preview.why_this_campaign || preview.why}</p>
          </div>
        )}

        {/* Confidence */}
        {typeof preview.confidence === "number" && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-3">
              <div className="label-field">Confidence</div>
              <div className="flex-1 h-2 bg-border rounded-full overflow-hidden max-w-xs">
                <div className="h-full bg-accent rounded-full" style={{ width: `${preview.confidence}%` }} />
              </div>
              <span className="font-mono text-sm text-text">{preview.confidence}%</span>
            </div>
            <WhyExplanation>{whyConfidence()}</WhyExplanation>
          </div>
        )}

        {/* Risks */}
        {preview.risks && preview.risks.length > 0 && (
          <div>
            <div className="label-field mb-1">Risks</div>
            <WhyExplanation>{whyRisks()}</WhyExplanation>
            <ul className="space-y-1 mt-2">
              {preview.risks.map((risk, i) => (
                <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                  <AlertCircle className="w-3.5 h-3.5 text-warning mt-0.5 shrink-0" />
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Alternative */}
        {preview.alternative && (
          <div>
            <div className="label-field mb-1">If this doesn&apos;t work</div>
            <p className="text-sm text-text-secondary">{preview.alternative}</p>
            <WhyExplanation>{whyAlternative()}</WhyExplanation>
          </div>
        )}
      </div>

      {/* Actions — Next actions */}
      <div className="space-y-1.5">
        <WhyExplanation>{whyActions()}</WhyExplanation>
        <div className="flex gap-3 justify-end">
          <button onClick={onRegenerate} disabled={generating} className="btn-ghost">
            Regenerate
          </button>
          <button onClick={onApprove} className="btn-primary group">
            Approve &amp; start
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass rounded-xl p-3">
      <div className="label-field">{label}</div>
      <div className="text-sm text-text mt-1">{value}</div>
    </div>
  );
}

// ─── CreativeDirections (3 directions, tabbed layout) ─────────────────────

function CreativeDirections({
  directions,
  why,
  prominent,
}: {
  directions: CreativeDirection[];
  why?: string;
  prominent?: boolean;
}) {
  const [active, setActive] = useState(0);
  const dir = directions[active];
  if (!dir) return null;
  return (
    <div className={cn("space-y-3", prominent && "glass-strong rounded-2xl p-5 border-l-2 border-l-accent/60")}>
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className={cn("text-accent", prominent ? "w-4 h-4" : "w-3.5 h-3.5")} />
        <span className={prominent ? "text-text-secondary" : ""}>3 creative directions</span>
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      {/* Tabs */}
      <div className="flex gap-2 flex-wrap">
        {directions.map((d, i) => (
          <button
            key={d.id}
            onClick={() => setActive(i)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-mono transition-colors",
              i === active
                ? "bg-accent text-white"
                : "glass text-text-secondary hover:text-text"
            )}
          >
            {d.id.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Active direction card */}
      <div className={cn("rounded-xl p-4 space-y-3", prominent ? "glass-strong" : "glass")}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="label-field mb-1">Hook</div>
            <p className="text-sm text-text">{dir.hook}</p>
          </div>
          {dir.tone && (
            <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono bg-accent/10 text-accent">
              {dir.tone}
            </span>
          )}
        </div>

        <div>
          <div className="label-field mb-1">Angle</div>
          <p className="text-sm text-text-secondary">{dir.angle}</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="glass rounded-lg p-3">
            <div className="label-field mb-1">Sample headline</div>
            <p className="text-sm text-text">{dir.sample_headline}</p>
          </div>
          <div className="glass rounded-lg p-3">
            <div className="label-field mb-1">Sample CTA</div>
            <p className="text-sm text-text">{dir.sample_cta}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── HookPatterns (5 hooks, list layout) ──────────────────────────────────

const HOOK_PATTERN_STYLES: Record<string, string> = {
  question: "bg-blue-500/10 text-blue-400",
  stat: "bg-emerald-500/10 text-emerald-400",
  story: "bg-purple-500/10 text-purple-400",
  contrarian: "bg-orange-500/10 text-orange-400",
  aspiration: "bg-pink-500/10 text-pink-400",
};

function HookPatterns({
  hooks,
  why,
  prominent,
}: {
  hooks: Hook[];
  why?: string;
  prominent?: boolean;
}) {
  return (
    <div className={cn("space-y-3", prominent && "glass-strong rounded-2xl p-5 border-l-2 border-l-accent/60")}>
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className={cn("text-accent", prominent ? "w-4 h-4" : "w-3.5 h-3.5")} />
        <span className={prominent ? "text-text-secondary" : ""}>5 hook patterns</span>
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {hooks.map((hook, i) => {
          const badgeStyle =
            HOOK_PATTERN_STYLES[hook.pattern] || "bg-accent/10 text-accent";
          return (
            <div key={i} className={cn("rounded-xl p-4 space-y-2", prominent ? "glass-strong" : "glass")}>
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono capitalize",
                    badgeStyle
                  )}
                >
                  {hook.pattern}
                </span>
                <p className="text-sm text-text flex-1">{hook.copy}</p>
              </div>
              {hook.why_it_works && (
                <p className="text-xs text-text-muted pl-1">
                  <span className="text-text-secondary">Why it works: </span>
                  {hook.why_it_works}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── AudiencePsychologySection (motivations, objections, triggers, decision style) ─

function AudiencePsychologySection({ psychology, why }: { psychology: AudiencePsychology; why?: string }) {
  const hasMotivations = psychology.motivations && psychology.motivations.length > 0;
  const hasObjections = psychology.objections && psychology.objections.length > 0;
  const hasTriggers = psychology.emotional_triggers && psychology.emotional_triggers.length > 0;
  const hasDecisionStyle = Boolean(psychology.decision_style);
  if (!hasMotivations && !hasObjections && !hasTriggers && !hasDecisionStyle) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        Audience psychology
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="glass rounded-xl p-4 space-y-4">
        {/* Motivations + Objections (2 columns) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {hasMotivations && (
            <div>
              <div className="label-field mb-2">Top motivations</div>
              <ul className="space-y-1.5">
                {psychology.motivations.map((m, i) => (
                  <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-success mt-2 shrink-0" />
                    {m}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasObjections && (
            <div>
              <div className="label-field mb-2">Top objections</div>
              <ul className="space-y-1.5">
                {psychology.objections.map((o, i) => (
                  <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2 shrink-0" />
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Emotional triggers */}
        {hasTriggers && (
          <div>
            <div className="label-field mb-2">Emotional triggers</div>
            <div className="flex flex-wrap gap-2">
              {psychology.emotional_triggers.map((t, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-mono bg-accent/10 text-accent"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Decision style */}
        {hasDecisionStyle && (
          <div className="flex items-center gap-3">
            <div className="label-field shrink-0">Decision style</div>
            <p className="text-sm text-text-secondary">{psychology.decision_style}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── OfferSection (3 engineered offers with structure, copy, lever, lift) ──

const OFFER_STRUCTURE_STYLES: Record<string, string> = {
  anchoring: "bg-blue-500/10 text-blue-400",
  scarcity: "bg-red-500/10 text-red-400",
  bundling: "bg-emerald-500/10 text-emerald-400",
  "loss-aversion": "bg-orange-500/10 text-orange-400",
  "loss_aversion": "bg-orange-500/10 text-orange-400",
  "decoy pricing": "bg-purple-500/10 text-purple-400",
  "decoy_pricing": "bg-purple-500/10 text-purple-400",
};

function OfferSection({ offers, why }: { offers: Offer[]; why?: string }) {
  const validOffers = offers.filter((o) => o.copy || o.structure);
  if (validOffers.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        3 engineered offers
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {offers.map((offer, i) => {
          const badgeStyle =
            OFFER_STRUCTURE_STYLES[offer.structure.toLowerCase()] ||
            "bg-accent/10 text-accent";
          const lift = offer.expected_conversion_lift.toLowerCase();
          const liftColor =
            lift.includes("high") || lift.includes("30") || lift.includes("40") || lift.includes("50")
              ? "text-success bg-success/10"
              : lift.includes("medium") || lift.includes("15") || lift.includes("20") || lift.includes("25")
                ? "text-warning bg-warning/10"
                : "text-text-muted bg-border/30";
          return (
            <div key={i} className="glass rounded-xl p-4 space-y-2">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono capitalize",
                    badgeStyle
                  )}
                >
                  {offer.structure.replace(/_/g, " ")}
                </span>
                <p className="text-sm text-text flex-1">{offer.copy}</p>
              </div>
              {offer.psychology_lever && (
                <p className="text-xs text-text-muted pl-1">
                  <span className="text-text-secondary">Why it works: </span>
                  {offer.psychology_lever}
                </p>
              )}
              {offer.expected_conversion_lift && (
                <div className="pl-1">
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono",
                      liftColor
                    )}
                  >
                    Expected lift: {offer.expected_conversion_lift}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PricingPsychologySection (3 pricing presentations with technique, copy, rationale) ──

const PRICING_TECHNIQUE_STYLES: Record<string, string> = {
  charm: "bg-blue-500/10 text-blue-400",
  tier: "bg-emerald-500/10 text-emerald-400",
  bundle: "bg-purple-500/10 text-purple-400",
  anchor: "bg-orange-500/10 text-orange-400",
  loss_leader: "bg-red-500/10 text-red-400",
  "loss-leader": "bg-red-500/10 text-red-400",
};

function PricingPsychologySection({ presentations, why }: { presentations: PricingPresentation[]; why?: string }) {
  const valid = presentations.filter((p) => p.copy || p.technique);
  if (valid.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        3 pricing presentations
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {presentations.map((pres, i) => {
          const badgeStyle =
            PRICING_TECHNIQUE_STYLES[pres.technique.toLowerCase()] ||
            "bg-accent/10 text-accent";
          return (
            <div key={i} className="glass rounded-xl p-4 space-y-2">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono capitalize",
                    badgeStyle
                  )}
                >
                  {pres.technique.replace(/_/g, " ")}
                </span>
                <p className="text-sm text-text flex-1">{pres.copy}</p>
              </div>
              {pres.rationale && (
                <p className="text-xs text-text-muted pl-1">
                  <span className="text-text-secondary">Why it works: </span>
                  {pres.rationale}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── SeasonalIdeasSection (seasonal ideas with month, occasion, idea, copy) ──

function SeasonalIdeasSection({
  ideas,
  why,
  prominent,
}: {
  ideas: SeasonalIdea[];
  why?: string;
  prominent?: boolean;
}) {
  if (ideas.length === 0) return null;

  return (
    <div className={cn("space-y-3", prominent && "glass-strong rounded-2xl p-5 border-l-2 border-l-accent/60")}>
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Clock className={cn("text-accent", prominent ? "w-4 h-4" : "w-3.5 h-3.5")} />
        <span className={prominent ? "text-text-secondary" : ""}>Seasonal ideas</span>
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {ideas.map((idea, i) => (
          <div key={i} className={cn("rounded-xl p-4 space-y-2", prominent ? "glass-strong" : "glass")}>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono bg-accent/10 text-accent">
                {idea.month}
              </span>
              {idea.occasion && (
                <span className="text-xs text-text-secondary font-mono">
                  {idea.occasion}
                </span>
              )}
            </div>
            {idea.idea && (
              <p className="text-sm text-text-secondary">{idea.idea}</p>
            )}
            {idea.copy && (
              <p className="text-sm text-text pl-1 border-l-2 border-l-accent/30">
                {idea.copy}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── LocalIdeasSection (local marketing ideas with type, idea, copy) ──────

const LOCAL_TYPE_STYLES: Record<string, string> = {
  event: "bg-blue-500/10 text-blue-400",
  partnership: "bg-emerald-500/10 text-emerald-400",
  geo_target: "bg-purple-500/10 text-purple-400",
  "geo-target": "bg-purple-500/10 text-purple-400",
  seo: "bg-orange-500/10 text-orange-400",
};

function LocalIdeasSection({ ideas, why }: { ideas: LocalIdea[]; why?: string }) {
  if (ideas.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Target className="w-3.5 h-3.5 text-accent" />
        Local marketing ideas
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {ideas.map((idea, i) => {
          const badgeStyle =
            LOCAL_TYPE_STYLES[idea.type.toLowerCase()] ||
            "bg-accent/10 text-accent";
          return (
            <div key={i} className="glass rounded-xl p-4 space-y-2">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono capitalize",
                    badgeStyle
                  )}
                >
                  {idea.type.replace(/_/g, " ")}
                </span>
                <p className="text-sm text-text-secondary flex-1">{idea.idea}</p>
              </div>
              {idea.copy && (
                <p className="text-sm text-text pl-1 border-l-2 border-l-accent/30">
                  {idea.copy}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── DifferentiationSection (competitor differentiation matrix) ───────────

function DifferentiationSection({ entries, why }: { entries: DifferentiationEntry[]; why?: string }) {
  const valid = entries.filter((e) => e.competitor_claim || e.our_counter);
  if (valid.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <TrendingUp className="w-3.5 h-3.5 text-accent" />
        Differentiation matrix
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="space-y-2">
        {entries.map((entry, i) => (
          <div key={i} className="glass rounded-xl p-4 space-y-3">
            {/* Competitor claim */}
            <div className="flex items-start gap-3">
              <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono bg-warning/10 text-warning">
                Competitor
              </span>
              <p className="text-sm text-text-secondary flex-1">{entry.competitor_claim}</p>
            </div>

            {/* Our counter */}
            <div className="flex items-start gap-3 pl-4">
              <ArrowRight className="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <p className="text-sm text-text">{entry.our_counter}</p>
                {entry.evidence && (
                  <p className="text-xs text-text-muted">
                    <span className="text-text-secondary">Evidence: </span>
                    {entry.evidence}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── ABConceptsSection (A/B concept variants grid) ────────────────────────

function ABConceptsSection({ concepts, why }: { concepts: ABConcept[]; why?: string }) {
  if (!concepts || concepts.length === 0) return null;

  // Group concepts by direction_id (each direction has A and B variants)
  const byDirection = new Map<string, ABConcept[]>();
  for (const concept of concepts) {
    const existing = byDirection.get(concept.direction_id) || [];
    existing.push(concept);
    byDirection.set(concept.direction_id, existing);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        A/B concept variants
      </div>
      <WhyExplanation>{why}</WhyExplanation>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {Array.from(byDirection.entries()).map(([dirId, variants]) => (
          <div key={dirId} className="glass rounded-xl p-4 space-y-3">
            <div className="text-xs font-mono text-text-muted uppercase tracking-wider">
              {dirId}
            </div>
            {variants
              .sort((a, b) => a.variant_label.localeCompare(b.variant_label))
              .map((concept, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border/50 p-3 space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono",
                        concept.variant_label === "A"
                          ? "bg-accent/10 text-accent"
                          : "bg-info/10 text-info"
                      )}
                    >
                      Variant {concept.variant_label}
                    </span>
                  </div>

                  {concept.hook && (
                    <p className="text-sm font-medium text-text">{concept.hook}</p>
                  )}
                  {concept.headline && (
                    <p className="text-sm text-text-secondary italic">
                      &ldquo;{concept.headline}&rdquo;
                    </p>
                  )}
                  {concept.cta && (
                    <p className="text-xs text-text-muted">
                      <span className="text-text-secondary">CTA: </span>
                      {concept.cta}
                    </p>
                  )}
                  {concept.what_changed && (
                    <p className="text-xs text-text-muted">
                      <span className="text-text-secondary">What changed: </span>
                      {concept.what_changed}
                    </p>
                  )}
                  {concept.why && (
                    <p className="text-xs text-text-muted">
                      <span className="text-text-secondary">Why: </span>
                      {concept.why}
                    </p>
                  )}
                  {concept.expected_audience_segment && (
                    <p className="text-xs text-text-muted">
                      <span className="text-text-secondary">Segment: </span>
                      {concept.expected_audience_segment}
                    </p>
                  )}
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Domain presentation configs (one per domain, drives the components) ───

export const BUSINESS_PRESENTATION: DomainPresentationConfig = {
  understandingLabel: "business",
  opportunitiesLabel: "growth_opportunities",
  planLabel: "plan",
  showMaturity: true,
  understandingSections: [
    { title: "Your strengths", items: [], accent: "success", icon: "check" },
    { title: "Where you can improve", items: [], accent: "warning", icon: "alert" },
    { title: "Your likely customers", items: [], accent: "info", icon: "target" },
    { title: "Your competitors", items: [], accent: "danger", icon: "trend" },
  ],
  weekFields: [
    { key: "objectives", label: "Objectives", kind: "list" },
    { key: "content", label: "Content", kind: "list" },
    { key: "offers", label: "Offers", kind: "list" },
    { key: "channels", label: "Channels", kind: "list" },
    { key: "kpis", label: "KPIs", kind: "list" },
  ],
};

export const CREATOR_PRESENTATION: DomainPresentationConfig = {
  understandingLabel: "creator",
  opportunitiesLabel: "growth_opportunities",
  planLabel: "plan",
  showMaturity: true,
  understandingSections: [
    { title: "strengths", items: [], accent: "success", icon: "check" },
    { title: "weaknesses", items: [], accent: "warning", icon: "alert" },
    { title: "growth_opportunities", items: [], accent: "info", icon: "target" },
    { title: "content_gaps", items: [], accent: "danger", icon: "trend" },
  ],
  weekFields: [
    { key: "videos", label: "Videos", kind: "list" },
    { key: "shorts", label: "Shorts", kind: "list" },
    { key: "community_posts", label: "Community posts", kind: "list" },
    { key: "collaborations", label: "Collaborations", kind: "list" },
    { key: "seo", label: "SEO", kind: "list" },
    { key: "newsletter", label: "Newsletter", kind: "text" },
    { key: "live_sessions", label: "Live sessions", kind: "text" },
    { key: "kpis", label: "KPIs", kind: "list" },
  ],
};

/**
 * Get the presentation config for a domain.
 * Adding a new domain: add its config here (or fetch from the backend /consult/nav endpoint).
 */
export function getPresentationConfig(domain: string): DomainPresentationConfig {
  if (domain === "creator") return CREATOR_PRESENTATION;
  // business, restaurant, clinic, and all future business subtypes use the business config
  return BUSINESS_PRESENTATION;
}
