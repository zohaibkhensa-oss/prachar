"use client";

/**
 * Unified Dashboard Shell — ONE dashboard framework for ALL domains.
 *
 * The shell renders the common structure (greeting, today's action, approvals,
 * loading state). Domain-specific widgets (KPIs, quick actions, trending, etc.)
 * are supplied by the Domain Pack via the DomainConfig.
 *
 * Adding a new domain requires ZERO changes here. The domain pack config
 * drives the widgets.
 */
import { ReactNode } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import * as LucideIcons from "lucide-react";
import {
  ArrowRight,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Minus,
  Sparkles,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { Brand, CampaignPlan } from "@/lib/hooks";
import type {
  DomainConfig,
  KpiCardSpec,
  ActionCardSpec,
  WidgetSpec,
} from "@/lib/unified-consult";

// ─── Icon helper ──────────────────────────────────────────────────────────

function getIcon(name: string): LucideIcon {
  const icons = LucideIcons as unknown as Record<string, LucideIcon>;
  return icons[name] ?? (icons.LayoutDashboard as LucideIcon);
}

// ─── KPI Grid widget ──────────────────────────────────────────────────────

/**
 * Trend badge — shows up/down/flat/new with optional % change.
 * When no trend data is available, renders a graceful "connect channels" hint.
 */
function TrendBadge({ kpi, hasValue }: { kpi: KpiCardSpec; hasValue: boolean }) {
  // No trend data from backend → graceful fallback
  if (!kpi.trend_direction) {
    if (!hasValue) {
      return (
        <span className="inline-flex items-center gap-1 text-xs text-text-muted">
          <span className="w-1.5 h-1.5 rounded-full bg-text-muted/40" />
          Connect channels to see trends
        </span>
      );
    }
    // Has a value but no trend — show "new" if first time, otherwise just a neutral dot
    return (
      <span className="inline-flex items-center gap-1 text-xs text-text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-text-muted/40" />
        First snapshot
      </span>
    );
  }

  const trendConfig: Record<
    NonNullable<KpiCardSpec["trend_direction"]>,
    { icon: LucideIcon; className: string; label: string }
  > = {
    up: { icon: ArrowUpRight, className: "text-success", label: "up" },
    down: { icon: ArrowDownRight, className: "text-warning", label: "down" },
    flat: { icon: Minus, className: "text-text-muted", label: "flat" },
    new: { icon: Sparkles, className: "text-accent", label: "new" },
  };

  const cfg = trendConfig[kpi.trend_direction];
  const Icon = cfg.icon;
  const pctLabel =
    kpi.trend_pct != null ? ` ${kpi.trend_pct > 0 ? "+" : ""}${kpi.trend_pct}%` : "";

  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", cfg.className)}>
      <Icon className="w-3 h-3" />
      {kpi.trend_direction === "new" ? "New" : `${cfg.label}${pctLabel}`}
    </span>
  );
}

