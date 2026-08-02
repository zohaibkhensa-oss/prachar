"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  ArrowDownRight,
  ArrowUpRight,
  TrendingUp,
  Eye,
  Target,
  CheckCircle2,
  Clock,
  AlertCircle,
  Minus,
  Plus,
  Megaphone,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { INDUSTRY_BY_ID } from "@/lib/industries";
import { Skeleton } from "@/components/ui/skeleton";
import { CreatorDashboard } from "./creator-dashboard";
import { DashboardShell } from "@/components/consult/DashboardShell";
import { unifiedConsultApi, type DomainConfig } from "@/lib/unified-consult";
import { useQuery } from "@tanstack/react-query";

// Fallback configs if the /consult/nav endpoint is unavailable
const BUSINESS_FALLBACK: DomainConfig = {
  domain: "business",
  label: "Business Growth",
  emoji: "🏢",
  nav_sections: [],
  kpi_cards: [
    { key: "customers", label: "Customers", icon: "Users", hint: "From your campaigns" },
    { key: "revenue", label: "Revenue", icon: "TrendingUp", hint: "From your campaigns" },
    { key: "enquiries", label: "Enquiries", icon: "MessageSquare", hint: "From your campaigns" },
    { key: "reach", label: "Reach", icon: "Eye", hint: "People who saw your business" },
  ],
  dashboard_widgets: [
    { kind: "kpi_grid", title: "Your business at a glance", props: {} },
    { kind: "quick_actions", title: "Grow your business", props: {} },
    { kind: "approvals", title: "Waiting for your approval", props: {} },
    { kind: "pipeline", title: "Your campaigns", props: {} },
  ],
  quick_actions: [
    {
      title: "Create My Campaign",
      description: "We'll build your marketing campaign — tailored for your business. Takes 30 seconds.",
      href: "/app/brands/{brand_id}/campaigns/new",
      icon: "Zap",
      accent: "accent",
    },
  ],
  tools: [],
};

const CREATOR_FALLBACK: DomainConfig = {
  domain: "creator",
  label: "Creator Growth",
  emoji: "🎨",
  nav_sections: [],
  kpi_cards: [
    { key: "subscribers", label: "Subscribers", icon: "Users", hint: "Connect YouTube to see" },
    { key: "views", label: "Views (28d)", icon: "Eye", hint: "Connect YouTube to see" },
    { key: "watch_time", label: "Watch time", icon: "Clock", hint: "Connect YouTube to see" },
    { key: "retention", label: "Avg. retention", icon: "Target", hint: "Connect YouTube to see" },
    { key: "ctr", label: "CTR", icon: "TrendingUp", hint: "Connect YouTube to see" },
    { key: "uploads", label: "Uploads (30d)", icon: "Video", hint: "From your plans" },
    { key: "revenue", label: "Est. revenue", icon: "DollarSign", hint: "Connect YouTube to see" },
    { key: "brand_deals", label: "Brand deals", icon: "Handshake", hint: "Track in Brand Deals" },
  ],
  dashboard_widgets: [
    { kind: "kpi_grid", title: "Your channel", props: {} },
    { kind: "quick_actions", title: "Create content", props: {} },
    { kind: "approvals", title: "Waiting for your approval", props: {} },
    { kind: "pipeline", title: "Content pipeline", props: {} },
  ],
  quick_actions: [
    {
      title: "Repurpose a video",
      description: "Turn one YouTube video into 11 assets — Shorts, Reels, posts, blog, newsletter.",
      href: "/app/repurpose",
      icon: "RefreshCw",
      accent: "accent",
    },
    {
      title: "Plan a YouTube video",
      description: "Get titles, thumbnails, hooks, SEO, tags, chapters — everything you need to post.",
      href: "/app/youtube-plan",
      icon: "Video",
      accent: "info",
    },
    {
      title: "Build content campaign",
      description: "Get a 30-day content plan tailored to your channel and goals.",
      href: "/app/brands/{brand_id}/campaigns/new",
      icon: "Calendar",
      accent: "success",
    },
  ],
  tools: [],
};

