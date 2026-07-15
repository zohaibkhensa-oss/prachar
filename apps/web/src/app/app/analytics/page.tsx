"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  BarChart3,
  Download,
  TrendingUp,
  DollarSign,
  Target,
  MousePointerClick,
  Globe,
  Users,
  Zap,
  Eye,
} from "lucide-react";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric, MetricMini } from "@/components/ui/metric";
import { PerformanceRing, ProgressBar } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/* ────────────────────────────── Mock data ────────────────────────────── */

const RANGES = ["7d", "30d", "90d", "Custom"];

const TREND_DATA = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  spend: Math.round(8000 + Math.sin(i / 3) * 2200 + i * 180 + Math.random() * 800),
  conversions: Math.round(120 + Math.sin(i / 4) * 40 + i * 4 + Math.random() * 20),
}));

const CHANNEL_PERF = [
  { name: "Google", spend: 184, conversions: 420 },
  { name: "YouTube", spend: 93, conversions: 280 },
  { name: "Instagram", spend: 65, conversions: 310 },
  { name: "TikTok", spend: 39, conversions: 240 },
  { name: "Facebook", spend: 41, conversions: 150 },
  { name: "LinkedIn", spend: 22, conversions: 60 },
  { name: "X", spend: 8, conversions: 22 },
];

const VISIBILITY_TREND = Array.from({ length: 30 }, (_, i) => ({
  day: `D${i + 1}`,
  score: Math.round(58 + Math.sin(i / 5) * 8 + i * 0.6 + Math.random() * 3),
}));

const CHANNEL_BREAKDOWN = [
  { name: "Google Ads", pct: 40, color: "#3B82F6" },
  { name: "YouTube", pct: 20, color: "#EF4444" },
  { name: "Instagram", pct: 14, color: "#FFD400" },
  { name: "TikTok", pct: 9, color: "#22C55E" },
  { name: "Facebook", pct: 9, color: "#3B82F6" },
  { name: "LinkedIn", pct: 5, color: "#94A3B8" },
  { name: "X", pct: 3, color: "#94A3B8" },
];

// Heatmap: 7 days × 24 hours
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HEATMAP = DAYS.map((d) => ({
  day: d,
  hours: Array.from({ length: 24 }, (_, h) => {
    // peak around 9-11am and 7-10pm, weekends lower
    const morning = Math.exp(-Math.pow(h - 10, 2) / 8);
    const evening = Math.exp(-Math.pow(h - 20, 2) / 6);
    const weekend = d === "Sat" || d === "Sun" ? 0.6 : 1;
    const val = (morning * 0.6 + evening * 0.8) * weekend + Math.random() * 0.15;
    return Math.min(1, Math.max(0, val));
  }),
}));

const RINGS = [
  { label: "Organic", value: 78, accent: "#22C55E", sublabel: "Visibility" },
  { label: "Paid", value: 92, accent: "#FFD400", sublabel: "ROAS" },
  { label: "Social", value: 64, accent: "#3B82F6", sublabel: "Engagement" },
  { label: "AI Citation", value: 71, accent: "#EF4444", sublabel: "Mentions" },
];

function heatColor(v: number) {
  // 0 -> dark, 1 -> accent
  if (v < 0.15) return "rgba(255,255,255,0.03)";
  if (v < 0.35) return "rgba(255,212,0,0.18)";
  if (v < 0.55) return "rgba(255,212,0,0.38)";
  if (v < 0.75) return "rgba(255,212,0,0.62)";
  return "rgba(255,212,0,0.9)";
}

const tooltipStyle = {
  backgroundColor: "#161B22",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#F9FAFB",
};

/* ────────────────────────────── Page ────────────────────────────── */

