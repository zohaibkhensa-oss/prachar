"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { Sparkles, Clock } from "lucide-react";

/**
 * ComingSoon — a beautiful, on-brand empty state for Tier 3 "Labs" pages.
 *
 * Shows an honest "Coming in an upcoming update" message with:
 * - A large animated icon with glowing gradient ring
 * - A pulsing "Coming in an upcoming update" badge
 * - A clear title and description
 * - Feature pills showing what's planned
 * - Decorative gradient blobs and grid pattern background
 * - Glass morphism + subtle floating animation
 */
export function ComingSoon({
  icon,
  title,
  description,
  features,
  className,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  features?: string[];
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className={cn("relative overflow-hidden", className)}
    >
      {/* Decorative gradient blobs */}
      <div className="absolute -top-24 -left-24 w-72 h-72 rounded-full bg-accent/[0.06] blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -right-24 w-72 h-72 rounded-full bg-info/[0.04] blur-3xl pointer-events-none" />

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 grid-pattern opacity-40 pointer-events-none" />

      <div className="relative glass-strong rounded-2xl p-10 md:p-16 flex flex-col items-center text-center max-w-2xl mx-auto">
        {/* Icon with glowing gradient ring */}
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          className="relative mb-6"
        >
          {/* Outer glow ring */}
          <div className="absolute inset-0 rounded-3xl bg-accent/20 blur-xl scale-150" />
          {/* Icon container */}
          <div className="relative w-20 h-20 rounded-3xl bg-gradient-to-br from-accent/20 to-accent/5 border border-accent/20 flex items-center justify-center glow-ring">
            <div className="text-accent">{icon}</div>
          </div>
          {/* Orbiting sparkle */}
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            className="absolute inset-0"
          >
            <Sparkles className="w-3.5 h-3.5 text-accent/60 absolute -top-1 left-1/2 -translate-x-1/2" />
          </motion.div>
        </motion.div>

        {/* Coming soon badge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 mb-5"
        >
          <span className="relative flex w-2 h-2">
            <span className="absolute inline-flex w-full h-full rounded-full bg-accent opacity-60 animate-ping" />
            <span className="relative inline-flex w-2 h-2 rounded-full bg-accent" />
          </span>
          <span className="font-mono text-[10px] uppercase tracking-wider text-accent font-semibold">
            Coming in an upcoming update
          </span>
        </motion.div>

        {/* Title */}
        <h2 className="font-display text-2xl md:text-3xl font-semibold text-text mb-3 text-balance">
          {title}
        </h2>

        {/* Description */}
        <p className="text-sm md:text-base text-text-secondary leading-relaxed max-w-lg text-balance mb-6">
          {description}
        </p>

        {/* Feature pills */}
        {features && features.length > 0 && (
          <div className="flex flex-wrap gap-2 justify-center max-w-md">
            {features.map((f, i) => (
              <motion.span
                key={f}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + i * 0.06 }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-text-secondary"
              >
                <Sparkles className="w-3 h-3 text-accent/50" />
                {f}
              </motion.span>
            ))}
          </div>
        )}

        {/* Footer hint */}
        <div className="mt-8 flex items-center gap-1.5 text-[11px] text-text-muted">
          <Clock className="w-3 h-3" />
          <span>We&apos;re building this with care — it&apos;ll be worth the wait.</span>
        </div>
      </div>
    </motion.div>
  );
}
