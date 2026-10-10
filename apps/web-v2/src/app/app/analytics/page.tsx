"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  TrendingUp,
  Eye,
  Target,
  ArrowRight,
  Sparkles,
  Megaphone,
  BarChart3,
  Clock,
  RefreshCw,
  IndianRupee,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface MetricsSummary {
  totals: Record<string, { current: number; previous: number }>;
  series: Record<string, { date: string; value: number }[]>;
  last_synced: string | null;
}

const fmtNum = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
  : n >= 1_000 ? `${(n / 1_000).toFixed(1)}K`
  : String(Math.round(n));

export default function ResultsPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);
  const [syncing, setSyncing] = useState(false);
  const queryClient = useQueryClient();

  const { data: metrics } = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary", brand?.id, 30],
    queryFn: () => apiGet(`/brands/${brand!.id}/metrics/summary?days=30`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const isLoading = brandLoading || plansLoading;
  const activeCount = plans?.filter((p) => p.status === "active" || p.status === "approved").length ?? 0;
  const totalCampaigns = plans?.length ?? 0;
  const hasData = totalCampaigns > 0;

  // Real metrics — undefined means the sync hasn't produced data
  const reached = metrics?.totals?.impressions?.current;
  const actions = metrics?.totals
    ? (metrics.totals.engagements?.current ?? 0) + (metrics.totals.clicks?.current ?? 0)
    : undefined;
  const spend = metrics?.totals?.spend?.current;
  const chartData = metrics?.series?.impressions ?? [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
          <BarChart3 className="w-7 h-7 text-accent" />
        </div>
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to see your results.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Your Results</h1>
          <p className="text-sm text-text-secondary mt-1">
            How {brand.name} is performing across all channels.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={async () => {
              if (!brand?.id || syncing) return;
              setSyncing(true);
              try {
                await apiPost(`/brands/${brand.id}/metrics/sync`);
                queryClient.invalidateQueries({ queryKey: ["metrics-summary"] });
              } finally {
                setSyncing(false);
              }
            }}
            disabled={syncing}
            title={metrics?.last_synced ? `Last synced ${metrics.last_synced}` : "Pull latest channel metrics"}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line/10 bg-bg-card text-xs text-text-secondary hover:text-text disabled:opacity-50"
          >
            <RefreshCw className={cn("w-3 h-3", syncing && "animate-spin")} />
            {syncing ? "Syncing" : "Sync"}
          </button>
          {hasData && (
            <span className="badge badge-accent">
              <TrendingUp className="w-3 h-3" />
              {totalCampaigns} campaign{totalCampaigns > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* Top metrics — real synced values or honest empty states */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ResultCard
          icon={<Eye className="w-4 h-4" />}
          label="People reached"
          value={reached !== undefined ? fmtNum(reached) : "—"}
          sub={reached !== undefined ? "Last 30 days — impressions + views" : "Sync channel data"}
          accent="text-info"
          dimmed={reached === undefined}
        />
        <ResultCard
          icon={<Target className="w-4 h-4" />}
          label="Customer actions"
          value={actions !== undefined ? fmtNum(actions) : "—"}
          sub={actions !== undefined ? "Last 30 days — likes, clicks, shares" : "Sync channel data"}
          accent="text-success"
          dimmed={actions === undefined}
        />
        <ResultCard
          icon={<IndianRupee className="w-4 h-4" />}
          label="Ad spend"
          value={spend !== undefined ? fmtNum(spend) : "—"}
          sub={spend !== undefined ? "Last 30 days" : "No ads account connected"}
          accent="text-accent"
          dimmed={spend === undefined}
        />
        <ResultCard
          icon={<TrendingUp className="w-4 h-4" />}
          label="Visibility"
          value={brand.visibility_score != null ? `${brand.visibility_score.toFixed(0)}/100` : "—"}
          sub={brand.visibility_score != null ? "Across all channels" : "Not scored yet"}
          accent="text-accent"
          dimmed={brand.visibility_score == null}
        />
      </div>

      {/* Real performance chart when metrics exist */}
      {chartData.length > 0 && (
        <div className="glass-strong rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">Performance over time</h2>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="reachFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="transparent" tickLine={false}
                  tickFormatter={(d: string) => d.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} stroke="transparent" tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#13131f", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="value" stroke="#8b5cf6" strokeWidth={2} fill="url(#reachFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* No data yet state */}
      {totalCampaigns === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-12 text-center"
        >
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-accent" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            No results yet — let&apos;s change that
          </h2>
          <p className="text-sm text-text-secondary mb-6 max-w-sm mx-auto">
            Create your first campaign and we&apos;ll show you exactly how many people you&apos;re reaching and how they&apos;re responding.
          </p>
          <Link
            href={`/app/brands/${brand.id}/campaigns/new`}
            className="btn-primary inline-flex group"
          >
            <Sparkles className="w-4 h-4" />
            Create your first campaign
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      )}

      {/* Campaigns exist but no performance data yet */}
      {totalCampaigns > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-8"
        >
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">Performance over time</h2>
          </div>
          <p className="text-sm text-text-secondary mb-6">
            Once your campaigns have run for a few days, you&apos;ll see:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              "How many people saw your business",
              "How many clicked, called, or visited",
              "Which channels are bringing the most customers",
              "How your visibility is improving over time",
            ].map((item, i) => (
              <motion.div
                key={item}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
                <span className="text-sm text-text-secondary">{item}</span>
              </motion.div>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2 text-xs text-text-muted">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-2 h-2 rounded-full bg-success"
            />
            <span>Your campaigns are running — data will appear here soon</span>
          </div>
        </motion.div>
      )}

      {/* Link to individual performance stories */}
      {totalCampaigns > 0 && plans && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-text-muted" />
            <span className="label-field">Campaign performance stories</span>
          </div>
          {plans.slice(0, 3).map((plan, i) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Link
                href={`/app/performance/${plan.id}`}
                className="block glass rounded-xl p-4 hover:bg-white/[0.04] hover:border-white/[0.1] transition-all group"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-text truncate">{plan.name || "Untitled campaign"}</h3>
                    {plan.goal && <p className="text-xs text-text-muted truncate mt-0.5">{plan.goal}</p>}
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent shrink-0" />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultCard({
  icon,
  label,
  value,
  sub,
  accent,
  dimmed,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent: string;
  dimmed?: boolean;
}) {
  return (
    <div className={`glass rounded-2xl p-5 transition-all ${dimmed ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={accent}>{icon}</span>
        <span className="label-field">{label}</span>
      </div>
      <div className="font-display text-3xl font-semibold text-text tabular-nums">{value}</div>
      <div className="text-[11px] text-text-muted mt-1.5">{sub}</div>
    </div>
  );
}
