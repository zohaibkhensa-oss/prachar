"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Animated timeline — vertical line with animated dots and entries.
 * Used for live activity feeds, audit progress, loop status.
 */
interface TimelineEntry {
  id: string;
  title: string;
  description?: string;
  timestamp?: string;
  status?: "active" | "done" | "pending" | "error";
  icon?: ReactNode;
}

const STATUS_STYLES = {
  active: { dot: "bg-accent shadow-glow", line: "bg-accent/30" },
  done: { dot: "bg-success", line: "bg-success/20" },
  pending: { dot: "bg-text-muted", line: "bg-white/[0.06]" },
  error: { dot: "bg-danger", line: "bg-danger/20" },
};

export function Timeline({ entries, className }: { entries: TimelineEntry[]; className?: string }) {
  return (
    <div className={cn("relative", className)}>
      {entries.map((entry, i) => {
        const style = STATUS_STYLES[entry.status || "pending"];
        const isLast = i === entries.length - 1;
        return (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="relative flex gap-4 pb-6 last:pb-0"
          >
            {/* Line */}
            {!isLast && (
              <div className={cn("absolute left-[11px] top-6 bottom-0 w-px", style.line)} />
            )}
            {/* Dot */}
            <div className="relative shrink-0">
              <div className={cn("w-6 h-6 rounded-full flex items-center justify-center", style.dot)}>
                {entry.icon || (
                  <div className="w-2 h-2 rounded-full bg-bg" />
                )}
              </div>
              {entry.status === "active" && (
                <motion.div
                  className="absolute inset-0 rounded-full border-2 border-accent"
                  animate={{ scale: [1, 1.4], opacity: [0.6, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                />
              )}
            </div>
            {/* Content */}
            <div className="flex-1 min-w-0 pt-0.5">
              <div className="flex items-center justify-between gap-2">
                <span className="font-display text-sm font-medium text-text">{entry.title}</span>
                {entry.timestamp && (
                  <span className="font-mono text-[10px] text-text-muted shrink-0">
                    {entry.timestamp}
                  </span>
                )}
              </div>
              {entry.description && (
                <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                  {entry.description}
                </p>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/**
 * Activity feed — horizontal scrolling cards for "Today's Wins" etc.
 */
export function ActivityFeed({
  items,
  className,
}: {
  items: { id: string; icon?: ReactNode; title: string; meta?: string; value?: string }[];
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      {items.map((item, i) => (
        <motion.div
          key={item.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05 }}
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-white/[0.03] transition-colors"
        >
          {item.icon && <div className="shrink-0 text-text-secondary">{item.icon}</div>}
          <div className="flex-1 min-w-0">
            <span className="text-sm text-text truncate block">{item.title}</span>
            {item.meta && (
              <span className="text-xs text-text-muted">{item.meta}</span>
            )}
          </div>
          {item.value && (
            <span className="font-mono text-xs font-medium text-accent shrink-0">
              {item.value}
            </span>
          )}
        </motion.div>
      ))}
    </div>
  );
}
