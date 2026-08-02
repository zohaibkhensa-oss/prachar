"use client";

import { motion, useMotionValue, useSpring, useTransform, animate } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

interface MetricProps {
  label: string;
  value: number;
  format?: "number" | "currency" | "percent" | "compact";
  prefix?: string;
  suffix?: string;
  delta?: number;
  deltaLabel?: string;
  icon?: ReactNode;
  accent?: "default" | "accent" | "success" | "danger" | "info";
  className?: string;
}

const ACCENT_COLORS = {
  default: "text-text",
  accent: "text-accent",
  success: "text-success",
  danger: "text-danger",
  info: "text-info",
};

const ACCENT_GLOW = {
  default: "",
  accent: "shadow-glow",
  success: "shadow-glow-green",
  danger: "shadow-glow-red",
  info: "shadow-glow-blue",
};

function formatValue(val: number, format: MetricProps["format"], prefix?: string, suffix?: string) {
  let str: string;
  switch (format) {
    case "currency":
      str = new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(val);
      break;
    case "percent":
      str = `${val.toFixed(1)}%`;
      break;
    case "compact":
      str = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(val);
      break;
    default:
      str = new Intl.NumberFormat("en").format(val);
  }
  return `${prefix || ""}${str}${suffix || ""}`;
}

/**
 * Animated metric — counts up from 0 to value on mount.
 * 3D tilt effect + glow based on accent color.
 */
export function Metric({
  label,
  value,
  format = "number",
  prefix,
  suffix,
  delta,
  deltaLabel,
  icon,
  accent = "default",
  className,
}: MetricProps) {
  const count = useMotionValue(0);
  const rounded = useSpring(count, { stiffness: 60, damping: 20 });
  const displayRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const controls = animate(count, value, {
      duration: 1.2,
      ease: [0.16, 1, 0.3, 1],
    });
    const unsub = rounded.on("change", (v) => {
      if (displayRef.current) {
        displayRef.current.textContent = formatValue(v, format, prefix, suffix);
      }
    });
    return () => {
      controls.stop();
      unsub();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const isPositive = (delta ?? 0) >= 0;

  return (
    <div
      className={cn(
        "card-3d rounded-xl p-5 transition-all duration-300",
        ACCENT_GLOW[accent],
        className,
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <span className="label-field">{label}</span>
        {icon && (
          <div className={cn("opacity-60", ACCENT_COLORS[accent])}>{icon}</div>
        )}
      </div>
      <div className="flex items-end justify-between">
        <span
          ref={displayRef}
          className={cn(
            "font-display text-3xl font-semibold tracking-tight",
            ACCENT_COLORS[accent],
          )}
        >
          0
        </span>
        {delta !== undefined && (
          <div
            className={cn(
              "flex items-center gap-1 text-xs font-mono",
              isPositive ? "text-success" : "text-danger",
            )}
          >
            {isPositive ? (
              <ArrowUpRight className="w-3.5 h-3.5" />
            ) : (
              <ArrowDownRight className="w-3.5 h-3.5" />
            )}
            {Math.abs(delta).toFixed(1)}%
            {deltaLabel && (
              <span className="text-text-muted ml-1">{deltaLabel}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Compact metric for inline use in sidebars and small spaces.
 */
export function MetricMini({
  label,
  value,
  format = "number",
  accent = "default",
}: Pick<MetricProps, "label" | "value" | "format" | "accent">) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="label-field text-[10px]">{label}</span>
      <span className={cn("font-mono text-sm font-medium", ACCENT_COLORS[accent])}>
        {formatValue(value, format)}
      </span>
    </div>
  );
}
