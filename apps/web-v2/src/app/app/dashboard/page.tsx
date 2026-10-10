"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { cn } from "@/lib/utils";
import { apiGet, apiPost } from "@/lib/api";
import { useActiveBrand, useBrands } from "@/lib/hooks";
import {
  Users, Heart, MousePointerClick, IndianRupee, AlertTriangle,
  ArrowUpRight, ArrowDownRight, ChevronDown, PenSquare, Megaphone,
  ImageIcon, VideoIcon, Link2, Sparkles, FileText, CheckCircle2,
  Clock, XCircle, RefreshCw,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface MetricsSummary {
  days: number;
  period_start: string;
  totals: Record<string, { current: number; previous: number }>;
  series: Record<string, { date: string; value: number }[]>;
  last_synced: string | null;
}

interface ContentItem {
  id: string;
  type: string;
  locale: string;
  channel: string;
  policy_status: string;
  copy: string;
  image_url: string;
  created_at: string | null;
}

interface Campaign {
  id: string;
  network: string;
  objective: string;
  budget_daily: number;
  currency: string;
  status: string;
  dry_run: boolean;
  created_at: string | null;
}

interface Connection {
  id: string;
  channel: string;
  status: string;
  expires_at: string | null;
}

const METRIC_LABELS: Record<string, string> = {
  impressions: "People Reached",
  engagements: "Engagements",
  clicks: "Website Visits",
  spend: "Ad Spend",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function fmt(n: number, currency = ""): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return currency ? `${currency}${Math.round(n).toLocaleString()}` : Math.round(n).toLocaleString();
}

function delta(t?: { current: number; previous: number }): { pct: number | null } {
  if (!t || t.previous <= 0) return { pct: null };
  return { pct: ((t.current - t.previous) / t.previous) * 100 };
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { brand, brands, isLoading: brandsLoading } = useActiveBrand();
  const [days, setDays] = useState(30);
  const [daysOpen, setDaysOpen] = useState(false);
  const [chartMetric, setChartMetric] = useState("impressions");
  const [chartOpen, setChartOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const queryClient = useQueryClient();

  const { data: metrics } = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary", brand?.id, days],
    queryFn: () => apiGet(`/brands/${brand!.id}/metrics/summary?days=${days}`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const { data: content } = useQuery<ContentItem[]>({
    queryKey: ["brand-content", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/content`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const { data: campaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () => apiGet("/campaigns"),
    retry: 1,
  });

  const { data: connections } = useQuery<Connection[]>({
    queryKey: ["connections"],
    queryFn: () => apiGet("/connections"),
    retry: 1,
  });

  const { data: reviewQueue } = useQuery<unknown[]>({
    queryKey: ["review-queue"],
    queryFn: () => apiGet("/review/queue"),
    retry: 1,
  });

  const expiredConns = (connections ?? []).filter(
    (c) => c.status !== "active" || (c.expires_at && new Date(c.expires_at).getTime() < Date.now()),
  );
  const connectedCount = (connections ?? []).length - expiredConns.length;
  const pendingReviews = (reviewQueue ?? []).length;
  const recentContent = (content ?? []).slice(0, 5);
  const recentCampaigns = (campaigns ?? []).slice(0, 3);
  const draftCount = (content ?? []).filter((c) => c.policy_status !== "passed").length;

  const isNewUser =
    (connections ?? []).length === 0 &&
    (content ?? []).length === 0 &&
    (campaigns ?? []).length === 0;

  // ─── Suggestions (computed from real state, max 3) ─────────────────────────
  const suggestions = useMemo(() => {
    const out: { icon: React.ReactNode; text: string; action: string; href: string }[] = [];
    if (expiredConns.length > 0) {
      out.push({
        icon: <Link2 className="w-4 h-4" />,
        text: `${expiredConns.map((c) => c.channel).join(", ")} access expired — reconnect to keep publishing.`,
        action: "Reconnect",
        href: "/app/connections",
      });
    }
    if ((connections ?? []).length === 0) {
      out.push({
        icon: <Link2 className="w-4 h-4" />,
        text: "No channels connected yet — connecting one lets CURV publish and track performance.",
        action: "Connect a channel",
        href: "/app/connections",
      });
    }
    if (draftCount > 0) {
      out.push({
        icon: <FileText className="w-4 h-4" />,
        text: `You have ${draftCount} unscheduled draft${draftCount > 1 ? "s" : ""} — put them on the calendar.`,
        action: "Open Calendar",
        href: "/app/calendar",
      });
    }
    if ((content ?? []).length === 0) {
      out.push({
        icon: <Sparkles className="w-4 h-4" />,
        text: "Create your first post — CURV writes it in your brand voice.",
        action: "Create Post",
        href: "/app/creative-studio",
      });
    }
    return out.slice(0, 3);
  }, [connections, expiredConns, draftCount, content]);

  // ─── Attention items ───────────────────────────────────────────────────────
  const attention = useMemo(() => {
    const out: { icon: React.ReactNode; text: string; action: string; href: string }[] = [];
    if (pendingReviews > 0) {
      out.push({ icon: <Clock className="w-4 h-4 text-amber-400" />, text: `${pendingReviews} item${pendingReviews > 1 ? "s" : ""} pending your approval`, action: "Review", href: "/app/review" });
    }
    for (const c of expiredConns) {
      out.push({ icon: <XCircle className="w-4 h-4 text-danger" />, text: `${c.channel} connection expired`, action: "Reconnect", href: "/app/connections" });
    }
    return out.slice(0, 4);
  }, [pendingReviews, expiredConns]);

  const chartData = metrics?.series?.[chartMetric] ?? [];
  const hasMetrics = Object.keys(metrics?.totals ?? {}).length > 0;

  const KPIS = [
    { key: "impressions", label: "People Reached", icon: Users, color: "text-sky-400", bg: "bg-sky-500/15" },
    { key: "engagements", label: "Engagements", icon: Heart, color: "text-pink-400", bg: "bg-pink-500/15" },
    { key: "clicks", label: "Website Visits", icon: MousePointerClick, color: "text-emerald-400", bg: "bg-emerald-500/15" },
    { key: "spend", label: "Ad Spend", icon: IndianRupee, color: "text-amber-400", bg: "bg-amber-500/15" },
  ];

  const QUICK = [
    { label: "Create Post", icon: PenSquare, href: "/app/post" },
    { label: "Create Ad", icon: Megaphone, href: "/app/campaigns" },
    { label: "Create Video", icon: VideoIcon, href: "/app/video" },
    { label: "Create Image", icon: ImageIcon, href: "/app/images" },
  ];

  return (
    <div className="space-y-6" onClick={() => { setDaysOpen(false); setChartOpen(false); }}>
      {/* ─── Welcome + quick actions ─── */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">
            {isNewUser ? `Welcome, ${brand?.name ?? "there"}` : `${brand?.name ?? "Dashboard"}`}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {isNewUser ? "Let's get your marketing started." : "Here's how your marketing is doing."}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
          {(brands?.length ?? 0) > 1 && (
            <select
              value={brand?.id ?? ""}
              onChange={(e) => {
                localStorage.setItem("prachar_active_brand", e.target.value);
                window.location.reload();
              }}
              className="px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-xs text-text"
            >
              {(brands ?? []).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
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
            title={metrics?.last_synced ? `Last synced ${timeAgo(metrics.last_synced)}` : "Sync channel metrics"}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-xs text-text-secondary hover:text-text disabled:opacity-50"
            disabled={syncing}
          >
            <RefreshCw className={cn("w-3 h-3", syncing && "animate-spin")} />
            {syncing ? "Syncing" : "Sync"}
          </button>
          <div className="relative">
            <button
              onClick={() => setDaysOpen(!daysOpen)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-xs text-text-secondary hover:text-text"
            >
              Last {days} days <ChevronDown className="w-3 h-3" />
            </button>
            {daysOpen && (
              <div className="absolute right-0 top-full mt-1 z-20 min-w-[130px] rounded-xl border border-line/10 bg-bg-elevated p-1 shadow-xl">
                {[7, 30, 90].map((d) => (
                  <button key={d} onClick={() => { setDays(d); setDaysOpen(false); }} className={cn("w-full text-left px-3 py-2 rounded-lg text-xs", days === d ? "text-accent" : "text-text-secondary hover:bg-bg-hover")}>
                    Last {d} days
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {QUICK.map((q) => (
          <Link
            key={q.label}
            href={q.href}
            className="flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-br from-accent to-accent-dark text-white text-sm font-medium hover:opacity-90 transition-opacity shadow-glow"
          >
            <q.icon className="w-4 h-4" /> {q.label}
          </Link>
        ))}
      </div>

      {/* ─── Onboarding (new user) ─── */}
      {isNewUser && !brandsLoading && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-line/10 bg-bg-card p-6">
          <h2 className="font-display text-lg font-semibold text-text mb-1">Get started in three steps</h2>
          <p className="text-sm text-text-secondary mb-5">Connect a channel, create content, publish — then come back here to watch performance.</p>
          <div className="grid sm:grid-cols-3 gap-3">
            {[
              { n: "1", title: "Connect a channel", desc: "Link Instagram, YouTube, WhatsApp…", href: "/app/connections", icon: Link2 },
              { n: "2", title: "Create content", desc: "CURV writes posts in your brand voice", href: "/app/creative-studio", icon: PenSquare },
              { n: "3", title: "Publish & track", desc: "Schedule it — results appear here", href: "/app/calendar", icon: CheckCircle2 },
            ].map((s) => (
              <Link key={s.n} href={s.href} className="group flex flex-col gap-2 p-4 rounded-xl bg-bg-hover/60 border border-line/10 hover:border-accent/30 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
                  <s.icon className="w-4 h-4 text-accent" />
                </div>
                <div className="text-sm font-medium text-text"><span className="text-accent mr-1.5">{s.n}.</span>{s.title}</div>
                <div className="text-xs text-text-secondary">{s.desc}</div>
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* ─── Main column ─── */}
        <div className="lg:col-span-2 space-y-6">
          {/* KPI cards */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            {KPIS.map((k) => {
              const t = metrics?.totals?.[k.key];
              const d = delta(t);
              return (
                <div key={k.key} className="rounded-2xl border border-line/10 bg-bg-card p-4">
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center mb-3", k.bg)}>
                    <k.icon className={cn("w-4 h-4", k.color)} />
                  </div>
                  <div className="text-xs text-text-secondary">{k.label}</div>
                  {t && t.current > 0 ? (
                    <>
                      <div className="font-display text-xl font-semibold text-text mt-0.5">
                        {k.key === "spend" ? fmt(t.current, "₹") : fmt(t.current)}
                      </div>
                      {d.pct !== null && (
                        <div className={cn("flex items-center gap-0.5 text-[11px] mt-1", d.pct >= 0 ? "text-emerald-400" : "text-danger")}>
                          {d.pct >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          {Math.abs(d.pct).toFixed(0)}% vs previous {days}d
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-xs text-text-muted mt-1.5 leading-snug">
                      No data yet — {k.key === "spend" ? "appears once campaigns run" : "appears after publishing"}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Chart */}
          <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="font-display text-base font-semibold text-text">Marketing Performance</h2>
                <p className="text-xs text-text-muted mt-0.5">Daily trend over the last {days} days</p>
              </div>
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <button onClick={() => setChartOpen(!chartOpen)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-hover text-xs text-text-secondary hover:text-text">
                  {METRIC_LABELS[chartMetric]} <ChevronDown className="w-3 h-3" />
                </button>
                {chartOpen && (
                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[150px] rounded-xl border border-line/10 bg-bg-elevated p-1 shadow-xl">
                    {Object.entries(METRIC_LABELS).map(([k, l]) => (
                      <button key={k} onClick={() => { setChartMetric(k); setChartOpen(false); }} className={cn("w-full text-left px-3 py-2 rounded-lg text-xs", chartMetric === k ? "text-accent" : "text-text-secondary hover:bg-bg-hover")}>
                        {l}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {chartData.length > 0 ? (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                    <defs>
                      <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#ffffff08" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" })} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#64748B" }} tickFormatter={(v) => fmt(v)} axisLine={false} tickLine={false} width={52} />
                    <Tooltip
                      contentStyle={{ background: "#1A1E2A", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: "#94A3B8" }}
                      itemStyle={{ color: "#C4B5FD" }}
                    />
                    <Area type="monotone" dataKey="value" stroke="#8B5CF6" strokeWidth={2} fill="url(#chartFill)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-56 flex flex-col items-center justify-center text-center">
                <Sparkles className="w-6 h-6 text-text-muted mb-2" />
                <p className="text-sm text-text-secondary">Performance data will appear here</p>
                <p className="text-xs text-text-muted mt-1 max-w-xs">
                  {connectedCount === 0
                    ? "Connect a channel and publish — reach, engagement and visits show up automatically."
                    : "Publish content — reach, engagement and visits show up here automatically."}
                </p>
              </div>
            )}
          </div>

          {/* Recent content */}
          <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-base font-semibold text-text">Recent Content</h2>
              <Link href="/app/creative-studio" className="text-xs text-accent hover:underline">View all →</Link>
            </div>
            {recentContent.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {recentContent.map((c) => (
                  <div key={c.id} className="rounded-xl bg-bg-hover/50 border border-line/10 overflow-hidden">
                    <div className="aspect-square bg-white/[0.02] flex items-center justify-center overflow-hidden">
                      {c.image_url ? (
                        <img src={c.image_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <FileText className="w-6 h-6 text-text-muted" />
                      )}
                    </div>
                    <div className="p-2.5">
                      <p className="text-[11px] text-text truncate">{c.copy || "Draft"}</p>
                      <p className="text-[10px] text-text-muted mt-0.5">{c.channel} · {timeAgo(c.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center">
                <FileText className="w-6 h-6 text-text-muted mx-auto mb-2" />
                <p className="text-sm text-text-secondary">No content yet</p>
                <Link href="/app/creative-studio" className="text-xs text-accent hover:underline mt-1 inline-block">Create your first post →</Link>
              </div>
            )}
          </div>

          {/* Recent campaigns */}
          <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-base font-semibold text-text">Recent Campaigns</h2>
              <Link href="/app/campaigns" className="text-xs text-accent hover:underline">View all campaigns →</Link>
            </div>
            {recentCampaigns.length > 0 ? (
              <div className="divide-y divide-white/[0.04]">
                {recentCampaigns.map((c) => (
                  <Link key={c.id} href={`/app/performance/${c.id}`} className="flex items-center gap-4 py-3 hover:bg-bg-hover/40 -mx-2 px-2 rounded-lg transition-colors">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: c.status === "active" ? "#34D399" : c.status === "paused" ? "#FBBF24" : "#64748B" }} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-text truncate">{c.objective} · {c.network}</div>
                      <div className="text-[11px] text-text-muted">{c.status}{c.dry_run ? " (dry run)" : ""} · ₹{Math.round(c.budget_daily).toLocaleString()}/day</div>
                    </div>
                    <div className="text-xs text-text-muted">{timeAgo(c.created_at)}</div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center">
                <Megaphone className="w-6 h-6 text-text-muted mx-auto mb-2" />
                <p className="text-sm text-text-secondary">No campaigns yet</p>
                <Link href="/app/campaigns" className="text-xs text-accent hover:underline mt-1 inline-block">Create an ad campaign →</Link>
              </div>
            )}
          </div>
        </div>

        {/* ─── Right column ─── */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4 text-accent" />
              <h2 className="font-display text-base font-semibold text-text">CURV AI Suggestions</h2>
            </div>
            <div className="space-y-3">
              {suggestions.map((s, i) => (
                <div key={i} className="flex gap-3">
                  <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center shrink-0 text-accent">{s.icon}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-text-secondary leading-relaxed">{s.text}</p>
                    <Link href={s.href} className="text-xs text-accent font-medium hover:underline mt-1 inline-block">{s.action} →</Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {attention.length > 0 && (
            <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h2 className="font-display text-base font-semibold text-text">Needs Your Attention</h2>
                <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-medium">{attention.length}</span>
              </div>
              <div className="space-y-3">
                {attention.map((a, i) => (
                  <div key={i} className="flex gap-3 items-center">
                    <div className="w-7 h-7 rounded-lg bg-white/[0.04] flex items-center justify-center shrink-0">{a.icon}</div>
                    <p className="flex-1 text-xs text-text-secondary">{a.text}</p>
                    <Link href={a.href} className="text-xs text-accent font-medium hover:underline shrink-0">{a.action}</Link>
                  </div>
                ))}
              </div>
            </div>
          )}

          {connectedCount === 0 && !isNewUser && (
            <div className="rounded-2xl border border-line/10 bg-bg-card p-5 text-center">
              <Link2 className="w-6 h-6 text-text-muted mx-auto mb-2" />
              <p className="text-xs text-text-secondary">Connect a channel to start publishing from CURV.</p>
              <Link href="/app/connections" className="mt-3 inline-block px-4 py-2 rounded-xl bg-accent text-white text-xs font-medium">Connect now</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
