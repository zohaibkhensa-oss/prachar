"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  Users,
  Eye,
  Clock,
  TrendingUp,
  Target,
  Video,
  Zap,
  DollarSign,
  Handshake,
  Calendar,
  CheckCircle2,
  Lightbulb,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Brand, CampaignPlan } from "@/lib/hooks";

interface Props {
  brand: Brand;
  plans: CampaignPlan[] | undefined;
}

/**
 * Creator dashboard — replaces business KPIs with creator KPIs.
 * Shows: Subscriber Growth, Views, Watch Time, Retention, CTR, Uploads,
 * Revenue, Brand Deals, Trending Opportunities, Content Pipeline.
 *
 * Common dashboard elements (shared with business): Today's recommended action,
 * upcoming tasks, drafts, approvals, performance summary.
 */
export function CreatorDashboard({ brand, plans }: Props) {
  const activePlans = plans?.filter((p) => p.status === "active" || p.status === "approved") ?? [];
  const pendingPlans = plans?.filter((p) => p.status === "pending" || p.status === "draft") ?? [];
  const hasCampaigns = (activePlans.length + pendingPlans.length) > 0;

  return (
    <div className="space-y-8">
      {/* ─── Greeting ─── */}
      <div>
        <h1 className="font-display text-3xl font-semibold text-text">
          {brand.name}
        </h1>
        <p className="text-text-secondary mt-1.5 text-sm">
          Here's your channel at a glance.
        </p>
      </div>

      {/* ─── Today's recommended action (common dashboard element) ─── */}
      <TodaysAction brand={brand} hasCampaigns={hasCampaigns} pendingCount={pendingPlans.length} />

      {/* ─── Creator KPIs ─── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-accent" />
          <h2 className="font-display text-sm font-semibold text-text">Your channel</h2>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <CreatorKpiCard icon={Users} label="Subscribers" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={Eye} label="Views (28d)" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={Clock} label="Watch time" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={Target} label="Avg. retention" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={TrendingUp} label="CTR" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={Video} label="Uploads (30d)" value={String(activePlans.reduce((n, p) => n + countUploads(p), 0))} hint="From your plans" />
          <CreatorKpiCard icon={DollarSign} label="Est. revenue" value="—" hint="Connect YouTube to see" />
          <CreatorKpiCard icon={Handshake} label="Brand deals" value="—" hint="Track in Brand Deals" />
        </div>
        <p className="text-[11px] text-text-muted mt-3">
          Connect your YouTube channel in Channels to see live numbers.
        </p>
      </div>

      {/* ─── Quick actions (creator-specific) ─── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-accent" />
          <h2 className="font-display text-sm font-semibold text-text">Create content</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <CreatorActionCard
            icon={RefreshCw}
            title="Repurpose a video"
            desc="Turn one YouTube video into 11 assets — Shorts, Reels, posts, blog, newsletter."
            href="/app/repurpose"
            accent="accent"
          />
          <CreatorActionCard
            icon={Video}
            title="Plan a YouTube video"
            desc="Get titles, thumbnails, hooks, SEO, tags, chapters — everything you need to post."
            href="/app/youtube-plan"
            accent="info"
          />
          <CreatorActionCard
            icon={Calendar}
            title="Build content campaign"
            desc="Get a 30-day content plan tailored to your channel and goals."
            href={`/app/brands/${brand.id}/campaigns/new`}
            accent="success"
          />
        </div>
      </div>

      {/* ─── Approvals (common dashboard element) ─── */}
      {pendingPlans.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-warning" />
            <h2 className="font-display text-sm font-semibold text-text">Waiting for your approval</h2>
          </div>
          <div className="space-y-2">
            {pendingPlans.slice(0, 3).map((p) => (
              <Link
                key={p.id}
                href={`/app/brands/${brand.id}/campaigns/${p.id}`}
                className="glass hover:glass-strong rounded-xl p-4 flex items-center justify-between transition-all group"
              >
                <div>
                  <div className="text-sm font-medium text-text">{p.name}</div>
                  <div className="text-xs text-text-muted mt-0.5">{p.goal}</div>
                </div>
                <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ─── Trending opportunities (creator-specific) ─── */}
      <TrendingOpportunities brand={brand} />

      {/* ─── Content pipeline (creator-specific) ─── */}
      <ContentPipeline plans={activePlans} />
    </div>
  );
}

function countUploads(plan: CampaignPlan): number {
  const cp = plan.campaign as { content_plan?: { videos?: unknown[]; shorts?: unknown[] }[] };
  if (!cp?.content_plan) return 0;
  return cp.content_plan.reduce((n, w) => n + (w.videos?.length ?? 0) + (w.shorts?.length ?? 0), 0);
}

// ─── Today's recommended action (common dashboard element) ─────────────────

function TodaysAction({ brand, hasCampaigns, pendingCount }: { brand: Brand; hasCampaigns: boolean; pendingCount: number }) {
  let action: { title: string; desc: string; href: string; cta: string };
  if (pendingCount > 0) {
    action = {
      title: "Review your pending campaign",
      desc: `You have ${pendingCount} campaign${pendingCount > 1 ? "s" : ""} waiting for approval. Review and launch in 30 seconds.`,
      href: `/app/brands/${brand.id}/campaigns`,
      cta: "Review now",
    };
  } else if (!hasCampaigns) {
    action = {
      title: "Build your first content plan",
      desc: "Get a 30-day content plan tailored to your channel. Takes 30 seconds.",
      href: `/app/brands/${brand.id}/campaigns/new`,
      cta: "Build my plan",
    };
  } else {
    action = {
      title: "Repurpose your latest video",
      desc: "Turn one video into 11 assets — Shorts, Reels, posts, blog, newsletter. Save hours.",
      href: "/app/repurpose",
      cta: "Repurpose a video",
    };
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-strong rounded-2xl p-6 relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-48 h-48 bg-accent/10 rounded-full blur-3xl" />
      <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 mb-3">
            <Sparkles className="w-3 h-3 text-accent" />
            <span className="font-mono text-[10px] text-accent uppercase tracking-wider">Today's action</span>
          </div>
          <h2 className="font-display text-lg font-semibold text-text">{action.title}</h2>
          <p className="text-sm text-text-secondary mt-1 max-w-md">{action.desc}</p>
        </div>
        <Link
          href={action.href}
          className="btn-primary group shrink-0"
        >
          {action.cta}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </motion.div>
  );
}

// ─── Creator KPI card ──────────────────────────────────────────────────────

function CreatorKpiCard({ icon: Icon, label, value, hint }: { icon: LucideIcon; label: string; value: string; hint: string }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-text-muted" />
        <span className="label-field">{label}</span>
      </div>
      <div className="text-xl font-display font-semibold text-text">{value}</div>
      <div className="text-[10px] text-text-muted mt-1">{hint}</div>
    </div>
  );
}

// ─── Creator action card ───────────────────────────────────────────────────

function CreatorActionCard({
  icon: Icon,
  title,
  desc,
  href,
  accent,
}: {
  icon: LucideIcon;
  title: string;
  desc: string;
  href: string;
  accent: "accent" | "info" | "success";
}) {
  const accentBg: Record<string, string> = {
    accent: "bg-accent/10 text-accent",
    info: "bg-info/10 text-info",
    success: "bg-success/10 text-success",
  };
  return (
    <Link
      href={href}
      className="glass hover:glass-strong rounded-xl p-5 transition-all group hover:scale-[1.01]"
    >
      <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center mb-3", accentBg[accent])}>
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="font-display text-sm font-semibold text-text mb-1">{title}</h3>
      <p className="text-xs text-text-secondary leading-relaxed">{desc}</p>
      <div className="mt-3 inline-flex items-center gap-1 text-xs text-accent">
        Start
        <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

// ─── Trending opportunities ────────────────────────────────────────────────

function TrendingOpportunities({ brand }: { brand: Brand }) {
  // Until we have platform API integration, show a prompt to discover opportunities
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-accent" />
        <h2 className="font-display text-sm font-semibold text-text">Trending in your niche</h2>
      </div>
      <p className="text-sm text-text-secondary mb-4">
        Connect your YouTube channel to see trending topics, viral formats, and content opportunities specific to {brand.name}.
      </p>
      <Link href="/app/channels" className="btn-secondary text-xs">
        Connect YouTube
        <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}

// ─── Content pipeline ──────────────────────────────────────────────────────

function ContentPipeline({ plans }: { plans: CampaignPlan[] }) {
  if (plans.length === 0) {
    return (
      <div className="glass rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="w-4 h-4 text-text-muted" />
          <h2 className="font-display text-sm font-semibold text-text">Content pipeline</h2>
        </div>
        <p className="text-sm text-text-secondary">
          No active content plans yet. Build your first plan to see your publishing schedule here.
        </p>
      </div>
    );
  }

  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Calendar className="w-4 h-4 text-accent" />
        <h2 className="font-display text-sm font-semibold text-text">Content pipeline</h2>
      </div>
      <div className="space-y-2">
        {plans.slice(0, 3).map((p) => {
          const cp = p.campaign as { content_plan?: { week?: number; theme?: string; videos?: unknown[]; shorts?: unknown[] }[]; publishing_schedule?: string };
          const totalVideos = cp.content_plan?.reduce((n, w) => n + (w.videos?.length ?? 0), 0) ?? 0;
          const totalShorts = cp.content_plan?.reduce((n, w) => n + (w.shorts?.length ?? 0), 0) ?? 0;
          return (
            <div key={p.id} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02]">
              <div>
                <div className="text-sm font-medium text-text">{p.name}</div>
                <div className="text-xs text-text-muted mt-0.5">
                  {totalVideos} videos · {totalShorts} shorts
                  {cp.publishing_schedule ? ` · ${cp.publishing_schedule}` : ""}
                </div>
              </div>
              <span className="badge badge-success">Active</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
