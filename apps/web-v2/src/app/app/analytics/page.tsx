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
  BarChart3,
  Clock,
  RefreshCw,
  IndianRupee,
  MousePointerClick,
  Heart,
  Plus,
  Check,
  Copy,
  Layers,
  Award,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface ChannelMetricRow {
  channel: string;
  impressions: number;
  engagements: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  followers: number;
  ctr: number;
  engagement_rate: number;
  cpa: number;
  roas: number;
}

interface MetricsSummary {
  days: number;
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
  by_channel?: ChannelMetricRow[];
  series: Record<string, { date: string; value: number }[]>;
  last_synced: string | null;
}

const fmtNum = (n: number, prefix = "") => {
  if (n >= 1_000_000) return `${prefix}${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${prefix}${(n / 1_000).toFixed(1)}K`;
  return `${prefix}${Math.round(n).toLocaleString()}`;
};

const SERIES_LABELS: Record<string, string> = {
  impressions: "People Reached",
  engagements: "Engagements",
  clicks: "Website Clicks",
  conversions: "Conversions & Leads",
  revenue: "Revenue (₹)",
  spend: "Ad Spend (₹)",
};

export default function ResultsPage() {
  const { brand, brands, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);
  const [days, setDays] = useState(30);
  const [chartMetric, setChartMetric] = useState("impressions");
  const [syncing, setSyncing] = useState(false);
  const [showLogModal, setShowLogModal] = useState(false);
  const [logChannel, setLogChannel] = useState("whatsapp");
  const [logConversions, setLogConversions] = useState("1");
  const [logRevenue, setLogRevenue] = useState("");
  const [logSpend, setLogSpend] = useState("");
  const [logNote, setLogNote] = useState("");
  const [savingLog, setSavingLog] = useState(false);
  const [copiedPixel, setCopiedPixel] = useState(false);
  const queryClient = useQueryClient();

  const { data: metrics } = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary", brand?.id, days],
    queryFn: () => apiGet(`/brands/${brand!.id}/metrics/summary?days=${days}`),
    enabled: !!brand?.id,
    retry: 1,
  });

  const isLoading = brandLoading || plansLoading;
  const totalCampaigns = plans?.length ?? 0;

  const comm = metrics?.commercial;
  const reached = comm?.impressions ?? metrics?.totals?.impressions?.current ?? 0;
  const engagements = comm?.engagements ?? metrics?.totals?.engagements?.current ?? 0;
  const clicks = comm?.clicks ?? metrics?.totals?.clicks?.current ?? 0;
  const conversions = comm?.conversions ?? metrics?.totals?.conversions?.current ?? 0;
  const revenue = comm?.revenue ?? metrics?.totals?.revenue?.current ?? 0;
  const spend = comm?.spend ?? metrics?.totals?.spend?.current ?? 0;
  const roas = comm?.roas ?? (spend > 0 ? revenue / spend : 0);
  const cpa = comm?.cpa ?? (conversions > 0 ? spend / conversions : 0);
  const cpc = comm?.cpc ?? (clicks > 0 ? spend / clicks : 0);
  const ctr = comm?.ctr ?? (reached > 0 ? (clicks / reached) * 100 : 0);
  const engRate = comm?.engagement_rate ?? (reached > 0 ? (engagements / reached) * 100 : 0);

  const chartData = metrics?.series?.[chartMetric] ?? [];
  const byChannel = metrics?.by_channel ?? [];

  const handleRecordConversion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brand?.id || savingLog) return;
    setSavingLog(true);
    try {
      await apiPost(`/brands/${brand.id}/metrics/record-conversion`, {
        channel: logChannel,
        conversions: Number(logConversions) || 0,
        revenue: Number(logRevenue) || 0,
        spend: Number(logSpend) || 0,
        note: logNote.trim(),
      });
      queryClient.invalidateQueries({ queryKey: ["metrics-summary"] });
      setShowLogModal(false);
      setLogRevenue("");
      setLogSpend("");
      setLogNote("");
    } finally {
      setSavingLog(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
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
        <p className="text-sm text-text-secondary mb-6">Create a brand to see your commercial results.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  const pixelSnippet = `<script src="https://app.curvai.org/api/pixel.js" data-brand-id="${brand.id}" async></script>`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Commercial Metrics &amp; ROI</h1>
          <p className="text-sm text-text-secondary mt-1">
            Full-funnel reach, engagement, conversions, ad spend, and ROAS for {brand.name}.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {(brands?.length ?? 0) > 1 && (
            <select
              value={brand.id}
              onChange={(e) => {
                localStorage.setItem("prachar_active_brand", e.target.value);
                localStorage.setItem("prachar_active_brand_id", e.target.value);
                window.location.reload();
              }}
              className="px-3 py-1.5 rounded-lg border border-line/10 bg-bg-card text-xs text-text"
            >
              {(brands ?? []).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
          <div className="flex bg-bg-card rounded-lg p-0.5 border border-line/10">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition",
                  days === d ? "bg-accent text-white" : "text-text-secondary hover:text-text"
                )}
              >
                {d}d
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowLogModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/30 transition"
          >
            <Plus className="w-3.5 h-3.5" /> Log Sale / Spend
          </button>
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
            {syncing ? "Syncing…" : "Sync Channels"}
          </button>
        </div>
      </div>

      {/* 8-Card Commercial & Growth KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ResultCard
          icon={<Eye className="w-4 h-4" />}
          label="People Reached"
          value={fmtNum(reached)}
          sub={`Last ${days}d — impressions + views`}
          accent="text-sky-400"
        />
        <ResultCard
          icon={<Heart className="w-4 h-4" />}
          label="Engagements"
          value={fmtNum(engagements)}
          sub={`${engRate.toFixed(1)}% engagement rate`}
          accent="text-pink-400"
        />
        <ResultCard
          icon={<MousePointerClick className="w-4 h-4" />}
          label="Website Clicks"
          value={fmtNum(clicks)}
          sub={`${ctr.toFixed(2)}% click-through rate (CTR)`}
          accent="text-emerald-400"
        />
        <ResultCard
          icon={<Target className="w-4 h-4" />}
          label="Conversions & Leads"
          value={fmtNum(conversions)}
          sub={cpa > 0 ? `₹${cpa.toFixed(0)} cost per acquisition` : "Pixel + WhatsApp/DM leads"}
          accent="text-amber-400"
        />
        <ResultCard
          icon={<IndianRupee className="w-4 h-4" />}
          label="Attributed Revenue"
          value={fmtNum(revenue, "₹")}
          sub={`Last ${days}d gross attributed sales`}
          accent="text-emerald-400"
        />
        <ResultCard
          icon={<IndianRupee className="w-4 h-4" />}
          label="Ad Spend"
          value={fmtNum(spend, "₹")}
          sub={cpc > 0 ? `₹${cpc.toFixed(1)} avg cost per click (CPC)` : "Across connected ad networks"}
          accent="text-amber-400"
        />
        <ResultCard
          icon={<Award className="w-4 h-4" />}
          label="ROAS (Return on Spend)"
          value={spend > 0 ? `${roas.toFixed(2)}x` : "—"}
          sub={spend > 0 ? `₹${roas.toFixed(2)} earned per ₹1 spent` : "Log spend & revenue to track"}
          accent="text-accent"
        />
        <ResultCard
          icon={<TrendingUp className="w-4 h-4" />}
          label="Visibility Score"
          value={brand.visibility_score != null ? `${brand.visibility_score.toFixed(0)}/100` : "—"}
          sub="Search + AI Citation + Social index"
          accent="text-sky-400"
        />
      </div>

      {/* Interactive Trend Chart */}
      <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">Commercial &amp; Reach Trend</h2>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(SERIES_LABELS).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setChartMetric(k)}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-medium transition",
                  chartMetric === k ? "bg-accent text-white" : "bg-bg-hover text-text-secondary hover:text-text"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {chartData.length > 0 ? (
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="reachFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#ffffff08" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#64748B" }}
                  stroke="transparent"
                  tickLine={false}
                  tickFormatter={(d: string) => d.slice(5)}
                />
                <YAxis tick={{ fontSize: 10, fill: "#64748B" }} stroke="transparent" tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "#13131f",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Area type="monotone" dataKey="value" stroke="#8b5cf6" strokeWidth={2} fill="url(#reachFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-44 flex flex-col items-center justify-center text-center">
            <p className="text-sm text-text-secondary">
              No daily points for {SERIES_LABELS[chartMetric]} yet — click &ldquo;Sync Channels&rdquo; or &ldquo;Log Sale / Spend&rdquo; above.
            </p>
          </div>
        )}
      </div>

      {/* Channel-by-Channel Commercial Breakdown Table */}
      <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">Channel-by-Channel ROI Breakdown</h2>
          </div>
          <span className="text-xs text-text-muted">Last {days} days</span>
        </div>
        {byChannel.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line/10 text-text-muted">
                  <th className="py-2.5 pr-4 font-medium">Channel</th>
                  <th className="py-2.5 px-3 font-medium text-right">Reach / Views</th>
                  <th className="py-2.5 px-3 font-medium text-right">Engagements</th>
                  <th className="py-2.5 px-3 font-medium text-right">Clicks (CTR)</th>
                  <th className="py-2.5 px-3 font-medium text-right">Conversions</th>
                  <th className="py-2.5 px-3 font-medium text-right">Spend</th>
                  <th className="py-2.5 px-3 font-medium text-right">Revenue</th>
                  <th className="py-2.5 pl-3 font-medium text-right">ROAS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {byChannel.map((row) => (
                  <tr key={row.channel} className="hover:bg-white/[0.02]">
                    <td className="py-3 pr-4 font-semibold text-text capitalize">{row.channel.replace("_", " ")}</td>
                    <td className="py-3 px-3 text-right tabular-nums text-text-secondary">{fmtNum(row.impressions)}</td>
                    <td className="py-3 px-3 text-right tabular-nums text-text-secondary">
                      {fmtNum(row.engagements)}
                      {row.engagement_rate > 0 && (
                        <span className="text-[10px] text-text-muted ml-1">({row.engagement_rate}%)</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right tabular-nums text-text-secondary">
                      {fmtNum(row.clicks)}
                      {row.ctr > 0 && <span className="text-[10px] text-text-muted ml-1">({row.ctr}%)</span>}
                    </td>
                    <td className="py-3 px-3 text-right tabular-nums text-text">{fmtNum(row.conversions)}</td>
                    <td className="py-3 px-3 text-right tabular-nums text-text-secondary">{fmtNum(row.spend, "₹")}</td>
                    <td className="py-3 px-3 text-right tabular-nums text-emerald-400 font-medium">{fmtNum(row.revenue, "₹")}</td>
                    <td className="py-3 pl-3 text-right tabular-nums font-semibold text-accent">
                      {row.roas > 0 ? `${row.roas.toFixed(2)}x` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-6 text-center text-xs text-text-secondary">
            Click <strong>Sync Channels</strong> to pull live reach &amp; engagement from your connected accounts, or click <strong>+ Log Sale / Spend</strong> to record commercial conversions.
          </div>
        )}
      </div>

      {/* First-Party Attribution Pixel Card */}
      <div className="rounded-2xl border border-line/10 bg-bg-card p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="font-display text-sm font-semibold text-text">First-Party Revenue &amp; Conversion Pixel (40/20/40 Attribution)</h3>
          <p className="text-xs text-text-secondary mt-1">
            Paste this 1-line snippet on your website or checkout page to automatically attribute `gclid`, `fbclid`, `ttclid`, and UTM sales into your ROAS &amp; CPA metrics.
          </p>
          <code className="mt-2 block text-[11px] text-accent bg-bg-hover px-3 py-2 rounded-lg font-mono overflow-x-auto">
            {pixelSnippet}
          </code>
        </div>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard.writeText(pixelSnippet);
            setCopiedPixel(true);
            setTimeout(() => setCopiedPixel(false), 2000);
          }}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-accent/15 border border-accent/30 text-xs font-semibold text-accent hover:bg-accent/25 transition shrink-0"
        >
          {copiedPixel ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy Pixel</>}
        </button>
      </div>

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

      {/* Log Conversion / Sale / Spend Modal */}
      {showLogModal && (
        <div
          onClick={() => setShowLogModal(false)}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleRecordConversion}
            className="w-full max-w-md rounded-2xl border border-line/10 bg-bg-elevated p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-display text-base font-semibold text-text">Log Commercial Conversion / Spend</h3>
              <button
                type="button"
                onClick={() => setShowLogModal(false)}
                className="text-xs text-text-muted hover:text-text"
              >
                Close
              </button>
            </div>
            <p className="text-xs text-text-secondary">
              Record WhatsApp/DM orders, store sales, or offline ad spend so your ROAS and CPA stay accurate.
            </p>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-text-secondary mb-1">Channel</label>
                <select
                  value={logChannel}
                  onChange={(e) => setLogChannel(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-text"
                >
                  <option value="whatsapp">WhatsApp</option>
                  <option value="instagram">Instagram</option>
                  <option value="facebook">Facebook</option>
                  <option value="meta_ads">Meta Ads</option>
                  <option value="google_ads">Google Ads</option>
                  <option value="youtube">YouTube</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="x">X (Twitter)</option>
                  <option value="direct">Website / Direct</option>
                </select>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-text-secondary mb-1">Conversions</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={logConversions}
                    onChange={(e) => setLogConversions(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-text"
                  />
                </div>
                <div>
                  <label className="block text-text-secondary mb-1">Revenue (₹)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0"
                    value={logRevenue}
                    onChange={(e) => setLogRevenue(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-text"
                  />
                </div>
                <div>
                  <label className="block text-text-secondary mb-1">Ad Spend (₹)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0"
                    value={logSpend}
                    onChange={(e) => setLogSpend(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-text"
                  />
                </div>
              </div>
              <div>
                <label className="block text-text-secondary mb-1">Note (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Diwali offer WhatsApp order"
                  value={logNote}
                  onChange={(e) => setLogNote(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-text"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowLogModal(false)}
                className="px-4 py-2 rounded-xl bg-bg-hover text-xs text-text-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingLog}
                className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50"
              >
                {savingLog ? "Saving…" : "Save Metrics"}
              </button>
            </div>
          </form>
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
    <div className={`rounded-2xl border border-line/10 bg-bg-card p-5 transition-all ${dimmed ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={accent}>{icon}</span>
        <span className="text-xs text-text-secondary font-medium">{label}</span>
      </div>
      <div className="font-display text-2xl font-semibold text-text tabular-nums">{value}</div>
      <div className="text-[11px] text-text-muted mt-1.5">{sub}</div>
    </div>
  );
}
