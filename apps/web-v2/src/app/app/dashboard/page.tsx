"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { cn } from "@/lib/utils";
import { apiGet, apiPost, apiPatch, apiUpload } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import {
  Users, Heart, MousePointerClick, IndianRupee, AlertTriangle,
  ArrowUpRight, ArrowDownRight, ChevronDown, PenSquare, Megaphone,
  ImageIcon, VideoIcon, Link2, Sparkles, FileText, CheckCircle2,
  Clock, XCircle, RefreshCw, Zap, Camera, Loader2, CalendarDays,
  Radar, Trophy, Wand2, Search,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface MetricsSummary {
  days: number;
  period_start: string;
  totals: Record<string, { current: number; previous: number }>;
  commercial?: {
    impressions: number;
    engagements: number;
    clicks: number;
    conversions: number;
    spend: number;
    revenue: number;
    followers: number;
    ctr: number;
    engagement_rate: number;
    cpc: number;
    cpa: number;
    roas: number;
  };
  by_channel?: {
    channel: string;
    impressions: number;
    engagements: number;
    clicks: number;
    conversions: number;
    spend: number;
    revenue: number;
    ctr: number;
    engagement_rate: number;
    cpa: number;
    roas: number;
  }[];
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
  brand_id?: string;
  channel: string;
  status: string;
  expires_at: string | null;
  account_label?: string | null;
}

interface AutopilotConfig {
  enabled: boolean;
  mode: "full_auto" | "approve_first" | "draft_only";
  posts_per_week: number;
  channels: string[];
  pillars: string[];
  connected_channels: string[];
  next_loop_at: string | null;
  queued_count: number;
}

interface ReadyQueueCard {
  id: string;
  teammate: string;
  badge: string;
  title: string;
  preview: string;
  channel: string;
  scheduled_item_id: string | null;
  state: string;
  cta_label: string;
  action_type: "approve_item" | "open_composer" | "fill_week" | "open_carousel";
}

interface ScheduledItem {
  id: string;
  channel: string;
  text: string;
  scheduled_at: string;
  published_at: string | null;
  state: string;
}

interface VisibilityRadar {
  overall_score: number | null;
  sub_scores: Record<string, number | null> | null;
  gsc: {
    connected: boolean;
    site: string | null;
    quick_wins: { query: string; clicks: number; impressions: number; ctr: number; position: number }[];
    error?: string;
  };
  ai_citations: {
    queries_tested: number;
    brand_mentioned: number;
    citation_rate: number | null;
    probes: { query: string; mentioned: boolean; snippet: string }[];
  };
  recommendations: string[];
}

interface WinnerPost {
  id: string;
  channel: string;
  copy: string;
  media_url: string | null;
  published_at: string | null;
  impressions: number;
  engagements: number;
  score: number;
}

interface CloneVariation {
  angle: string;
  hook: string;
  caption: string;
}

const METRIC_LABELS: Record<string, string> = {
  impressions: "People Reached",
  engagements: "Engagements",
  clicks: "Website Visits",
  conversions: "Conversions & Leads",
  revenue: "Attributed Revenue",
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
  const router = useRouter();
  const snapInputRef = useRef<HTMLInputElement>(null);
  const [days, setDays] = useState(30);
  const [daysOpen, setDaysOpen] = useState(false);
  const [chartMetric, setChartMetric] = useState("impressions");
  const [chartOpen, setChartOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [fillingWeek, setFillingWeek] = useState(false);
  const [savingAutopilot, setSavingAutopilot] = useState(false);
  const [approvingAll, setApprovingAll] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [busyCardId, setBusyCardId] = useState<string | null>(null);
  const [cloning, setCloning] = useState(false);
  const [cloneVariations, setCloneVariations] = useState<CloneVariation[] | null>(null);
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

  const { data: autopilot } = useQuery<AutopilotConfig>({
    queryKey: ["autopilot", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/autopilot`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const { data: readyQueue } = useQuery<{ cards: ReadyQueueCard[] }>({
    queryKey: ["daily-ready-queue", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/daily-ready-queue`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const { data: scheduledItems } = useQuery<ScheduledItem[]>({
    queryKey: ["scheduled-posts", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/scheduled`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const { data: radar } = useQuery<VisibilityRadar>({
    queryKey: ["visibility-radar", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/visibility-radar`),
    enabled: !!brand?.id,
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const { data: winners } = useQuery<{ posts: WinnerPost[]; has_metrics: boolean }>({
    queryKey: ["winner-posts", brand?.id],
    queryFn: () => apiGet(`/brands/${brand!.id}/winner-posts`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const brandConns = useMemo(() => {
    const all = connections ?? [];
    if (!brand?.id) return all;
    const filtered = all.filter((c) => !c.brand_id || c.brand_id === brand.id);
    return filtered.length > 0 ? filtered : all;
  }, [connections, brand?.id]);

  const expiredConns = brandConns.filter((c) => c.status !== "active");
  const activeConns = brandConns.filter((c) => c.status === "active");
  const connectedCount = activeConns.length;
  const pendingReviews = (reviewQueue ?? []).length;
  const recentContent = (content ?? []).slice(0, 5);
  const recentCampaigns = (campaigns ?? []).slice(0, 3);
  const awaitingApprovalCount = (scheduledItems ?? []).filter(
    (s) => !s.published_at && (s.state === "pending_approval" || s.state === "draft")
  ).length;
  const upcomingScheduledCount = (scheduledItems ?? []).filter((s) => !s.published_at).length;
  const draftCount = (content ?? []).filter((c) => c.policy_status !== "passed").length;
  const topWinner = winners?.posts?.[0];

  const updateAutopilot = async (patch: Partial<AutopilotConfig>) => {
    if (!brand?.id || savingAutopilot) return;
    setSavingAutopilot(true);
    try {
      await apiPatch(`/brands/${brand.id}/autopilot`, patch);
      queryClient.invalidateQueries({ queryKey: ["autopilot", brand.id] });
    } finally {
      setSavingAutopilot(false);
    }
  };

  const handleFillWeek = async () => {
    if (!brand?.id || fillingWeek) return;
    setFillingWeek(true);
    try {
      await apiPost(`/brands/${brand.id}/autopilot/fill-week`, {
        posts_per_week: autopilot?.posts_per_week ?? 5,
        mode: autopilot?.mode ?? "approve_first",
      });
      queryClient.invalidateQueries({ queryKey: ["scheduled-posts", brand.id] });
      queryClient.invalidateQueries({ queryKey: ["autopilot", brand.id] });
      queryClient.invalidateQueries({ queryKey: ["daily-ready-queue", brand.id] });
    } finally {
      setFillingWeek(false);
    }
  };

  const handleApproveAll = async () => {
    if (!brand?.id || approvingAll) return;
    setApprovingAll(true);
    try {
      await apiPost(`/brands/${brand.id}/autopilot/approve-all`, {});
      queryClient.invalidateQueries({ queryKey: ["scheduled-posts", brand.id] });
      queryClient.invalidateQueries({ queryKey: ["daily-ready-queue", brand.id] });
    } finally {
      setApprovingAll(false);
    }
  };

  const handleSnapProduct = async (f: File | null) => {
    if (!f || !brand?.id) return;
    setSnapping(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await apiUpload<{ caption: string; media_urls: string[] }>(
        `/brands/${brand.id}/snap-to-campaign`,
        fd
      );
      const urlsParam = encodeURIComponent((res.media_urls || []).join(","));
      const capParam = encodeURIComponent(res.caption || "");
      router.push(`/app/post?media_urls=${urlsParam}&caption=${capParam}`);
    } finally {
      setSnapping(false);
      if (snapInputRef.current) snapInputRef.current.value = "";
    }
  };

  const handleReadyCard = async (card: ReadyQueueCard) => {
    if (!brand?.id || busyCardId) return;
    if (card.action_type === "open_composer" || card.action_type === "open_carousel") {
      router.push(`/app/post?caption=${encodeURIComponent(card.preview)}`);
      return;
    }
    setBusyCardId(card.id);
    try {
      if (card.action_type === "approve_item" && card.scheduled_item_id) {
        await apiPost(`/brands/${brand.id}/schedule/${card.scheduled_item_id}/approve`, {});
        queryClient.invalidateQueries({ queryKey: ["scheduled-posts", brand.id] });
        queryClient.invalidateQueries({ queryKey: ["daily-ready-queue", brand.id] });
      } else if (card.action_type === "fill_week") {
        await handleFillWeek();
      }
    } finally {
      setBusyCardId(null);
    }
  };

  const handleCloneWinner = async (post: WinnerPost) => {
    if (!brand?.id || cloning) return;
    setCloning(true);
    setCloneVariations(null);
    try {
      const res = await apiPost<{ variations: CloneVariation[] }>(
        `/brands/${brand.id}/clone-winner`,
        { content_item_id: post.id, channel: post.channel, count: 3 }
      );
      setCloneVariations(res.variations ?? []);
    } finally {
      setCloning(false);
    }
  };

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
                localStorage.setItem("prachar_active_brand_id", e.target.value);
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

      {/* ─── Quick Actions + Snap Product → Campaign ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {QUICK.map((q) => (
          <Link
            key={q.label}
            href={q.href}
            className="flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-br from-accent to-accent-dark text-white text-sm font-medium hover:opacity-90 transition-opacity shadow-glow"
          >
            <q.icon className="w-4 h-4" /> {q.label}
          </Link>
        ))}
        <button
          type="button"
          disabled={snapping || !brand?.id}
          onClick={() => snapInputRef.current?.click()}
          className="col-span-2 lg:col-span-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-300 text-sm font-semibold hover:bg-amber-500/30 transition disabled:opacity-50"
          title="Upload 1 product photo → AI creates a 3-slide carousel + caption"
        >
          {snapping ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Building…</>
          ) : (
            <><Camera className="w-4 h-4" /> Snap Product</>
          )}
        </button>
        <input
          ref={snapInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleSnapProduct(e.target.files?.[0] ?? null)}
        />
      </div>

      {/* ─── Social Autopilot Control Strip ─── */}
      {autopilot && (
        <div className="rounded-2xl border border-accent/25 bg-gradient-to-r from-accent/[0.08] via-bg-card to-bg-card p-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex items-start sm:items-center gap-3">
              <button
                type="button"
                disabled={savingAutopilot}
                onClick={() => updateAutopilot({ enabled: !autopilot.enabled })}
                className={cn(
                  "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200",
                  autopilot.enabled ? "bg-emerald-500" : "bg-white/15"
                )}
                aria-label="Toggle Social Autopilot"
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200",
                    autopilot.enabled ? "translate-x-5" : "translate-x-0"
                  )}
                />
              </button>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-display text-sm font-semibold text-text">
                    Social Autopilot
                  </span>
                  <span
                    className={cn(
                      "text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider",
                      autopilot.enabled
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-white/10 text-text-muted"
                    )}
                  >
                    {autopilot.enabled ? "Active" : "Paused"}
                  </span>
                  <span className="text-xs text-text-muted">
                    · {upcomingScheduledCount} post{upcomingScheduledCount === 1 ? "" : "s"} queued on calendar
                  </span>
                </div>
                <p className="text-xs text-text-secondary mt-0.5">
                  CURV AI writes in your brand voice, slots posts at peak platform hours, and publishes on your rules.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex bg-white/[0.04] rounded-lg p-0.5 border border-white/[0.06]">
                {(
                  [
                    { id: "draft_only", label: "Drafts Only" },
                    { id: "approve_first", label: "Approve First" },
                    { id: "full_auto", label: "Full Autopilot" },
                  ] as const
                ).map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    disabled={savingAutopilot}
                    onClick={() => updateAutopilot({ mode: m.id })}
                    className={cn(
                      "px-2.5 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap",
                      autopilot.mode === m.id
                        ? "bg-accent text-white"
                        : "text-text-secondary hover:text-text"
                    )}
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              <select
                value={autopilot.posts_per_week}
                disabled={savingAutopilot}
                onChange={(e) => updateAutopilot({ posts_per_week: Number(e.target.value) })}
                className="bg-white/[0.04] text-text text-xs rounded-lg px-2.5 py-2 border border-white/[0.06] outline-none"
              >
                {[3, 5, 7, 10, 14].map((n) => (
                  <option key={n} value={n} className="bg-bg-card">
                    {n} posts / wk
                  </option>
                ))}
              </select>

              {awaitingApprovalCount > 0 && (
                <button
                  type="button"
                  onClick={handleApproveAll}
                  disabled={approvingAll}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-semibold hover:bg-emerald-500/30 transition disabled:opacity-50"
                >
                  {approvingAll ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Approving…</>
                  ) : (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> Approve All ({awaitingApprovalCount})</>
                  )}
                </button>
              )}

              <button
                type="button"
                onClick={handleFillWeek}
                disabled={fillingWeek}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-br from-accent to-amber-500 text-white text-xs font-semibold hover:opacity-90 transition disabled:opacity-50"
              >
                {fillingWeek ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Filling Week…</>
                ) : (
                  <><Zap className="w-3.5 h-3.5" /> Fill My Week</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── AI Teammates: Ready for Your 1-Tap Approval Today ─── */}
      {(readyQueue?.cards?.length ?? 0) > 0 && (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-sm font-semibold text-text flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent" />
              Your AI Team · Ready for 1-Tap Approval Today
            </h2>
            <Link href="/app/calendar" className="text-xs text-accent hover:underline flex items-center gap-1">
              <CalendarDays className="w-3.5 h-3.5" /> Open Calendar →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(readyQueue?.cards ?? []).map((card) => (
              <div
                key={card.id}
                className="rounded-2xl border border-line/10 bg-bg-card p-4 flex flex-col justify-between gap-3 hover:border-accent/30 transition"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-[11px] font-semibold text-accent">{card.teammate}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-text-secondary">
                      {card.badge}
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-text mb-1">{card.title}</div>
                  <p className="text-xs text-text-secondary line-clamp-3 leading-relaxed">
                    {card.preview}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busyCardId === card.id}
                  onClick={() => handleReadyCard(card)}
                  className="w-full py-2 px-3 rounded-xl bg-accent/15 border border-accent/30 text-accent text-xs font-semibold hover:bg-accent/25 transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  {busyCardId === card.id ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Working…</>
                  ) : (
                    <><CheckCircle2 className="w-3.5 h-3.5" /> {card.cta_label}</>
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

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

          {/* Commercial ROI & Efficiency Strip */}
          <div className="rounded-2xl border border-line/10 bg-bg-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <IndianRupee className="w-4 h-4 text-emerald-400" />
                <span className="font-display text-sm font-semibold text-text">Commercial Metrics &amp; ROI</span>
              </div>
              <Link href="/app/analytics" className="text-xs text-accent hover:underline font-medium">
                Full ROI &amp; Log Conversions →
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl bg-white/[0.02] border border-line/10 p-3">
                <div className="text-[11px] text-text-secondary">Conversions / Leads</div>
                <div className="font-display text-lg font-semibold text-text mt-0.5">
                  {metrics?.commercial?.conversions ? fmt(metrics.commercial.conversions) : "0"}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">
                  {metrics?.commercial?.cpa ? `CPA ₹${metrics.commercial.cpa}` : "Pixel + logged leads"}
                </div>
              </div>
              <div className="rounded-xl bg-white/[0.02] border border-line/10 p-3">
                <div className="text-[11px] text-text-secondary">Attributed Revenue</div>
                <div className="font-display text-lg font-semibold text-emerald-400 mt-0.5">
                  {metrics?.commercial?.revenue ? fmt(metrics.commercial.revenue, "₹") : "₹0"}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">Last {days} days</div>
              </div>
              <div className="rounded-xl bg-white/[0.02] border border-line/10 p-3">
                <div className="text-[11px] text-text-secondary">ROAS (Return on Spend)</div>
                <div className="font-display text-lg font-semibold text-accent mt-0.5">
                  {metrics?.commercial?.roas ? `${metrics.commercial.roas.toFixed(2)}x` : "—"}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">
                  {metrics?.commercial?.spend ? `on ${fmt(metrics.commercial.spend, "₹")} spend` : "Log spend or run ads"}
                </div>
              </div>
              <div className="rounded-xl bg-white/[0.02] border border-line/10 p-3">
                <div className="text-[11px] text-text-secondary">CTR &amp; Engagement Rate</div>
                <div className="font-display text-lg font-semibold text-sky-400 mt-0.5">
                  {metrics?.commercial?.ctr ? `${metrics.commercial.ctr}%` : "0%"}
                  <span className="text-xs text-text-muted font-normal"> CTR</span>
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">
                  {metrics?.commercial?.engagement_rate ?? 0}% engagement rate
                </div>
              </div>
            </div>
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

          {/* Winner Engine — Clone What Works */}
          {topWinner && (
            <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Trophy className="w-4 h-4 text-amber-400" />
                  <h2 className="font-display text-base font-semibold text-text">Winner Engine — Clone What Works</h2>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-text-muted">
                  {winners?.has_metrics ? "ranked by real engagement" : "recent posts"}
                </span>
              </div>
              <div className="flex items-start gap-3 rounded-xl bg-bg-hover/50 border border-line/10 p-3.5">
                <div className="w-12 h-12 rounded-lg bg-white/[0.04] flex items-center justify-center overflow-hidden shrink-0">
                  {topWinner.media_url ? (
                    <img src={topWinner.media_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <FileText className="w-5 h-5 text-text-muted" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent font-semibold capitalize">
                      {topWinner.channel}
                    </span>
                    {topWinner.engagements > 0 && (
                      <span className="text-[10px] text-emerald-400 font-medium">
                        {fmt(topWinner.engagements)} engagements · {fmt(topWinner.impressions)} reached
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
                    {topWinner.copy || "Published post"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleCloneWinner(topWinner)}
                  disabled={cloning}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gradient-to-br from-accent to-amber-500 text-white text-xs font-semibold hover:opacity-90 transition disabled:opacity-50"
                >
                  {cloning ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Cloning…</>
                  ) : (
                    <><Wand2 className="w-3.5 h-3.5" /> Clone ×3</>
                  )}
                </button>
              </div>

              {cloneVariations && cloneVariations.length > 0 && (
                <div className="mt-3 space-y-2.5">
                  <p className="text-[11px] text-text-muted">Fresh variations of your winning structure:</p>
                  {cloneVariations.map((v, i) => (
                    <div key={i} className="rounded-xl border border-line/10 bg-bg-hover/40 p-3">
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 font-semibold">{v.angle}</span>
                        <button
                          type="button"
                          onClick={() => router.push(`/app/post?caption=${encodeURIComponent(v.caption)}`)}
                          className="text-[11px] text-accent font-medium hover:underline shrink-0"
                        >
                          Use in Composer →
                        </button>
                      </div>
                      <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">{v.caption}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

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
          {/* Connected Channels live card */}
          <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-emerald-400" />
                <h2 className="font-display text-base font-semibold text-text">Connected Channels</h2>
              </div>
              <Link href="/app/connections" className="text-xs text-accent hover:underline">
                Manage →
              </Link>
            </div>
            {activeConns.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {activeConns.map((c) => (
                  <span
                    key={c.id}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-xs text-emerald-300 font-medium capitalize"
                  >
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    {c.channel}
                    {c.account_label ? <span className="text-text-muted font-normal">· {c.account_label}</span> : null}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-text-secondary">
                No active channels on this brand yet — switch brand above or connect a channel.
              </p>
            )}
          </div>

          {/* AI & Google Visibility Radar */}
          {radar && (
            <div className="rounded-2xl border border-line/10 bg-bg-card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Radar className="w-4 h-4 text-sky-400" />
                  <h2 className="font-display text-base font-semibold text-text">AI & Google Visibility</h2>
                </div>
                {radar.overall_score != null && (
                  <span className="font-display text-lg font-bold text-sky-300">
                    {Math.round(radar.overall_score)}
                    <span className="text-[10px] text-text-muted font-normal">/100</span>
                  </span>
                )}
              </div>

              {radar.sub_scores && (
                <div className="space-y-2">
                  {(
                    [
                      ["organic_rank_index", "Google rank"],
                      ["ai_citation_rate", "AI citations"],
                      ["social_reach_index", "Social reach"],
                    ] as const
                  ).map(([key, label]) => {
                    const val = radar.sub_scores?.[key];
                    if (val == null) return null;
                    const pct = Math.max(0, Math.min(100, val));
                    return (
                      <div key={key}>
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="text-text-secondary">{label}</span>
                          <span className="text-text-muted">{Math.round(val)}/100</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              pct >= 70 ? "bg-emerald-400" : pct >= 40 ? "bg-amber-400" : "bg-sky-400"
                            )}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {radar.ai_citations.queries_tested > 0 && (
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-3 space-y-2">
                  <div className="text-[11px] font-semibold text-text">
                    ChatGPT-style AI answers cited {brand?.name ?? "your brand"} in{" "}
                    {radar.ai_citations.brand_mentioned}/{radar.ai_citations.queries_tested} buyer questions
                  </div>
                  {radar.ai_citations.probes.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-[11px]">
                      {p.mentioned ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-text-muted shrink-0" />
                      )}
                      <span className="text-text-secondary truncate">"{p.query}"</span>
                    </div>
                  ))}
                </div>
              )}

              {radar.gsc.connected && radar.gsc.quick_wins.length > 0 && (
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-3 space-y-2">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text">
                    <Search className="w-3.5 h-3.5 text-emerald-400" />
                    Google quick wins{radar.gsc.site ? ` · ${radar.gsc.site.replace(/^https?:\/\//, "").replace(/\/$/, "")}` : ""}
                  </div>
                  {radar.gsc.quick_wins.slice(0, 3).map((q, i) => (
                    <div key={i} className="flex items-center justify-between gap-2 text-[11px]">
                      <span className="text-text-secondary truncate">"{q.query}"</span>
                      <span className="text-text-muted shrink-0">
                        rank #{Math.round(q.position)} · {fmt(q.impressions)} imp
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {radar.recommendations.slice(0, 2).map((r, i) => (
                <p key={i} className="text-[11px] text-text-secondary leading-relaxed flex gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" /> {r}
                </p>
              ))}

              {!radar.gsc.connected && (
                <Link
                  href="/app/connections"
                  className="block text-center py-2 rounded-xl bg-sky-500/15 border border-sky-500/30 text-xs font-semibold text-sky-300 hover:bg-sky-500/25 transition"
                >
                  Connect Search Console →
                </Link>
              )}
            </div>
          )}

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
