"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Performance ring — circular progress with animated stroke.
 * Used for visibility scores, health indicators, campaign performance.
 */
export function PerformanceRing({
  value,
  max = 100,
  size = 120,
  strokeWidth = 8,
  label,
  sublabel,
  accent = "#FFD400",
  className,
}: {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
  accent?: string;
  className?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min(value / max, 1);
  const offset = circumference * (1 - percentage);

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={accent}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          style={{ filter: `drop-shadow(0 0 6px ${accent}40)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-2xl font-semibold text-text">
          {label || value.toFixed(0)}
        </span>
        {sublabel && (
          <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-0.5">
            {sublabel}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Mini sparkline — inline trend indicator.
 */
export function Sparkline({
  data,
  width = 80,
  height = 24,
  color = "#FFD400",
  className,
}: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}) {
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className={className}>
      <motion.polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
    </svg>
  );
}

/**
 * Progress bar — animated horizontal bar.
 */
export function ProgressBar({
  value,
  max = 100,
  accent = "accent",
  className,
  showLabel = false,
}: {
  value: number;
  max?: number;
  accent?: "accent" | "success" | "danger" | "info" | "warning";
  className?: string;
  showLabel?: boolean;
}) {
  const percentage = Math.min((value / max) * 100, 100);
  const colors = {
    accent: "bg-accent",
    success: "bg-success",
    danger: "bg-danger",
    info: "bg-info",
    warning: "bg-warning",
  };

  return (
    <div className={cn("w-full", className)}>
      <div className="h-1.5 w-full bg-white/[0.06] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className={cn("h-full rounded-full", colors[accent])}
        />
      </div>
      {showLabel && (
        <div className="flex justify-between mt-1">
          <span className="font-mono text-[10px] text-text-muted">{percentage.toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
}