export default function AnalyticsPage() {
  const [range, setRange] = useState("30d");

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-text flex items-center gap-3">
            <BarChart3 className="w-7 h-7 text-accent" />
            Analytics
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Cross-channel performance intelligence, in real time.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.04]">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                  range === r ? "bg-accent text-bg" : "text-text-secondary hover:text-text",
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <button className="btn-secondary flex items-center gap-2 text-xs">
            <Download className="w-4 h-4" /> Export
          </button>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Metric label="ROAS" value={4.2} suffix="x" delta={12.4} deltaLabel="vs last" icon={<TrendingUp className="w-4 h-4" />} accent="accent" />
        <Metric label="CPA" value={487} format="currency" delta={-8.1} deltaLabel="vs last" icon={<Target className="w-4 h-4" />} accent="success" />
        <Metric label="CTR" value={3.8} format="percent" delta={5.2} deltaLabel="vs last" icon={<MousePointerClick className="w-4 h-4" />} accent="info" />
        <Metric label="Revenue" value={2840000} format="currency" delta={18.6} deltaLabel="vs last" icon={<DollarSign className="w-4 h-4" />} accent="default" />
      </div>

      {/* Performance rings */}
      <div className="mb-8">
        <SectionHeader
          title="Performance Rings"
          subtitle="Multi-dimensional visibility across channels"
          icon={<Eye className="w-4 h-4" />}
        />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
          {RINGS.map((r, i) => (
            <motion.div
              key={r.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08, duration: 0.4 }}
            >
              <Card3D className="flex flex-col items-center text-center">
                <PerformanceRing
                  value={r.value}
                  size={130}
                  label={`${r.value}`}
                  sublabel={r.sublabel}
                  accent={r.accent}
                />
                <div className="mt-3 font-display text-sm font-medium text-text">{r.label}</div>
              </Card3D>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Trend charts */}
      <div className="mb-8">
        <SectionHeader
          title="Trend Charts"
          subtitle="Spend, conversions, and visibility over time"
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Area: spend vs conversions */}
          <Card3D>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-display text-sm font-medium text-text">Spend vs Conversions</div>
                <div className="text-[10px] text-text-muted font-mono">Last 30 days</div>
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono">
                <span className="flex items-center gap-1.5 text-accent"><span className="w-2 h-2 rounded-full bg-accent" />Spend</span>
                <span className="flex items-center gap-1.5 text-success"><span className="w-2 h-2 rounded-full bg-success" />Conv.</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={TREND_DATA} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gSpend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FFD400" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#FFD400" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gConv" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22C55E" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#22C55E" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="day" stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} interval={5} />
                <YAxis stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="spend" stroke="#FFD400" strokeWidth={2} fill="url(#gSpend)" />
                <Area type="monotone" dataKey="conversions" stroke="#22C55E" strokeWidth={2} fill="url(#gConv)" />
              </AreaChart>
            </ResponsiveContainer>
          </Card3D>

          {/* Bar: channel performance */}
          <Card3D>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-display text-sm font-medium text-text">Channel Performance</div>
                <div className="text-[10px] text-text-muted font-mono">Spend (₹k) vs Conversions</div>
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono">
                <span className="flex items-center gap-1.5 text-info"><span className="w-2 h-2 rounded-full bg-info" />Spend</span>
                <span className="flex items-center gap-1.5 text-accent"><span className="w-2 h-2 rounded-full bg-accent" />Conv.</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={CHANNEL_PERF} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                <Bar dataKey="spend" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="conversions" fill="#FFD400" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card3D>

          {/* Line: visibility score */}
          <Card3D className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-display text-sm font-medium text-text">Visibility Score Trend</div>
                <div className="text-[10px] text-text-muted font-mono">AI citation + organic ranking composite</div>
              </div>
              <span className="badge badge-success">+18% MoM</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={VISIBILITY_TREND} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="day" stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} interval={5} />
                <YAxis stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} domain={[40, 90]} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="score" stroke="#FFD400" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: "#FFD400" }} />
              </LineChart>
            </ResponsiveContainer>
          </Card3D>
        </div>
      </div>

      {/* Heatmap */}
      <div className="mb-8">
        <SectionHeader
          title="Performance Heatmap"
          subtitle="Conversions by day of week × hour"
          icon={<Zap className="w-4 h-4" />}
        />
        <Card3D>
          <div className="overflow-x-auto scrollbar-none">
            <div className="min-w-[680px]">
              {/* Hour labels */}
              <div className="flex gap-1 mb-1.5 pl-12">
                {Array.from({ length: 24 }, (_, h) => (
                  <div key={h} className="flex-1 text-center font-mono text-[9px] text-text-muted">
                    {h % 3 === 0 ? `${h}h` : ""}
                  </div>
                ))}
              </div>
              {HEATMAP.map((row) => (
                <div key={row.day} className="flex items-center gap-1 mb-1">
                  <div className="w-10 font-mono text-[10px] text-text-secondary text-right pr-1">{row.day}</div>
                  <div className="flex gap-1 flex-1">
                    {row.hours.map((v, h) => (
                      <motion.div
                        key={h}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: h * 0.005 }}
                        whileHover={{ scale: 1.15, zIndex: 10 }}
                        className="flex-1 aspect-square rounded-[3px] transition-colors"
                        style={{ backgroundColor: heatColor(v) }}
                        title={`${row.day} ${h}:00 — ${(v * 100).toFixed(0)}%`}
                      />
                    ))}
                  </div>
                </div>
              ))}
              {/* Legend */}
              <div className="flex items-center justify-end gap-2 mt-3 pl-12">
                <span className="font-mono text-[9px] text-text-muted">Low</span>
                <div className="flex gap-0.5">
                  {[0.05, 0.25, 0.45, 0.65, 0.85].map((v) => (
                    <div key={v} className="w-4 h-3 rounded-[3px]" style={{ backgroundColor: heatColor(v) }} />
                  ))}
                </div>
                <span className="font-mono text-[9px] text-text-muted">High</span>
              </div>
            </div>
          </div>
        </Card3D>
      </div>

      {/* Channel breakdown */}
      <div className="mb-8">
        <SectionHeader
          title="Channel Breakdown"
          subtitle="Spend distribution across all channels"
          icon={<Globe className="w-4 h-4" />}
        />
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
          <Card3D>
            {/* Stacked bar */}
            <div className="flex h-10 w-full rounded-lg overflow-hidden mb-6">
              {CHANNEL_BREAKDOWN.map((c) => (
                <motion.div
                  key={c.name}
                  initial={{ width: 0 }}
                  animate={{ width: `${c.pct}%` }}
                  transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                  style={{ backgroundColor: c.color }}
                  className="h-full relative group"
                >
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="font-mono text-[10px] text-bg font-bold">{c.pct}%</span>
                  </div>
                </motion.div>
              ))}
            </div>
            {/* Legend list */}
            <div className="grid grid-cols-2 gap-3">
              {CHANNEL_BREAKDOWN.map((c) => (
                <div key={c.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                    <span className="text-xs text-text-secondary">{c.name}</span>
                  </div>
                  <span className="font-mono text-xs font-medium text-text">{c.pct}%</span>
                </div>
              ))}
            </div>
          </Card3D>

          <Card3D>
            <div className="font-display text-sm font-medium text-text mb-4">Top Performers</div>
            <div className="space-y-4">
              {CHANNEL_BREAKDOWN.slice(0, 5).map((c, i) => (
                <div key={c.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-text-muted w-4">{i + 1}</span>
                      <span className="text-xs text-text">{c.name}</span>
                    </div>
                    <span className="font-mono text-xs text-text-secondary">{c.pct}%</span>
                  </div>
                  <ProgressBar value={c.pct} max={40} accent={i === 0 ? "accent" : i === 1 ? "info" : "success"} />
                </div>
              ))}
            </div>
          </Card3D>
        </div>
      </div>

      {/* Footer mini metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="flex items-center gap-3">
          <Users className="w-5 h-5 text-info" />
          <MetricMini label="Unique Reach" value={4820000} format="compact" accent="info" />
        </Card>
        <Card className="flex items-center gap-3">
          <MousePointerClick className="w-5 h-5 text-accent" />
          <MetricMini label="Total Clicks" value={184200} format="compact" accent="accent" />
        </Card>
        <Card className="flex items-center gap-3">
          <Target className="w-5 h-5 text-success" />
          <MetricMini label="Conversions" value={14820} accent="success" />
        </Card>
        <Card className="flex items-center gap-3">
          <DollarSign className="w-5 h-5 text-text" />
          <MetricMini label="Total Spend" value={452000} format="currency" accent="default" />
        </Card>
      </div>
    </div>
  );
}
