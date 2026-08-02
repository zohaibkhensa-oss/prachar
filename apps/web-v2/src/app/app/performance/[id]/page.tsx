"use client";

/**
 * Performance Story — `/app/performance/{id}`
 *
 * Leads with a NARRATIVE story (headline, paragraphs, highlights), not a
 * dashboard. The metrics grid and chart are supporting evidence at the
 * bottom under "Here's the data behind this story."
 *
 * Sections:
 *  1. The Story — large headline, narrative paragraphs, highlight callouts.
 *  2. Platform breakdown — simple bar visualization (if multi-channel).
 *  3. "Here's the data behind this story" — metrics grid + chart (collapsed).
 *  4. Why this happened — likely causes (existing, secondary).
 *  5. What to do next — recommendations (existing, secondary).
 *
 * All metrics are de-jargonised:
 *   ROAS → "Revenue per ₹100 spent", CPA → "Cost per new customer",
 *   CTR → "Click rate", Conversions → "New customers / enquiries".
 */
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  HelpCircle,
  Lightbulb,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Calendar,
  Target,
  Zap,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react";
import {
  performanceApi,
  isNotFound,
  type PerformanceSummary,
  type PerformanceStory,
  type LikelyCause,
  type Recommendation,
  type TopMetrics,
} from "@/lib/performance";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricsChart } from "@/components/performance/MetricsChart";

// ─── Page ─────────────────────────────────────────────────────────────────

