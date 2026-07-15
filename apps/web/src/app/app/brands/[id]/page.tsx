"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowLeft,
  Globe,
  Zap,
  Megaphone,
  Target,
  DollarSign,
  Eye,
  TrendingUp,
  TrendingDown,
  Trophy,
  Sparkles,
  Play,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { PerformanceRing, ProgressBar, Sparkline } from "@/components/ui/charts";
import { AIStatusBlock, AIRecommendation } from "@/components/ui/ai-blocks";
import { SectionHeader } from "@/components/ui/empty-state";

interface Channel {
  name: string;
  short: string;
  status: "connected" | "syncing" | "error";
  metric: string;
  value: string;
}

interface Campaign {
  id: string;
  name: string;
  network: string;
  roas: number;
  ctr: number;
  budget: number;
  status: "active" | "paused" | "review";
}

interface Competitor {
  name: string;
  rank: number;
  change: number;
  visibility: number;
}

const CHANNELS: Channel[] = [
  { name: "Google Ads", short: "G", status: "connected", metric: "ROAS", value: "3.2x" },
  { name: "Meta Ads", short: "M", status: "connected", metric: "CPA", value: "₹420" },
  { name: "Instagram", short: "IG", status: "syncing", metric: "Reach", value: "12.4K" },
  { name: "YouTube", short: "YT", status: "connected", metric: "Views", value: "8.1K" },
  { name: "TikTok", short: "TT", status: "error", metric: "—", value: "—" },
  { name: "LinkedIn", short: "in", status: "connected", metric: "Leads", value: "23" },
];

const CAMPAIGNS: Campaign[] = [
  { id: "c1", name: "Google RSA — Coffee Search", network: "Google", roas: 3.2, ctr: 4.8, budget: 500, status: "active" },
  { id: "c2", name: "Meta CBO — Retargeting", network: "Meta", roas: 1.8, ctr: 2.1, budget: 300, status: "active" },
  { id: "c3", name: "YouTube — Awareness", network: "YouTube", roas: 2.5, ctr: 3.4, budget: 200, status: "active" },
  { id: "c4", name: "Instagram — Story Ads", network: "Meta", roas: 2.1, ctr: 3.0, budget: 150, status: "review" },
  { id: "c5", name: "LinkedIn — Lead Gen", network: "LinkedIn", roas: 1.2, ctr: 1.1, budget: 250, status: "paused" },
];

const COMPETITORS: Competitor[] = [
  { name: "BeanThere Coffee", rank: 1, change: 2, visibility: 61.2 },
  { name: "BrewCraft Co", rank: 2, change: -1, visibility: 48.7 },
  { name: "Artisan Roasters", rank: 3, change: 0, visibility: 39.4 },
  { name: "Daily Grind", rank: 4, change: 1, visibility: 28.1 },
];

const HEALTH_DIMS = [
  { label: "Organic Rank", value: 18.2, accent: "success" as const },
  { label: "AI Citation Rate", value: 12.0, accent: "info" as const },
  { label: "Social Reach", value: 31.5, accent: "accent" as const },
  { label: "Paid Efficiency", value: 42.8, accent: "success" as const },
  { label: "Content Momentum", value: 28.0, accent: "danger" as const },
  { label: "Review Sentiment", value: 54.3, accent: "accent" as const },
];

const NETWORK_BADGE: Record<string, string> = {
  Google: "badge-info",
  Meta: "badge-info",
  YouTube: "badge-danger",
  LinkedIn: "badge-info",
};

