"use client";

/**
 * MetricsChart — renders campaign performance data using Recharts.
 *
 * The `/performance/{id}` summary endpoint does not expose a full daily time
 * series; it exposes `notable_days` (days where a metric spiked/dropped >20%
 * vs the rolling average). We render those as a bar chart so the user gets a
 * visual sense of the notable events. When there is no data we show an empty
 * state rather than a blank chart.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import { TrendingUp } from "lucide-react";
import type { NotableDay } from "@/lib/performance";

interface MetricsChartProps {
  /** Notable-day entries from the performance summary. */
  data: NotableDay[];
  /** Optional height in px (default 280). */
  height?: number;
}

/** Colour per metric so bars are distinguishable. */
const METRIC_COLORS: Record<string, string> = {
  impressions: "#60a5fa",
  clicks: "#a78bfa",
  conversions: "#8B5CF6",
  spend: "#f472b6",
  revenue: "#34d399",
};

const NOTE_COLOR: Record<string, string> = {
  spike: "#34d399",
  drop: "#f87171",
};

function barColor(entry: { metric?: string; note?: string }): string {
  if (entry.note && entry.note.startsWith("drop")) {
    return NOTE_COLOR.drop!;
  }
  if (entry.note && entry.note.startsWith("spike")) {
    return NOTE_COLOR.spike!;
  }
  return METRIC_COLORS[entry.metric ?? ""] ?? "#8B5CF6";
}

interface ChartPoint {
  date: string;
  shortDate: string;
  metric: string;
  value: number;
  note: string;
  label: string;
}

function toChartPoints(data: NotableDay[]): ChartPoint[] {
  return data
    .map((d) => ({
      date: d.date,
      shortDate: d.date.slice(5), // MM-DD
      metric: d.metric,
      value: d.value,
      note: d.note,
      label: `${d.metric} · ${d.note}`,
    }))
    .sort((a, b) => (a.date < b.date ? -1 : 1));
}

function ChartTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]!.payload;
  return (
    <div className="glass-strong rounded-lg px-3 py-2 text-xs space-y-0.5">
      <div className="font-mono text-text-muted">{point.date}</div>
      <div className="font-medium text-text capitalize">{point.metric}</div>
      <div className="font-mono text-text-secondary">
        Value: {point.value.toLocaleString()}
      </div>
      <div className="text-text-muted capitalize">{point.note}</div>
    </div>
  );
}

export function MetricsChart({ data, height = 280 }: MetricsChartProps) {
  const points = toChartPoints(data);

  if (points.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center text-center rounded-xl border border-white/[0.04] bg-white/[0.02]"
        style={{ height }}
      >
        <TrendingUp className="w-8 h-8 text-text-muted mb-2" />
        <p className="text-sm text-text-secondary">
          No notable day spikes detected
        </p>
        <p className="text-xs text-text-muted mt-1">
          Performance was steady across the analysis window.
        </p>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          margin={{ top: 10, right: 12, left: -10, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.05)"
            vertical={false}
          />
          <XAxis
            dataKey="shortDate"
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
          />
          <YAxis
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {points.map((p, i) => (
              <Cell key={`bar-${i}`} fill={barColor(p)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default MetricsChart;
