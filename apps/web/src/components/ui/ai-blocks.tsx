"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Brain, Sparkles, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type AIStatus = "thinking" | "generating" | "analyzing" | "done" | "idle" | "error";

const STATUS_CONFIG: Record<AIStatus, { icon: ReactNode; label: string; color: string; pulse: boolean }> = {
  thinking: { icon: <Brain className="w-4 h-4" />, label: "AI Thinking", color: "text-accent", pulse: true },
  generating: { icon: <Sparkles className="w-4 h-4" />, label: "Generating", color: "text-info", pulse: true },
  analyzing: { icon: <Loader2 className="w-4 h-4 animate-spin" />, label: "Analyzing", color: "text-info", pulse: true },
  done: { icon: <CheckCircle2 className="w-4 h-4" />, label: "Complete", color: "text-success", pulse: false },
  idle: { icon: <Brain className="w-4 h-4" />, label: "Idle", color: "text-text-muted", pulse: false },
  error: { icon: <AlertCircle className="w-4 h-4" />, label: "Error", color: "text-danger", pulse: false },
};

/**
 * AI Status block — shows what the AI is currently doing.
 * Animated pulse + thinking dots.
 */
export function AIStatusBlock({
  status,
  label,
  detail,
  confidence,
  className,
}: {
  status: AIStatus;
  label?: string;
  detail?: string;
  confidence?: number;
  className?: string;
}) {
  const config = STATUS_CONFIG[status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "glass rounded-lg p-4 flex items-center gap-3",
        config.pulse && "glow-ring",
        className,
      )}
    >
      <div className={cn("shrink-0", config.color)}>
        {config.pulse ? (
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          >
            {config.icon}
          </motion.div>
        ) : (
          config.icon
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("font-mono text-xs font-medium", config.color)}>
            {label || config.label}
          </span>
          {config.pulse && (
            <span className="ai-dots">
              <span /> <span /> <span />
            </span>
          )}
        </div>
        {detail && (
          <p className="text-xs text-text-secondary mt-0.5 truncate">{detail}</p>
        )}
      </div>
      {confidence !== undefined && (
        <div className="shrink-0">
          <div className="flex items-center gap-1.5">
            <span className="label-field text-[9px]">Confidence</span>
            <span className="font-mono text-xs font-medium text-text">
              {confidence}%
            </span>
          </div>
          <div className="w-16 h-1 bg-white/[0.06] rounded-full mt-1 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidence}%` }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className={cn("h-full rounded-full", config.color.replace("text-", "bg-"))}
            />
          </div>
        </div>
      )}
    </motion.div>
  );
}

/**
 * AI Recommendation card — shows AI-suggested actions with reasoning.
 */
export function AIRecommendation({
  title,
  reasoning,
  action,
  confidence,
  onAccept,
  onDismiss,
}: {
  title: string;
  reasoning: string;
  action?: string;
  confidence?: number;
  onAccept?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="card-3d rounded-xl p-4 border-l-2 border-l-accent/40"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-display text-sm font-medium text-text">{title}</span>
            {confidence !== undefined && (
              <span className="badge badge-accent">{confidence}% confidence</span>
            )}
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">{reasoning}</p>
          {action && (
            <p className="text-xs text-accent mt-2 font-mono">→ {action}</p>
          )}
          {(onAccept || onDismiss) && (
            <div className="flex gap-2 mt-3">
              {onAccept && (
                <button onClick={onAccept} className="btn-primary text-xs px-3 py-1.5">
                  Accept
                </button>
              )}
              {onDismiss && (
                <button onClick={onDismiss} className="btn-ghost text-xs px-3 py-1.5">
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/**
 * AI Thinking overlay — full-screen or section-level loading state.
 */
export function AIThinkingOverlay({ message = "AI is processing..." }: { message?: string }) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 glass-strong rounded-xl flex items-center justify-center z-50"
      >
        <div className="flex flex-col items-center gap-4">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="w-12 h-12 rounded-full border-2 border-accent/20 border-t-accent"
          />
          <div className="flex items-center gap-2">
            <span className="ai-dots">
              <span /> <span /> <span />
            </span>
            <span className="font-mono text-xs text-text-secondary">{message}</span>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
