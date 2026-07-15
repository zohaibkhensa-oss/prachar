"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";
import {
  Download,
  ChevronDown,
  TrendingUp,
  DollarSign,
  Target,
  MousePointerClick,
  Sparkles,
  FileText,
  MapPin,
  Filter,
} from "lucide-react";
import { Metric } from "@/components/ui/metric";
import { Card, Card3D } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { cn } from "@/lib/utils";

const BRANDS = [
  { id: "brewcraft", name: "BrewCraft Coffee" },
  { id: "lumina", name: "Lumina Skincare" },
  { id: "voltedge", name: "VoltEdge Electronics" },
];

const TIME_RANGES = ["7D", "30D", "90D", "12W", "1Y"];

const CHANNEL_ROAS = [
  { name: "Google", roas: 4.8 },
  { name: "Meta", roas: 3.9 },
  { name: "YouTube", roas: 5.2 },
  { name: "TikTok", roas: 3.1 },
  { name: "Amazon", roas: 6.4 },
  { name: "LinkedIn", roas: 2.7 },
];

const GROWTH_DATA = Array.from({ length: 12 }, (_, i) => ({
  week: `W${i + 1}`,
  revenue: 120000 + i * 18000 + Math.sin(i) * 12000,
  spend: 80000 + i * 9000,
}));

const FUNNEL = [
  { label: "Impressions", value: 2840000, color: "from-info/80 to-info/40" },
  { label: "Clicks", value: 142000, color: "from-accent/80 to-accent/40" },
  { label: "Conversions", value: 18600, color: "from-success/80 to-success/40" },
  { label: "Revenue", value: 4200000, color: "from-danger/80 to-danger/40" },
];

const REGIONS = [
  { name: "Mumbai", roas: 5.4, spend: 480000, trend: "up" },
  { name: "Delhi NCR", roas: 4.2, spend: 390000, trend: "up" },
  { name: "Bengaluru", roas: 6.1, spend: 520000, trend: "up" },
  { name: "Chennai", roas: 3.4, spend: 210000, trend: "down" },
  { name: "Hyderabad", roas: 4.8, spend: 280000, trend: "up" },
  { name: "Pune", roas: 3.9, spend: 190000, trend: "flat" },
];

const REPORT_HISTORY = [
  { id: "r1", title: "Weekly Report — W12", date: "Mar 24, 2025", size: "2.4 MB" },
  { id: "r2", title: "Weekly Report — W11", date: "Mar 17, 2025", size: "2.1 MB" },
  { id: "r3", title: "Monthly Report — Feb", date: "Mar 01, 2025", size: "5.8 MB" },
  { id: "r4", title: "Weekly Report — W10", date: "Mar 10, 2025", size: "2.0 MB" },
];

const CHARTTextStyle = { fill: "#94A3B8", fontSize: 11, fontFamily: "monospace" };

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-strong rounded-lg px-3 py-2 border border-white/10">
      <p className="font-mono text-[10px] text-text-muted uppercase tracking-wider mb-1">
        {label}
      </p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="font-mono text-xs text-text">
          <span className="text-accent">{p.name}:</span>{" "}
          {typeof p.value === "number"
            ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(p.value)
            : p.value}
        </p>
      ))}
    </div>
  );
}

