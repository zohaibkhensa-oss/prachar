"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ThinkingBubbleProps {
  label?: string;
  steps?: { label: string; status: "pending" | "running" | "done" | "error" }[];
}

/**
 * ThinkingBubble — animated indicator shown while CURV AI is working.
 * ChatGPT/Gemini-style: minimal, no card border, just dots + label.
 */
export function ThinkingBubble({ label = "Thinking", steps }: ThinkingBubbleProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="flex flex-col gap-2"
    >
      {/* Pulsing dots + label */}
      <div className="flex items-center gap-1.5 py-1">
        <motion.div
          className="w-1.5 h-1.5 rounded-full bg-text-muted"
          animate={{ scale: [0.8, 1.3, 0.8], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut", delay: 0 }}
        />
        <motion.div
          className="w-1.5 h-1.5 rounded-full bg-text-muted"
          animate={{ scale: [0.8, 1.3, 0.8], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut", delay: 0.15 }}
        />
        <motion.div
          className="w-1.5 h-1.5 rounded-full bg-text-muted"
          animate={{ scale: [0.8, 1.3, 0.8], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
        />
        <span className="text-sm text-text-secondary ml-2">{label}</span>
      </div>

      {/* Progress steps (friendly labels) */}
      {steps && steps.length > 0 && (
        <div className="space-y-1.5">
          {steps.map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="flex items-center gap-2 text-xs"
            >
              <div
                className={cn(
                  "w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] flex-shrink-0",
                  step.status === "done" && "bg-green-500/15 text-green-400",
                  step.status === "running" && "bg-accent/15 text-accent",
                  step.status === "error" && "bg-red-500/15 text-red-400",
                  step.status === "pending" && "bg-white/[0.04] text-text-muted",
                )}
              >
                {step.status === "done"
                  ? "✓"
                  : step.status === "error"
                    ? "⚠"
                    : step.status === "running"
                      ? "●"
                      : "○"}
              </div>
              <span
                className={cn(
                  "text-text-secondary",
                  step.status === "running" && "text-text",
                  step.status === "done" && "text-text-muted",
                )}
              >
                {step.label}
              </span>
              {step.status === "running" && (
                <motion.span
                  className="text-text-muted"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  ...
                </motion.span>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