export default function PerformancePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  // ─── Data ──────────────────────────────────────────────────────────────
  const {
    data: story,
    isLoading: storyLoading,
    error: storyError,
  } = useQuery<PerformanceStory>({
    queryKey: ["performance-story", id],
    queryFn: () => performanceApi.getStory(id),
    enabled: !!id,
    retry: 1,
  });

  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useQuery<PerformanceSummary>({
    queryKey: ["performance-summary", id],
    queryFn: () => performanceApi.getSummary(id),
    enabled: !!id,
    retry: 1,
  });

  const {
    data: whyData,
    isLoading: whyLoading,
    error: whyError,
  } = useQuery<{ likely_causes: LikelyCause[] }>({
    queryKey: ["performance-why", id],
    queryFn: () => performanceApi.getWhy(id),
    enabled: !!id,
    retry: 1,
  });

  const {
    data: nextData,
    isLoading: nextLoading,
    error: nextError,
  } = useQuery<{ recommendations: Recommendation[] }>({
    queryKey: ["performance-next", id],
    queryFn: () => performanceApi.getNext(id),
    enabled: !!id,
    retry: 1,
  });

  // ─── Apply toast ───────────────────────────────────────────────────────
  const [toast, setToast] = useState<string | null>(null);
  const [showData, setShowData] = useState(false);

  function handleApply(rec: Recommendation) {
    // Acknowledge the recommendation — no fake "coming soon" message.
    setToast(`Recommendation noted: "${rec.action}"`);
    window.setTimeout(() => setToast(null), 3000);
  }

  // ─── Loading ───────────────────────────────────────────────────────────
  if (storyLoading && summaryLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40 rounded-lg" />
        <Skeleton className="h-16 w-full rounded-2xl" />
        <Skeleton className="h-24 rounded-2xl" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  // ─── Error / not found ─────────────────────────────────────────────────
  if ((storyError || summaryError) && !story && !summary) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <AlertCircle className="w-10 h-10 text-danger mx-auto mb-3" />
        <h2 className="font-display text-lg font-semibold text-text mb-1">
          Performance data unavailable
        </h2>
        <p className="text-sm text-text-secondary mb-6">
          {(storyError as Error)?.message ??
            (summaryError as Error)?.message ??
            "We couldn't load performance analysis for this campaign."}
        </p>
        <Link href="/app/analytics" className="btn-primary inline-flex">
          <ArrowLeft className="w-4 h-4" />
          Back to analytics
        </Link>
      </div>
    );
  }

  const metrics = summary?.top_metrics ?? {};
  const trend = summary?.trend ?? "flat";
  const notableDays = summary?.notable_days ?? [];
  const benchmarks = summary?.benchmark_comparison ?? {};
  const likelyCauses = whyData?.likely_causes ?? [];
  const recommendations = nextData?.recommendations ?? [];
  const whyMissing = isNotFound(whyError);
  const nextMissing = isNotFound(nextError);

  return (
    <div className="space-y-8 pb-12">
      {/* ─── Back link ─── */}
      <Link
        href="/app/analytics"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to analytics
      </Link>

      {/* ─── Section 1: The Story ─── */}
      <section className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
            <BookOpen className="w-6 h-6 text-accent" />
          </div>
          <div className="min-w-0">
            <h1 className="font-display text-2xl font-semibold text-text">
              Your Campaign Story
            </h1>
            <p className="text-xs text-text-muted mt-0.5 font-mono">
              Campaign {story?.campaign_id ?? summary?.campaign_id ?? id}
            </p>
          </div>
          {summary && (
            <div className="ml-auto">
              <TrendBadge trend={trend} />
            </div>
          )}
        </div>

        {/* Headline */}
        {story ? (
          <div className="glass-strong rounded-2xl p-6 md:p-8">
            <h2 className="font-display text-2xl md:text-3xl font-semibold text-text leading-tight">
              {story.headline}
            </h2>
          </div>
        ) : (
          <div className="glass-strong rounded-2xl p-6 md:p-8">
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        )}

        {/* Narrative paragraphs */}
        {story && story.paragraphs.length > 0 && (
          <div className="glass-strong rounded-2xl p-6 md:p-8 space-y-4">
            {story.paragraphs.map((p, i) => (
              <p
                key={i}
                className="text-base text-text leading-relaxed"
              >
                {p}
              </p>
            ))}
          </div>
        )}

        {/* Highlight callout cards */}
        {story && story.highlights.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {story.highlights.map((h, i) => (
              <HighlightCard
                key={i}
                metric={h.metric}
                value={h.value}
                insight={h.insight}
              />
            ))}
          </div>
        )}
      </section>

      {/* ─── Section 2: Platform breakdown ─── */}
      {story && story.platform_breakdown.length >= 2 && (
        <section className="space-y-5">
          <SectionTitle
            icon={<BarChart3 className="w-4 h-4" />}
            title="Where your enquiries came from"
            subtitle="Platform-by-platform breakdown"
          />
          <div className="glass-strong rounded-2xl p-6 space-y-4">
            {story.platform_breakdown.map((p, i) => (
              <PlatformBar
                key={i}
                platform={p.platform}
                share={p.share}
                conversionRate={p.conversion_rate}
                conversions={p.conversions}
              />
            ))}
          </div>
        </section>
      )}

      {/* ─── Section 3: Supporting data (collapsed by default) ─── */}
      <section className="space-y-4">
        <button
          type="button"
          onClick={() => setShowData((v) => !v)}
          aria-expanded={showData}
          className="w-full flex items-center gap-3 text-left group"
        >
          <div className="w-8 h-8 rounded-lg bg-white/[0.03] flex items-center justify-center text-text-muted group-hover:bg-white/[0.05] transition-colors">
            <BarChart3 className="w-3.5 h-3.5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-display text-base font-semibold text-text-secondary">
                Supporting data
              </h2>
              <span className="text-[10px] uppercase tracking-wider font-medium text-text-muted bg-white/[0.04] px-1.5 py-0.5 rounded">
                Evidence
              </span>
            </div>
            <p className="text-xs text-text-muted mt-0.5">
              The full metrics, chart, and benchmarks behind the story
            </p>
          </div>
          <span className="text-xs font-medium text-text-muted group-hover:text-text-secondary transition-colors shrink-0">
            {showData ? "Hide the data" : "Show the data"}
          </span>
          {showData ? (
            <ChevronUp className="w-4 h-4 text-text-muted shrink-0" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-muted shrink-0" />
          )}
        </button>

        {showData && (
          <div className="space-y-4 animate-in fade-in duration-200 border-t border-white/[0.04] pt-4">
            {/* Top metrics grid — de-jargonised */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MetricCard
                label="People reached"
                value={fmtNumber(metrics.impressions)}
                icon={<Target className="w-4 h-4" />}
              />
              <MetricCard
                label="Clicks"
                value={fmtNumber(metrics.clicks)}
                icon={<Zap className="w-4 h-4" />}
              />
              <MetricCard
                label="New customers"
                value={fmtNumber(metrics.conversions)}
                icon={<CheckCircle2 className="w-4 h-4" />}
                accent="success"
              />
              <MetricCard
                label="Spend"
                value={fmtMoney(metrics.spend)}
                icon={<TrendingDown className="w-4 h-4" />}
              />
              <MetricCard
                label="Revenue"
                value={fmtMoney(metrics.revenue)}
                icon={<TrendingUp className="w-4 h-4" />}
                accent="success"
              />
              <MetricCard
                label="Click rate"
                value={fmtPercent(metrics.avg_ctr)}
                icon={<Zap className="w-4 h-4" />}
              />
              <MetricCard
                label="Cost per new customer"
                value={fmtMoney(metrics.avg_cpa)}
                icon={<TrendingDown className="w-4 h-4" />}
                accent="danger"
              />
              <MetricCard
                label="Revenue per ₹100 spent"
                value={fmtRoas(metrics.avg_roas)}
                icon={<TrendingUp className="w-4 h-4" />}
                accent="success"
              />
            </div>

            {/* Chart + notable days — compact, supporting evidence */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <BarChart3 className="w-3.5 h-3.5 text-text-muted" />
                  <h3 className="font-display text-xs font-semibold text-text-secondary">
                    Notable days
                  </h3>
                  <span className="text-[11px] text-text-muted ml-auto">
                    Days with &gt;20% metric deviation
                  </span>
                </div>
                <MetricsChart data={notableDays} height={180} />
              </div>

              {/* Notable days list */}
              <div className="glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Calendar className="w-3.5 h-3.5 text-text-muted" />
                  <h3 className="font-display text-xs font-semibold text-text-secondary">
                    Notable events
                  </h3>
                </div>
                {notableDays.length === 0 ? (
                  <p className="text-sm text-text-muted py-6 text-center">
                    No notable spikes or drops detected.
                  </p>
                ) : (
                  <ul className="space-y-3 max-h-72 overflow-y-auto pr-1">
                    {notableDays.map((d, i) => (
                      <li
                        key={`${d.date}-${d.metric}-${i}`}
                        className="flex items-start gap-3 text-sm"
                      >
                        <span
                          className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
                            d.note.startsWith("spike")
                              ? "bg-success"
                              : d.note.startsWith("drop")
                                ? "bg-danger"
                                : "bg-accent"
                          }`}
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-text-muted">
                              {d.date}
                            </span>
                            <span className="text-xs capitalize text-text-secondary">
                              {d.metric}
                            </span>
                          </div>
                          <p className="text-xs text-text-secondary mt-0.5">
                            {d.note} · {fmtNumber(d.value)}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Benchmark comparison */}
            {Object.keys(benchmarks).length > 0 && (
              <div className="glass rounded-xl p-4">
                <h3 className="font-display text-xs font-semibold text-text-secondary mb-3">
                  Benchmark comparison
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {Object.entries(benchmarks).map(([metric, b]) => (
                    <BenchmarkRow key={metric} metric={metric} entry={b} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ─── Section 4: Why this happened ─── */}
      <section className="space-y-5">
        <SectionTitle
          icon={<HelpCircle className="w-4 h-4" />}
          title="Why this happened"
          subtitle="Likely causes backed by evidence"
        />

        {whyLoading ? (
          <div className="glass-strong rounded-2xl p-6 space-y-3">
            <Skeleton className="h-5 w-3/4 rounded-lg" />
            <Skeleton className="h-4 w-1/2 rounded-lg" />
            <Skeleton className="h-4 w-2/3 rounded-lg" />
          </div>
        ) : whyMissing ? (
          <PendingCard
            title="Analysis in progress"
            description="The 'Why' analysis engine is running. Check back shortly for likely causes and evidence."
          />
        ) : whyError ? (
          <ErrorCard message={(whyError as Error).message} />
        ) : likelyCauses.length === 0 ? (
          <PendingCard
            title="No causes identified yet"
            description="The analysis didn't surface any likely causes for this campaign's performance."
          />
        ) : (
          <ul className="space-y-3">
            {likelyCauses.map((c, i) => (
              <li
                key={i}
                className="glass-strong rounded-2xl p-5 flex items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text">{c.cause}</p>
                  {c.evidence && (
                    <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
                      {c.evidence}
                    </p>
                  )}
                </div>
                <ConfidenceBadge confidence={c.confidence} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ─── Section 5: What to do next ─── */}
      <section className="space-y-5">
        <SectionTitle
          icon={<Lightbulb className="w-4 h-4" />}
          title="What to do next"
          subtitle="Recommended actions to improve performance"
        />

        {nextLoading ? (
          <div className="glass-strong rounded-2xl p-6 space-y-3">
            <Skeleton className="h-5 w-2/3 rounded-lg" />
            <Skeleton className="h-4 w-1/2 rounded-lg" />
          </div>
        ) : nextMissing ? (
          <PendingCard
            title="Recommendations coming soon"
            description="The 'What next' recommendation engine is preparing suggestions for this campaign."
          />
        ) : nextError ? (
          <ErrorCard message={(nextError as Error).message} />
        ) : recommendations.length === 0 ? (
          <PendingCard
            title="No recommendations yet"
            description="There are no recommended actions at this time. The engine may still be analysing your campaign."
          />
        ) : (
          <ul className="space-y-3">
            {recommendations.map((r, i) => (
              <li
                key={i}
                className="glass-strong rounded-2xl p-5 flex flex-col sm:flex-row sm:items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text">{r.action}</p>
                  {r.expected_impact && (
                    <p className="text-xs text-text-secondary mt-1.5">
                      <span className="text-text-muted">Expected impact: </span>
                      {r.expected_impact}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <PriorityBadge priority={r.priority} />
                  <button
                    type="button"
                    onClick={() => handleApply(r)}
                    className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-text-secondary hover:text-text transition-colors"
                    title="Note this recommendation"
                  >
                    Note
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ─── Toast ─── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-sm">
          <div className="glass-strong rounded-xl p-4 shadow-lg border border-accent/20 flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-success shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-text whitespace-pre-line">{toast}</p>
            </div>
            <button
              type="button"
              onClick={() => setToast(null)}
              className="text-text-muted hover:text-text text-xs"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────

function SectionTitle({
  icon,
  title,
  subtitle,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary">
        {icon}
      </div>
      <div>
        <h2 className="font-display text-xl font-semibold text-text">{title}</h2>
        {subtitle && (
          <p className="text-xs text-text-secondary mt-0.5">{subtitle}</p>
        )}
      </div>
    </div>
  );
}

function HighlightCard({
  metric,
  value,
  insight,
}: {
  metric: string;
  value: string;
  insight: string;
}) {
  return (
    <div className="glass-strong rounded-xl p-4 border border-accent/10">
      <p className="label-field text-text-muted mb-1">{metric}</p>
      <p className="font-display text-2xl font-semibold text-text mb-1">
        {value}
      </p>
      <p className="text-xs text-text-secondary">{insight}</p>
    </div>
  );
}

function PlatformBar({
  platform,
  share,
  conversionRate,
  conversions,
}: {
  platform: string;
  share: number;
  conversionRate: number;
  conversions: number;
}) {
  const pct = Math.round(share * 100);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-text">{platform}</span>
        <span className="text-text-secondary">
          {pct}% · {conversions} enquiries · {(conversionRate * 100).toFixed(0)}% conversion
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-white/[0.04] overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  accent = "default",
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  accent?: "default" | "success" | "danger";
}) {
  const accentClass =
    accent === "success"
      ? "text-success"
      : accent === "danger"
        ? "text-danger"
        : "text-text";
  return (
    <div className="glass rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="label-field text-[11px]">{label}</span>
        <span className="text-text-muted">{icon}</span>
      </div>
      <p className={`font-display text-lg font-semibold ${accentClass}`}>
        {value}
      </p>
    </div>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const config: Record<
    string,
    { icon: React.ReactNode; class: string; label: string }
  > = {
    up: {
      icon: <TrendingUp className="w-3.5 h-3.5" />,
      class: "badge-success",
      label: "Trending up",
    },
    down: {
      icon: <TrendingDown className="w-3.5 h-3.5" />,
      class: "badge-danger",
      label: "Trending down",
    },
    flat: {
      icon: <Minus className="w-3.5 h-3.5" />,
      class: "badge-neutral",
      label: "Flat",
    },
  };
  const c = config[trend] ?? config.flat!;
  return (
    <span className={`badge ${c.class} inline-flex items-center gap-1.5`}>
      {c.icon}
      {c.label}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const map: Record<string, string> = {
    high: "badge-danger",
    medium: "badge-warning",
    low: "badge-neutral",
  };
  const cls = map[confidence] ?? "badge-neutral";
  return <span className={`badge ${cls} capitalize`}>{confidence}</span>;
}

function PriorityBadge({ priority }: { priority: string }) {
  const map: Record<string, string> = {
    high: "badge-danger",
    medium: "badge-warning",
    low: "badge-neutral",
  };
  const cls = map[priority] ?? "badge-neutral";
  return <span className={`badge ${cls} capitalize`}>{priority}</span>;
}

function BenchmarkRow({
  metric,
  entry,
}: {
  metric: string;
  entry: {
    actual: number;
    benchmark: number;
    difference: number;
    status: string;
  };
}) {
  const statusClass =
    entry.status === "better"
      ? "text-success"
      : entry.status === "worse"
        ? "text-danger"
        : "text-text-muted";
  const statusLabel =
    entry.status === "better"
      ? "Above benchmark"
      : entry.status === "worse"
        ? "Below benchmark"
        : "Unknown";
  // De-jargonise benchmark metric labels.
  const labelMap: Record<string, string> = {
    ctr: "Click rate",
    cpa: "Cost per new customer",
    roas: "Revenue per ₹100 spent",
  };
  const label = labelMap[metric] ?? metric.toUpperCase();
  return (
    <div className="rounded-xl bg-white/[0.02] border border-white/[0.04] p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="label-field uppercase">{label}</span>
        <span className={`text-xs font-medium ${statusClass}`}>
          {statusLabel}
        </span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-lg font-semibold text-text">
          {metric === "ctr"
            ? fmtPercent(entry.actual)
            : metric === "roas"
              ? fmtRoas(entry.actual)
              : fmtMoney(entry.actual)}
        </span>
        <span className="text-xs text-text-muted">
          vs {metric === "ctr" ? fmtPercent(entry.benchmark) : metric === "roas" ? fmtRoas(entry.benchmark) : fmtMoney(entry.benchmark)}
        </span>
      </div>
    </div>
  );
}

function PendingCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="glass-strong rounded-2xl p-8 flex flex-col items-center text-center max-w-md mx-auto">
      <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center mb-3">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
      </div>
      <h3 className="font-display text-base font-semibold text-text mb-1">
        {title}
      </h3>
      <p className="text-sm text-text-secondary">{description}</p>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="glass-strong rounded-2xl p-6 flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-danger shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium text-text">
          Couldn't load this section
        </p>
        <p className="text-xs text-text-secondary mt-1">{message}</p>
      </div>
    </div>
  );
}

// ─── Formatting helpers ───────────────────────────────────────────────────

function fmtNumber(v?: number): string {
  if (v === undefined || v === null) return "—";
  return new Intl.NumberFormat("en").format(v);
}

function fmtMoney(v?: number): string {
  if (v === undefined || v === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(v);
}

function fmtPercent(v?: number): string {
  if (v === undefined || v === null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function fmtRoas(v?: number): string {
  if (v === undefined || v === null) return "—";
  // De-jargonised: show as "₹{roas*100}" (revenue per ₹100 spent).
  return `₹${(v * 100).toFixed(0)}`;
}