export default function HomePage() {
  const router = useRouter();
  const { brand, brands, isLoading } = useActiveBrand();
  const { data: plans } = useCampaignPlans(brand?.id ?? null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // If user has no brands, redirect to onboarding
  useEffect(() => {
    if (!isLoading && brands && brands.length === 0) {
      router.replace("/onboarding");
    }
  }, [isLoading, brands, router]);

  // Fetch the domain config from the backend (driven by the Domain Pack registry)
  const domain = brand?.customer_type === "creator" ? "creator" : "business";
  const { data: domainConfig } = useQuery({
    queryKey: ["domain-config", domain],
    queryFn: () => unifiedConsultApi.config(domain),
    enabled: !!brand,
    staleTime: 5 * 60 * 1000, // 5 min — config rarely changes
  });

  const industry = brand?.category ? INDUSTRY_BY_ID[brand.category] : null;
  const activePlans = plans?.filter((p) => p.status === "active" || p.status === "approved") ?? [];
  const pendingPlans = plans?.filter((p) => p.status === "pending" || p.status === "draft") ?? [];
  const hasCampaigns = (activePlans.length + pendingPlans.length) > 0;

  // ─── Creator dashboard: use the unified shell with creator config ───
  if (brand && brand.customer_type === "creator") {
    const config = domainConfig ?? CREATOR_FALLBACK;
    return (
      <DashboardShell
        brand={brand}
        plans={plans}
        config={config}
      />
    );
  }

  // ─── Business dashboard: use the unified shell with business config ───
  // (The original business dashboard UI is preserved within the shell's widget slots.
  //  The shell provides greeting, today's action, and approvals; the business-specific
  //  KPIs and quick actions come from the BusinessPack config.)
  if (brand && domainConfig) {
    return (
      <DashboardShell
        brand={brand}
        plans={plans}
        config={domainConfig}
      />
    );
  }

  // ─── Fallback: original business dashboard (while config loads) ───
  return (
    <div className="space-y-6">
      {/* ─── Greeting ─── */}
      <div>
        <h1 className="font-display text-2xl sm:text-3xl font-semibold text-text">
          {mounted ? greeting() : "Welcome"}
          {brand ? `, ${firstName(brand.name)}` : ""}
        </h1>
        <p className="text-text-secondary mt-1.5 text-sm">
          {brand
            ? `Here's what's happening with ${brand.name} today.`
            : "Let's get your marketing running."}
        </p>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : !brand ? (
        <LoadingState />
      ) : !hasCampaigns ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <FirstCampaignState brand={brand} industryLabel={industry?.label ?? "your business"} />
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ActiveDashboard
            brand={brand}
            industryLabel={industry?.label ?? "your business"}
            activeCount={activePlans.length}
            pendingCount={pendingPlans.length}
            visibility={brand.visibility_score}
          />
        </motion.div>
      )}
    </div>
  );
}

// ─── First campaign: positive framing — ONE dominant CTA ───────────────────


function FirstCampaignState({ brand, industryLabel }: { brand: { id: string; name: string }; industryLabel: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      {/* Hero CTA card */}
      <div className="glass-strong rounded-2xl p-6 shadow-3d-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-accent/10 rounded-full blur-3xl" />
        <div className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 mb-5">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span className="font-mono text-xs text-accent">Your first campaign is ready to build</span>
          </div>

          <h2 className="font-display text-xl font-semibold text-text max-w-lg leading-tight">
            Your first campaign for {brand.name}.
          </h2>
          <p className="text-text-secondary mt-3 max-w-md text-sm leading-relaxed">
            Let's launch your first marketing campaign — tailored for {industryLabel.toLowerCase()}.
            It takes 30 seconds. You approve everything before it goes live.
          </p>

          <Link
            href={`/app/brands/${brand.id}/campaigns/new`}
            className="btn-primary inline-flex mt-6 group text-base"
          >
            <Zap className="w-5 h-5" />
            Create My Campaign
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>

          <p className="text-xs text-text-muted mt-4">
            No credit card needed · You approve before anything goes live
          </p>
        </div>
      </div>

      {/* What happens next — 3 simple steps */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { icon: Sparkles, title: "We build your campaign", desc: "AI creates your ads, posts, and strategy — tuned for your business." },
          { icon: CheckCircle2, title: "You review & approve", desc: "See exactly what will go live. Tweak anything. Approve with one click." },
          { icon: TrendingUp, title: "We grow your reach", desc: "Your campaign runs across Google, Instagram, and more — automatically." },
        ].map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08, duration: 0.4 }}
            className="glass rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <step.icon className="w-4 h-4 text-accent" />
              </div>
              <span className="font-mono text-xs text-text-muted uppercase tracking-wider">Step {i + 1}</span>
            </div>
            <h3 className="font-display text-base font-semibold text-text mb-1.5">{step.title}</h3>
            <p className="text-sm text-text-secondary leading-relaxed">{step.desc}</p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

