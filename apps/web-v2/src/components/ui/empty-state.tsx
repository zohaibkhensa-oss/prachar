"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { Sparkles, ArrowRight } from "lucide-react";

/**
 * Empty state — never show "No Data". Instead educate, recommend, guide.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  actionLabel,
  demo,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: () => void;
  actionLabel?: string;
  demo?: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "card-3d rounded-xl p-8 flex flex-col items-center text-center max-w-md mx-auto",
        className,
      )}
    >
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4 glow-ring"
      >
        {icon || <Sparkles className="w-6 h-6 text-accent" />}
      </motion.div>
      <h3 className="font-display text-lg font-medium text-text mb-2">{title}</h3>
      <p className="text-sm text-text-secondary leading-relaxed mb-4">{description}</p>
      {demo && <div className="w-full mb-4">{demo}</div>}
      {action && actionLabel && (
        <button onClick={action} className="btn-primary group">
          {actionLabel}
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      )}
    </motion.div>
  );
}

/**
 * Skeleton loader — shimmer placeholder.
 */
export function Skeleton({ className, lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded-lg shimmer"
          style={{ width: `${100 - i * 15}%` }}
        />
      ))}
    </div>
  );
}

/**
 * Section header — consistent header for all sections.
 */
export function SectionHeader({
  title,
  subtitle,
  action,
  icon,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        {icon && (
          <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary">
            {icon}
          </div>
        )}
        <div>
          <h2 className="font-display text-xl font-semibold text-text">{title}</h2>
          {subtitle && (
            <p className="text-xs text-text-secondary mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}
