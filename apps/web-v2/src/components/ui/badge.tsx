import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "yellow" | "ink" | "paper" | "blue" | "grey" | "accent" | "success" | "danger" | "warning" | "info" | "neutral";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const variants: Record<Variant, string> = {
  // New neon-black variants
  accent: "bg-accent/10 text-accent border border-accent/20",
  success: "bg-success/10 text-success border border-success/20",
  danger: "bg-danger/10 text-danger border border-danger/20",
  warning: "bg-warning/10 text-warning border border-warning/20",
  info: "bg-info/10 text-info border border-info/20",
  neutral: "bg-white/[0.04] text-text-secondary border border-white/[0.06]",
  // Legacy aliases
  yellow: "bg-accent/10 text-accent border border-accent/20",
  ink: "bg-white/[0.04] text-text-secondary border border-white/[0.06]",
  paper: "bg-white/[0.04] text-text-secondary border border-white/[0.06]",
  blue: "bg-info/10 text-info border border-info/20",
  grey: "bg-white/[0.04] text-text-secondary border border-white/[0.06]",
};

export function Badge({ className, variant = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider font-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