export default function ReportsPage() {
  const [brand, setBrand] = useState(BRANDS[0]!);
  const [range, setRange] = useState("12W");
  const [brandOpen, setBrandOpen] = useState(false);

  const maxFunnel = FUNNEL[0]!.value;

  return (
    <div className="p-8 max-w-[1600px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-4xl tracking-wide text-text mb-1">
            Reports
          </h1>
          <p className="text-sm text-text-secondary">
            Performance intelligence across all channels and regions.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Brand selector */}
          <div className="relative">
            <button
              onClick={() => setBrandOpen((v) => !v)}
              className="btn-secondary flex items-center gap-2"
            >
              <span className="text-text">{brand.name}</span>
              <ChevronDown className="w-4 h-4 text-text-secondary" />
            </button>
            {brandOpen && (
              <div className="absolute top-full mt-2 right-0 z-30 glass-strong rounded-lg p-1 min-w-[200px] border border-white/10">
                {BRANDS.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => {
                      setBrand(b);
                      setBrandOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 rounded-md text-sm transition-colors hover:bg-white/5",
                      b.id === brand.id ? "text-accent" : "text-text-secondary",
                    )}
                  >
                    {b.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* Time range */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.04]">
            {TIME_RANGES.map((t) => (
              <button
                key={t}
                onClick={() => setRange(t)}
                className={cn(
                  "px-3 py-1.5 rounded-md font-mono text-xs transition-all",
                  t === range
                    ? "bg-accent text-bg font-medium"
                    : "text-text-secondary hover:text-text",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          {/* Export */}
          <button className="btn-primary flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export PDF
          </button>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Metric
          label="Revenue"
          value={4200000}
          format="currency"
          delta={18.4}
          deltaLabel="vs last period"
          icon={<DollarSign className="w-4 h-4" />}
          accent="accent"
        />
        <Metric
          label="ROAS"
          value={4.6}
          format="number"
          suffix="x"
          delta={6.2}
          deltaLabel="vs last period"
          icon={<TrendingUp className="w-4 h-4" />}
          accent="success"
        />
        <Metric
          label="CPA"
          value={226}
          format="currency"
          delta={-9.1}
          deltaLabel="vs last period"
          icon={<Target className="w-4 h-4" />}
          accent="info"
        />
        <Metric
          label="CTR"
          value={5.0}
          format="percent"
          delta={12.7}
          deltaLabel="vs last period"
          icon={<MousePointerClick className="w-4 h-4" />}
          accent="accent"
        />
      </div>

      {/* Performance Funnel */}
      <Card className="mb-8">
        <SectionHeader
          title="Performance Funnel"
          subtitle="Impressions → Clicks → Conversions → Revenue"
          icon={<Filter className="w-4 h-4" />}
        />
        <div className="space-y-4">
          {FUNNEL.map((stage, i) => {
            const width = (stage.value / maxFunnel) * 100;
            const prev = i > 0 ? FUNNEL[i - 1]!.value : stage.value;
            const conv = i > 0 ? ((stage.value / prev) * 100).toFixed(1) : "100";
            return (
              <div key={stage.label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-display text-sm text-text">{stage.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-text">
                      {stage.label === "Revenue"
                        ? new Intl.NumberFormat("en-IN", {
                            style: "currency",
                            currency: "INR",
                            maximumFractionDigits: 0,
                          }).format(stage.value)
                        : new Intl.NumberFormat("en").format(stage.value)}
                    </span>
                    <span className="badge badge-accent">{conv}%</span>
                  </div>
                </div>
                <div className="h-9 w-full bg-white/[0.03] rounded-lg overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${width}%` }}
                    transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: i * 0.1 }}
                    className={cn("h-full rounded-lg bg-gradient-to-r", stage.color)}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* ROAS by Channel */}
        <Card>
          <SectionHeader title="ROAS by Channel" subtitle="Return on ad spend per channel" />
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={CHANNEL_ROAS}
              layout="vertical"
              margin={{ left: 10, right: 20, top: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
              <XAxis type="number" tick={CHARTTextStyle} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="name"
                tick={CHARTTextStyle}
                axisLine={false}
                tickLine={false}
                width={70}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="roas" radius={[0, 6, 6, 0]} barSize={22}>
                {CHANNEL_ROAS.map((entry, idx) => (
                  <Cell
                    key={idx}
                    fill={entry.roas >= 5 ? "#22C55E" : entry.roas >= 4 ? "#FFD400" : "#3B82F6"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Growth Chart */}
        <Card>
          <SectionHeader title="Growth Chart" subtitle="Revenue & spend over 12 weeks" />
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={GROWTH_DATA} margin={{ left: 0, right: 10, top: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FFD400" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#FFD400" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="week" tick={CHARTTextStyle} axisLine={false} tickLine={false} />
              <YAxis
                tick={CHARTTextStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: "rgba(255,255,255,0.1)" }} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="#FFD400"
                strokeWidth={2}
                fill="url(#revGrad)"
              />
              <Area
                type="monotone"
                dataKey="spend"
                stroke="#3B82F6"
                strokeWidth={2}
                fill="url(#spendGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Geographic + Weekly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Card className="lg:col-span-2">
          <SectionHeader
            title="Geographic Performance"
            subtitle="ROAS by region"
            icon={<MapPin className="w-4 h-4" />}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {REGIONS.map((r) => (
              <div
                key={r.name}
                className="rounded-lg p-4 bg-white/[0.03] border border-white/[0.04] hover:border-accent/30 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-display text-sm text-text">{r.name}</span>
                  <span
                    className={cn(
                      "font-mono text-xs",
                      r.trend === "up"
                        ? "text-success"
                        : r.trend === "down"
                          ? "text-danger"
                          : "text-text-muted",
                    )}
                  >
                    {r.trend === "up" ? "▲" : r.trend === "down" ? "▼" : "—"}
                  </span>
                </div>
                <div className="flex items-end justify-between">
                  <div>
                    <p className="font-mono text-2xl font-semibold text-text">
                      {r.roas.toFixed(1)}x
                    </p>
                    <p className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">
                      ROAS
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-xs text-text-secondary">
                      ₹{(r.spend / 1000).toFixed(0)}k
                    </p>
                    <p className="text-[10px] text-text-muted">spend</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Weekly Summary */}
        <Card3D glow className="border-l-2 border-l-accent/40">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <span className="font-display text-sm font-medium text-text">
              AI Weekly Summary
            </span>
          </div>
          <p className="text-sm text-text-secondary leading-relaxed">
            This week delivered <span className="text-accent font-medium">₹42L revenue</span> at a{" "}
            <span className="text-success font-medium">4.6x ROAS</span>, up 18% week-over-week.
            Amazon and YouTube were the standout channels. CTR improved 12.7% after creative
            refresh on BrewCraft core SKUs. Chennai underperformed at 3.4x — consider pausing
            low-intent keyword clusters there.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <span className="badge badge-success">+18% Revenue</span>
            <span className="badge badge-accent">4.6x ROAS</span>
          </div>
        </Card3D>
      </div>

      {/* Report History */}
      <Card>
        <SectionHeader
          title="Report History"
          subtitle="Download past reports"
          icon={<FileText className="w-4 h-4" />}
        />
        <div className="space-y-2">
          {REPORT_HISTORY.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-white/[0.03] transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary group-hover:text-accent transition-colors">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <p className="font-display text-sm text-text">{r.title}</p>
                  <p className="text-xs text-text-muted font-mono">
                    {r.date} · {r.size}
                  </p>
                </div>
              </div>
              <button className="btn-ghost text-xs flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5" />
                Download
              </button>
            </div>
          ))}
        </div>
      </Card>

      {/* AI recommendation */}
      <div className="mt-8">
        <AIRecommendation
          title="Reallocate 15% budget from Chennai to Bengaluru"
          reasoning="Bengaluru is delivering 6.1x ROAS vs Chennai's 3.4x. Shifting budget could add an estimated ₹3.2L incremental revenue next week."
          action="Apply budget reallocation"
          confidence={87}
          onAccept={() => {}}
          onDismiss={() => {}}
        />
      </div>
    </div>
  );
}