export default function BrandWorkspacePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [analyzing, setAnalyzing] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setAnalyzing(false), 2200);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="space-y-6">
      {/* ─── Back + Header ─── */}
      <Link
        href="/app/brands"
        className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        All brands
      </Link>

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/25 to-accent/5 flex items-center justify-center border border-accent/15 shrink-0">
            <span className="font-display text-2xl font-semibold text-accent">D</span>
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold text-text">Demo Coffee Co</h1>
              <span className="badge badge-neutral">F&B</span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
              <span className="flex items-center gap-1">
                <Globe className="w-3 h-3" />
                democoffee.in
              </span>
              <span className="text-text-muted">·</span>
              <span>Brand ID: {id}</span>
            </div>
          </div>
        </div>
        <button className="btn-primary group">
          <Zap className="w-4 h-4" />
          Run Weekly Loop Now
        </button>
      </div>

      {/* ─── Visibility + AI Summary ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card3D glow className="lg:col-span-1 flex flex-col items-center">
          <SectionHeader title="Visibility Score" subtitle="Weighted across channels" />
          <PerformanceRing value={24.3} size={150} strokeWidth={11} sublabel="out of 100" accent="#FFD400" />
          <div className="w-full mt-4 space-y-2.5">
            {HEALTH_DIMS.slice(0, 4).map((d) => (
              <div key={d.label}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">{d.label}</span>
                  <span className="font-mono text-xs text-text">{d.value.toFixed(1)}</span>
                </div>
                <ProgressBar value={d.value} accent={d.accent} />
              </div>
            ))}
          </div>
        </Card3D>

        <div className="lg:col-span-2 space-y-4">
          {analyzing ? (
            <AIStatusBlock
              status="analyzing"
              label="AI Analyzing Brand"
              detail="Scanning 6 channels, 4 competitors, 8 weeks of performance data..."
              confidence={64}
            />
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <AIStatusBlock
                status="done"
                label="AI Summary Ready"
                detail="Analysis complete · 6 channels · 4 competitors scanned"
                confidence={92}
              />
              <Card className="border-l-2 border-l-accent/40">
                <div className="flex items-start gap-3">
                  <div className="shrink-0 w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-accent" />
                  </div>
                  <div>
                    <h3 className="font-display text-sm font-medium text-text mb-1.5">
                      Weekly Brand Intelligence
                    </h3>
                    <p className="text-sm text-text-secondary leading-relaxed">
                      Demo Coffee Co gained <span className="text-success font-medium">+6.8 visibility points</span> this
                      week, driven by Google RSA efficiency (CPA 18% below Meta). YouTube channel is dormant —
                      competitors publish 3x/week. Recommend launching 2 video assets and reallocating ₹1,500/day from
                      Meta to Google to capture &lsquo;specialty coffee subscription&rsquo; demand (+340% trending).
                    </p>
                  </div>
                </div>
              </Card>
            </motion.div>
          )}

          <div className="space-y-3">
            <AIRecommendation
              title="Reallocate ₹1,500/day Meta → Google"
              reasoning="Google RSA CPA is ₹290 vs Meta ₹420. Shifting budget yields ~12 extra conversions/week at current efficiency."
              action="Apply budget reallocation"
              confidence={87}
            />
            <AIRecommendation
              title="Publish 2 YouTube videos this week"
              reasoning="Channel dormant 14 days. Competitors average 3 uploads/week. Transcript→metadata engine is ready."
              action="Generate video metadata"
              confidence={92}
            />
          </div>
        </div>
      </div>

      {/* ─── Performance Metrics ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="ROAS" value={3.2} format="number" suffix="x" delta={14.2} deltaLabel="vs last wk" icon={<TrendingUp className="w-4 h-4" />} accent="success" />
        <Metric label="CPA" value={356} format="currency" delta={-18} deltaLabel="improved" icon={<DollarSign className="w-4 h-4" />} accent="accent" />
        <Metric label="Conversions" value={127} delta={23} deltaLabel="vs last wk" icon={<Target className="w-4 h-4" />} accent="info" />
        <Metric label="Impressions" value={284000} format="compact" delta={8.3} icon={<Eye className="w-4 h-4" />} accent="default" />
      </div>

      {/* ─── Channels + Campaigns ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <SectionHeader title="Connected Channels" subtitle="6 platforms" icon={<Globe className="w-4 h-4" />} />
          <div className="grid grid-cols-2 gap-3">
            {CHANNELS.map((ch) => (
              <div
                key={ch.name}
                className="rounded-lg p-3 bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.08] transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="w-7 h-7 rounded-md bg-white/[0.05] flex items-center justify-center font-mono text-[10px] font-medium text-text">
                    {ch.short}
                  </span>
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full",
                      ch.status === "connected" && "bg-success",
                      ch.status === "syncing" && "bg-info animate-pulse",
                      ch.status === "error" && "bg-danger",
                    )}
                  />
                </div>
                <div className="text-xs text-text truncate">{ch.name}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="label-field text-[9px]">{ch.metric}</span>
                  <span className="font-mono text-xs text-text-secondary">{ch.value}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <SectionHeader
            title="Recent Campaigns"
            subtitle="5 campaigns"
            icon={<Megaphone className="w-4 h-4" />}
            action={
              <Link href="/app/campaigns" className="btn-ghost text-xs">
                View all
              </Link>
            }
          />
          <div className="space-y-2">
            {CAMPAIGNS.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full shrink-0",
                      c.status === "active" && "bg-success",
                      c.status === "paused" && "bg-text-muted",
                      c.status === "review" && "bg-warning",
                    )}
                  />
                  <div className="min-w-0">
                    <div className="text-sm text-text truncate">{c.name}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={cn("badge text-[9px]", NETWORK_BADGE[c.network] ?? "badge-neutral")}>
                        {c.network}
                      </span>
                      <span className="font-mono text-[10px] text-text-muted">₹{c.budget}/d</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-5 shrink-0">
                  <div className="text-right">
                    <div className="label-field text-[9px]">ROAS</div>
                    <div className="font-mono text-xs text-text">{c.roas}x</div>
                  </div>
                  <div className="text-right">
                    <div className="label-field text-[9px]">CTR</div>
                    <div className="font-mono text-xs text-text">{c.ctr}%</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ─── Competitors + Health ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <SectionHeader
            title="Competitor Monitoring"
            subtitle="4 competitors tracked"
            icon={<Trophy className="w-4 h-4" />}
          />
          <div className="space-y-2">
            {COMPETITORS.map((comp) => (
              <div
                key={comp.name}
                className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="w-7 h-7 rounded-md bg-white/[0.05] flex items-center justify-center font-mono text-xs text-text-secondary">
                    #{comp.rank}
                  </span>
                  <div>
                    <div className="text-sm text-text">{comp.name}</div>
                    <div className="font-mono text-[10px] text-text-muted">
                      vis {comp.visibility.toFixed(1)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {comp.change > 0 ? (
                    <>
                      <TrendingUp className="w-3.5 h-3.5 text-danger" />
                      <span className="font-mono text-xs text-danger">+{comp.change}</span>
                    </>
                  ) : comp.change < 0 ? (
                    <>
                      <TrendingDown className="w-3.5 h-3.5 text-success" />
                      <span className="font-mono text-xs text-success">{comp.change}</span>
                    </>
                  ) : (
                    <span className="font-mono text-xs text-text-muted">—</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionHeader title="Health Overview" subtitle="6 dimensions" icon={<CheckCircle2 className="w-4 h-4" />} />
          <div className="space-y-3">
            {HEALTH_DIMS.map((d) => (
              <div key={d.label}>
                <div className="flex justify-between mb-1.5">
                  <span className="text-xs text-text-secondary">{d.label}</span>
                  <span className="font-mono text-xs text-text">{d.value.toFixed(1)}</span>
                </div>
                <ProgressBar value={d.value} accent={d.accent} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ─── Trend footer ─── */}
      <Card>
        <SectionHeader title="8-Week Visibility Trend" subtitle="Demo Coffee Co" icon={<TrendingUp className="w-4 h-4" />} />
        <div className="flex items-center justify-between">
          <div>
            <span className="font-display text-3xl font-semibold text-text">24.3</span>
            <span className="text-xs text-success ml-2 font-mono">+6.8 pts</span>
          </div>
          <Sparkline data={[12, 15, 14, 18, 22, 20, 24, 28]} width={240} height={56} color="#FFD400" />
        </div>
        <div className="mt-4 flex items-center gap-2 text-xs text-text-muted">
          <Play className="w-3 h-3" />
          Next weekly loop scheduled in 4 days · 18:00 IST
        </div>
      </Card>
    </div>
  );
}