export function KpiGrid({ kpis, values }: { kpis: KpiCardSpec[]; values?: Record<string, string> }) {
  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {kpis.map((kpi) => {
          const Icon = getIcon(kpi.icon);
          const value = values?.[kpi.key] ?? "—";
          const hasValue = value !== "—" && value !== "";
          const context = kpi.context ?? kpi.hint;
          const seeWhyHref = kpi.see_why_href ?? (hasValue ? "/app/analytics" : null);
          return (
            <div key={kpi.key} className="glass rounded-2xl p-4 flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Icon className="w-4 h-4 text-accent" />
                </div>
              </div>
              <div className="text-2xl font-display font-semibold text-text tabular-nums">{value}</div>
              <div className="text-xs text-text-muted mt-1">{kpi.label}</div>
              {/* Trend indicator */}
              <div className="mt-1.5">
                <TrendBadge kpi={kpi} hasValue={hasValue} />
              </div>
              {/* Context line — explains what the number means */}
              <div className="text-xs text-text-secondary mt-1.5 leading-relaxed flex-1">
                {context}
              </div>
              {/* "See why" link — only if actionable */}
              {seeWhyHref && (
                <Link
                  href={seeWhyHref}
                  className="inline-flex items-center gap-0.5 text-xs text-accent mt-2 hover:underline w-fit"
                >
                  See why
                  <ArrowRight className="w-3 h-3" />
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Quick Actions widget ─────────────────────────────────────────────────

export function QuickActions({ actions, brandId }: { actions: ActionCardSpec[]; brandId?: string }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {actions.map((action, i) => {
        const Icon = getIcon(action.icon);
        const href = action.href.replace("{brand_id}", brandId || "");
        const accentClass =
          action.accent === "info"
            ? "border-l-info/50"
            : action.accent === "success"
              ? "border-l-success/50"
              : action.accent === "warning"
                ? "border-l-warning/50"
                : "border-l-accent/50";
        return (
          <Link
            key={i}
            href={href}
            className={cn(
              "glass rounded-2xl p-5 border-l-2 hover:border-l-accent transition-all group",
              accentClass,
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <Icon className="w-5 h-5 text-accent" />
              </div>
              <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
            </div>
            <div className="text-base font-medium text-text">{action.title}</div>
            <div className="text-sm text-text-secondary mt-1">{action.description}</div>
          </Link>
        );
      })}
    </div>
  );
}

// ─── Today's Action (common dashboard element — shared across all domains) ─

export function TodaysAction({
  brand,
  hasCampaigns,
  pendingCount,
  domainLabel,
}: {
  brand: Brand;
  hasCampaigns: boolean;
  pendingCount: number;
  domainLabel: string;
}) {
  let title = `Set up your ${domainLabel.toLowerCase()}`;
  let desc = `Tell me about your ${domainLabel.toLowerCase()} and I'll build your first campaign.`;
  let cta = "Start";
  let href = "/onboarding";

  if (pendingCount > 0) {
    title = "Review your campaign";
    desc = `You have ${pendingCount} campaign${pendingCount > 1 ? "s" : ""} waiting for your approval.`;
    cta = "Review now";
    href = "/app/campaigns";
  } else if (hasCampaigns) {
    title = "Check this week's performance";
    desc = "Your campaigns are running. See what's working and what to adjust.";
    cta = "View results";
    href = "/app/analytics";
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono mb-2">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            Today&apos;s recommended action
          </div>
          <div className="text-xl font-display font-semibold text-text">{title}</div>
          <div className="text-sm text-text-secondary mt-1">{desc}</div>
        </div>
        <Link href={href} className="btn-primary group shrink-0">
          {cta}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </motion.div>
  );
}

// ─── Approvals (common dashboard element — shared across all domains) ─────

export function Approvals({ pendingPlans }: { pendingPlans: CampaignPlan[] }) {
  if (pendingPlans.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <CheckCircle2 className="w-4 h-4 text-warning" />
        <h2 className="font-display text-base font-semibold text-text">Waiting for your approval</h2>
      </div>
      <div className="space-y-2">
        {pendingPlans.map((plan) => (
          <Link
            key={plan.id}
            href={`/app/campaigns/${plan.id}`}
            className="glass rounded-xl p-4 flex items-center justify-between hover:border-accent/30 transition-all group"
          >
            <div>
              <div className="text-sm font-medium text-text">{plan.name}</div>
              <div className="text-xs text-text-muted mt-0.5">{plan.goal}</div>
            </div>
            <div className="flex items-center gap-2 text-text-muted group-hover:text-accent">
              <span className="text-xs">Review</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ─── Loading state (shared) ───────────────────────────────────────────────

export function DashboardLoading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      {/* Greeting skeleton — matches h1 + subtitle */}
      <div className="space-y-2">
        <Skeleton className="h-9 w-48 rounded-lg" />
        <Skeleton className="h-4 w-64 rounded-md" />
      </div>

      {/* Today's action skeleton — matches the glass-strong banner */}
      <Skeleton className="h-24 rounded-2xl" />

      {/* KPI grid skeleton — 4 cards matching the actual grid */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-40 rounded-md" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass rounded-2xl p-4 flex flex-col gap-2">
              <Skeleton className="h-9 w-9 rounded-lg" />
              <Skeleton className="h-7 w-20 rounded-md" />
              <Skeleton className="h-3 w-16 rounded-sm" />
              <Skeleton className="h-3 w-12 rounded-sm" />
              <Skeleton className="h-8 w-full rounded-sm mt-1" />
            </div>
          ))}
        </div>
      </div>

      {/* Quick actions skeleton — 3 cards matching the actions grid */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-40 rounded-md" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="glass rounded-2xl p-5 flex flex-col gap-2">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <Skeleton className="h-4 w-32 rounded-md" />
              <Skeleton className="h-3 w-full rounded-sm" />
              <Skeleton className="h-3 w-24 rounded-sm" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── The Shell ────────────────────────────────────────────────────────────

export interface DashboardShellProps {
  brand: Brand;
  plans: CampaignPlan[] | undefined;
  config: DomainConfig;
  /** Optional extra widgets rendered after the standard ones. */
  extraWidgets?: ReactNode;
  /** Optional KPI values (e.g. from platform API connections). */
  kpiValues?: Record<string, string>;
}

/**
 * The unified dashboard shell. Renders the common structure + domain-supplied
 * widgets. Adding a new domain = supplying a new DomainConfig. No shell changes.
 */
export function DashboardShell({
  brand,
  plans,
  config,
  extraWidgets,
  kpiValues,
}: DashboardShellProps) {
  if (!plans) {
    return <DashboardLoading />;
  }

  const activePlans = plans.filter((p) => p.status === "active" || p.status === "approved");
  const pendingPlans = plans.filter((p) => p.status === "pending" || p.status === "draft");
  const hasCampaigns = activePlans.length + pendingPlans.length > 0;

  // Render widgets in the order specified by the domain pack
  const renderWidget = (widget: WidgetSpec, index: number): ReactNode | null => {
    switch (widget.kind) {
      case "kpi_grid":
        return (
          <section key={index}>
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-accent" />
              <h2 className="font-display text-base font-semibold text-text">{widget.title}</h2>
            </div>
            <KpiGrid kpis={config.kpi_cards} values={kpiValues} />
          </section>
        );
      case "quick_actions":
        return (
          <section key={index}>
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-accent" />
              <h2 className="font-display text-base font-semibold text-text">{widget.title}</h2>
            </div>
            <QuickActions actions={config.quick_actions} brandId={brand.id} />
          </section>
        );
      case "approvals":
        return pendingPlans.length > 0 ? (
          <section key={index}>
            <Approvals pendingPlans={pendingPlans} />
          </section>
        ) : null;
      case "pipeline":
        return hasCampaigns ? (
          <section key={index}>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="w-4 h-4 text-accent" />
              <h2 className="font-display text-base font-semibold text-text">{widget.title}</h2>
            </div>
            <div className="space-y-2">
              {activePlans.map((plan) => (
                <Link
                  key={plan.id}
                  href={`/app/campaigns/${plan.id}`}
                  className="glass rounded-xl p-4 flex items-center justify-between hover:border-accent/30 transition-all"
                >
                  <div>
                    <div className="text-sm font-medium text-text">{plan.name}</div>
                    <div className="text-xs text-text-muted mt-0.5">{plan.goal}</div>
                  </div>
                  <span className="text-xs text-text-muted">{plan.status}</span>
                </Link>
              ))}
            </div>
          </section>
        ) : null;
      // Domain-specific widget kinds (trending, promotions, appointments) are
      // rendered by the extraWidgets prop. The shell just leaves space.
      default:
        return null;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      {/* ─── Greeting ─── */}
      <div>
        <h1 className="font-display text-2xl sm:text-3xl font-semibold text-text">{brand.name}</h1>
        <p className="text-text-secondary mt-1.5 text-sm">
          Here&apos;s your {config.label.toLowerCase()} at a glance.
        </p>
      </div>

      {/* ─── Today's recommended action (common) ─── */}
      <TodaysAction
        brand={brand}
        hasCampaigns={hasCampaigns}
        pendingCount={pendingPlans.length}
        domainLabel={config.label}
      />

      {/* ─── Domain-supplied widgets ─── */}
      {config.dashboard_widgets.map((widget, index) => renderWidget(widget, index))}

      {/* ─── Extra widgets (domain-specific, e.g. trending for creators) ─── */}
      {extraWidgets}
    </motion.div>
  );
}