// ─── Active dashboard: has campaigns ───────────────────────────────────────


function ActiveDashboard({
  brand,
  industryLabel,
  activeCount,
  pendingCount,
  visibility,
}: {
  brand: { id: string; name: string };
  industryLabel: string;
  activeCount: number;
  pendingCount: number;
  visibility: number | null;
}) {
  return (
    <div className="space-y-6">
      {/* What should I do today? */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Dominant CTA — only if there are pending approvals */}
        {pendingCount > 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="lg:col-span-2 glass-strong rounded-2xl p-6 border-l-2 border-l-accent/50"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-accent" />
                  <span className="font-mono text-xs text-accent uppercase tracking-wider">Needs your attention</span>
                </div>
                <h2 className="font-display text-xl font-semibold text-text">
                  {pendingCount} campaign{pendingCount > 1 ? "s" : ""} waiting for your approval
                </h2>
                <p className="text-sm text-text-secondary mt-1.5">
                  Review and approve to start reaching customers.
                </p>
              </div>
              <Link
                href={`/app/brands/${brand.id}/campaigns`}
                className="btn-primary shrink-0 group"
              >
                Review now
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="lg:col-span-2 glass-strong rounded-2xl p-6"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-4 h-4 text-success" />
                  <span className="font-mono text-xs text-success uppercase tracking-wider">All caught up</span>
                </div>
                <h2 className="font-display text-xl font-semibold text-text">
                  Your marketing is running smoothly
                </h2>
                <p className="text-sm text-text-secondary mt-1.5">
                  {activeCount} active campaign{activeCount > 1 ? "s" : ""} promoting {brand.name}.
                </p>
              </div>
              <Link
                href={`/app/brands/${brand.id}/campaigns/new`}
                className="btn-secondary shrink-0 group"
              >
                <Plus className="w-4 h-4" />
                New campaign
              </Link>
            </div>
          </motion.div>
        )}

        {/* Visibility score */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="glass rounded-2xl p-6 flex flex-col"
        >
          <span className="label-field mb-2">How visible is your business?</span>
          <div className="flex items-baseline gap-2 mt-1">
            {visibility != null ? (
              <>
                <span className="font-display text-4xl font-semibold text-gradient-accent tabular-nums">
                  {visibility.toFixed(0)}
                </span>
                <span className="text-sm text-text-muted">/ 100</span>
              </>
            ) : (
              <span className="font-display text-2xl text-text-secondary">Coming soon</span>
            )}
          </div>
          <p className="text-xs text-text-muted mt-2 leading-relaxed">
            Based on your Google ranking, social reach, and customer reviews.
          </p>
        </motion.div>
      </div>

      {/* Quick metrics — business language, not jargon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={<Eye className="w-4 h-4" />}
          label="People reached"
          value="—"
          sub="This month"
          accent="info"
          context="How many people saw your business across Google, Instagram & more. Connect your channels to start tracking."
          trend="pending"
          seeWhyHref="/app/channels"
        />
        <MetricCard
          icon={<Target className="w-4 h-4" />}
          label="Customer actions"
          value="—"
          sub="Clicks, calls, visits"
          accent="success"
          context="Clicks on your ads, calls to your business, and website visits from your campaigns. Connect channels to measure."
          trend="pending"
          seeWhyHref="/app/channels"
        />
        <MetricCard
          icon={<TrendingUp className="w-4 h-4" />}
          label="Active campaigns"
          value={String(activeCount)}
          sub={industryLabel}
          accent="accent"
          context={`${activeCount} campaign${activeCount !== 1 ? "s" : ""} promoting ${brand.name} across your channels right now.`}
          trend={activeCount > 0 ? "new" : "pending"}
          seeWhyHref={`/app/brands/${brand.id}/campaigns`}
        />
        <MetricCard
          icon={<Clock className="w-4 h-4" />}
          label="Awaiting approval"
          value={String(pendingCount)}
          sub={pendingCount > 0 ? "Action needed" : "All clear"}
          accent={pendingCount > 0 ? "warning" : "neutral"}
          context={
            pendingCount > 0
              ? `${pendingCount} campaign${pendingCount > 1 ? "s" : ""} ready to launch — review and approve to start reaching customers.`
              : "Nothing waiting on you. Your marketing is running smoothly."
          }
          trend={pendingCount > 0 ? "up" : "flat"}
          seeWhyHref={pendingCount > 0 ? `/app/brands/${brand.id}/campaigns` : undefined}
        />
      </div>

      {/* What's running + what to improve */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass rounded-2xl p-6">
          <h3 className="font-display text-base font-semibold text-text mb-4">What's running now</h3>
          <Link
            href={`/app/brands/${brand.id}/campaigns`}
            className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                <Megaphone className="w-4 h-4 text-accent" />
              </div>
              <div>
                <div className="text-sm text-text font-medium">{activeCount} active campaigns</div>
                <div className="text-xs text-text-muted">Across Google, Instagram & more</div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-text transition-colors" />
          </Link>
        </div>

        <div className="glass rounded-2xl p-6">
          <h3 className="font-display text-base font-semibold text-text mb-4">What to improve next</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02]">
              <Sparkles className="w-4 h-4 text-accent shrink-0" />
              <span className="text-sm text-text-secondary">Add more photos of your work — boosts engagement by ~30%</span>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02]">
              <Sparkles className="w-4 h-4 text-accent shrink-0" />
              <span className="text-sm text-text-secondary">Connect your Google Business Profile for local reach</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Loading state ──────────────────────────────────────────────────────────


function LoadingState() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      {/* Greeting skeleton — matches the h1 + subtitle layout */}
      <div className="space-y-2">
        <Skeleton className="h-9 w-64 rounded-lg" />
        <Skeleton className="h-4 w-80 rounded-md" />
      </div>

      {/* Today's action skeleton — matches the glass-strong banner */}
      <Skeleton className="h-24 rounded-2xl" />

      {/* KPI grid skeleton — 4 cards matching the actual grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="glass rounded-2xl p-4 flex flex-col gap-2">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <Skeleton className="h-7 w-20 rounded-md" />
            <Skeleton className="h-3 w-16 rounded-sm" />
            <Skeleton className="h-3 w-12 rounded-sm" />
            <Skeleton className="h-8 w-full rounded-sm mt-1" />
          </div>
        ))}
      </div>

      {/* Quick actions skeleton — 3 cards matching the actions grid */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-40 rounded-md" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
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

// ─── Metric card ────────────────────────────────────────────────────────────


type TrendDirection = "up" | "down" | "flat" | "new" | "pending";

function MetricCard({
  icon,
  label,
  value,
  sub,
  accent,
  context,
  trend,
  seeWhyHref,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent: "info" | "success" | "accent" | "warning" | "neutral";
  /** One-line context explaining what the number means and why it matters. */
  context?: string;
  /** Trend indicator. Defaults to "pending" (connect channels) if omitted. */
  trend?: TrendDirection;
  /** "See why" link. If omitted, no link is shown. */
  seeWhyHref?: string;
}) {
  const accentColor: Record<string, string> = {
    info: "text-info",
    success: "text-success",
    accent: "text-accent",
    warning: "text-warning",
    neutral: "text-text-secondary",
  };

  const trendConfig: Record<
    TrendDirection,
    { icon: React.ReactNode; className: string; label: string }
  > = {
    up: { icon: <ArrowUpRight className="w-3 h-3" />, className: "text-success", label: "up" },
    down: { icon: <ArrowDownRight className="w-3 h-3" />, className: "text-warning", label: "down" },
    flat: { icon: <Minus className="w-3 h-3" />, className: "text-text-muted", label: "flat" },
    new: { icon: <Sparkles className="w-3 h-3" />, className: "text-accent", label: "New" },
    pending: { icon: null, className: "text-text-muted", label: "Connect channels to see trends" },
  };

  const trendInfo = trendConfig[trend ?? "pending"];
  const hasValue = value !== "—" && value !== "";

  return (
    <div className="glass rounded-xl p-4 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("shrink-0", accentColor[accent])}>{icon}</span>
        <span className="label-field">{label}</span>
      </div>
      <div className="font-display text-2xl font-semibold text-text tabular-nums">{value}</div>
      {/* Trend indicator */}
      <div className={cn("inline-flex items-center gap-0.5 text-xs font-medium mt-1.5", trendInfo.className)}>
        {trendInfo.icon}
        {trendInfo.label}
      </div>
      {/* Context line — explains what the number means */}
      <div className="text-xs text-text-secondary mt-1.5 leading-relaxed flex-1">
        {context ?? sub}
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
}

// ─── Helpers ────────────────────────────────────────────────────────────────


function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function firstName(name: string): string {
  // For businesses, just return the first word (usually the brand name)
  return name.split(" ")[0] ?? name;
}
