"use client";

import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Check, Download, FileJson, Image as ImageIcon, Loader2, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";

// ─── Multi-Step Loading Animation ───────────────────────────────────────────

export function LoadingSteps({
  steps,
  currentStep,
  className,
}: {
  steps: string[];
  currentStep: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {steps.map((step, i) => {
        const isDone = i < currentStep;
        const isActive = i === currentStep;
        const isPending = i > currentStep;
        return (
          <motion.div
            key={step}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: isPending ? 0.4 : 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center gap-3"
          >
            <div
              className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all",
                isDone && "bg-green-500/20 text-green-400 border border-green-500/30",
                isActive && "bg-accent/20 text-accent border border-accent/30 glow-ring",
                isPending && "bg-white/[0.04] text-text-muted border border-white/[0.06]",
              )}
            >
              {isDone ? (
                <Check className="w-3.5 h-3.5" />
              ) : isActive ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                i + 1
              )}
            </div>
            <span
              className={cn(
                "text-sm transition-colors",
                isDone && "text-text-secondary line-through decoration-white/10",
                isActive && "text-text font-medium",
                isPending && "text-text-muted",
              )}
            >
              {step}
            </span>
            {isActive && (
              <motion.div
                className="flex-1 h-px bg-gradient-to-r from-accent/40 to-transparent"
                initial={{ scaleX: 0, originX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── Export Button ──────────────────────────────────────────────────────────

export function ExportButton({
  data,
  filename = "export",
  label = "Export",
  formats = ["json"],
  className,
}: {
  data: Record<string, any> | Record<string, any>[];
  filename?: string;
  label?: string;
  formats?: ("json" | "image" | "csv")[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  };

  const exportCSV = () => {
    const items = Array.isArray(data) ? data : [data];
    if (items.length === 0) return;
    const keys = Object.keys(items[0]);
    const csv = [
      keys.join(","),
      ...items.map((item) =>
        keys.map((k) => {
          const val = item[k];
          const str = typeof val === "object" ? JSON.stringify(val) : String(val ?? "");
          return `"${str.replace(/"/g, '""')}"`;
        }).join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  };

  const exportImage = () => {
    // Find the parent artefact card and use html2canvas-like approach
    // For now, export the data as a formatted JSON image placeholder
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 600;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#0a0a0a";
      ctx.fillRect(0, 0, 800, 600);
      ctx.fillStyle = "#ffffff";
      ctx.font = "14px monospace";
      const text = JSON.stringify(data, null, 2).slice(0, 2000);
      text.split("\n").forEach((line, i) => {
        ctx.fillText(line.slice(0, 80), 20, 30 + i * 18);
      });
    }
    canvas.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename}.png`;
      a.click();
      URL.revokeObjectURL(url);
    });
    setOpen(false);
  };

  return (
    <div className={cn("relative", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors px-2 py-1 rounded-lg hover:bg-white/[0.04]"
      >
        <Download className="w-3.5 h-3.5" />
        {label}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.95 }}
            className="absolute right-0 top-full mt-1 z-50 rounded-lg border border-white/[0.08] bg-zinc-900/95 backdrop-blur-xl shadow-xl py-1 min-w-[120px]"
          >
            {formats.includes("json") && (
              <button
                onClick={exportJSON}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-white/[0.04] transition-colors"
              >
                <FileJson className="w-3.5 h-3.5" />
                JSON
              </button>
            )}
            {formats.includes("csv") && (
              <button
                onClick={exportCSV}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-white/[0.04] transition-colors"
              >
                <FileJson className="w-3.5 h-3.5" />
                CSV
              </button>
            )}
            {formats.includes("image") && (
              <button
                onClick={exportImage}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-white/[0.04] transition-colors"
              >
                <ImageIcon className="w-3.5 h-3.5" />
                Image
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Onboarding Progress ────────────────────────────────────────────────────

export function OnboardingProgress({
  steps,
  currentStep,
  className,
}: {
  steps: { label: string; icon?: ReactNode }[];
  currentStep: number;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between", className)}>
      {steps.map((step, i) => {
        const isDone = i < currentStep;
        const isActive = i === currentStep;
        return (
          <div key={i} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <motion.div
                initial={false}
                animate={{
                  scale: isActive ? 1.1 : 1,
                  backgroundColor: isDone ? "rgba(34, 197, 94, 0.2)" : isActive ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.04)",
                }}
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center border transition-colors",
                  isDone && "border-green-500/30 text-green-400",
                  isActive && "border-accent/30 text-accent",
                  !isDone && !isActive && "border-white/[0.06] text-text-muted",
                )}
              >
                {isDone ? <Check className="w-4 h-4" /> : step.icon || i + 1}
              </motion.div>
              <span
                className={cn(
                  "text-[10px] font-medium transition-colors",
                  isDone && "text-green-400",
                  isActive && "text-accent",
                  !isDone && !isActive && "text-text-muted",
                )}
              >
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className="flex-1 h-px mx-2 bg-white/[0.06] relative overflow-hidden">
                <motion.div
                  initial={false}
                  animate={{ width: isDone ? "100%" : "0%" }}
                  transition={{ duration: 0.3 }}
                  className="absolute inset-0 bg-gradient-to-r from-accent/40 to-green-500/40"
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Mobile Responsive Wrapper ──────────────────────────────────────────────

export function ResponsiveGrid({
  children,
  className,
  cols = { mobile: 1, tablet: 2, desktop: 3 },
}: {
  children: ReactNode;
  className?: string;
  cols?: { mobile: number; tablet: number; desktop: number };
}) {
  return (
    <div
      className={cn(
        "grid gap-4",
        `grid-cols-${cols.mobile}`,
        `sm:grid-cols-${cols.tablet}`,
        `lg:grid-cols-${cols.desktop}`,
        className,
      )}
    >
      {children}
    </div>
  );
}

// ─── First-Time User Tooltip ────────────────────────────────────────────────

export function FirstTimeHint({
  show,
  title,
  description,
  onDismiss,
  className,
}: {
  show: boolean;
  title: string;
  description: string;
  onDismiss: () => void;
  className?: string;
}) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.95 }}
          className={cn(
            "absolute z-50 rounded-xl border border-accent/20 bg-zinc-900/95 backdrop-blur-xl shadow-xl p-3 max-w-xs",
            className,
          )}
        >
          <div className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-xs font-semibold text-text">{title}</div>
              <div className="text-[11px] text-text-secondary mt-0.5">{description}</div>
            </div>
          </div>
          <button
            onClick={onDismiss}
            className="mt-2 text-[10px] text-accent hover:text-accent/80 transition-colors"
          >
            Got it →
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── Approval Card ──────────────────────────────────────────────────────────

export function ApprovalCard({
  title,
  description,
  onApprove,
  onReject,
  onModify,
  loading,
  className,
}: {
  title: string;
  description: string;
  onApprove: () => void;
  onReject: () => void;
  onModify?: () => void;
  loading?: boolean;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-xl border border-white/[0.08] bg-gradient-to-br from-white/[0.04] to-transparent p-4",
        className,
      )}
    >
      <div className="flex items-start gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-accent" />
        </div>
        <div>
          <div className="text-sm font-semibold text-text">{title}</div>
          <div className="text-xs text-text-secondary mt-0.5">{description}</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onApprove}
          disabled={loading}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20 text-xs font-medium hover:bg-green-500/20 transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          Approve
        </button>
        {onModify && (
          <button
            onClick={onModify}
            disabled={loading}
            className="px-3 py-2 rounded-lg bg-white/[0.04] text-text-secondary border border-white/[0.06] text-xs font-medium hover:bg-white/[0.08] transition-colors disabled:opacity-50"
          >
            Modify
          </button>
        )}
        <button
          onClick={onReject}
          disabled={loading}
          className="px-3 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </motion.div>
  );
}

// ─── Undo Toast ─────────────────────────────────────────────────────────────

export function UndoToast({
  show,
  message,
  onUndo,
  onDismiss,
  className,
}: {
  show: boolean;
  message: string;
  onUndo: () => void;
  onDismiss: () => void;
  className?: string;
}) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className={cn(
            "fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl border border-white/[0.08] bg-zinc-900/95 backdrop-blur-xl shadow-2xl px-4 py-3 flex items-center gap-3",
            className,
          )}
        >
          <span className="text-sm text-text">{message}</span>
          <button
            onClick={onUndo}
            className="text-xs font-medium text-accent hover:text-accent/80 transition-colors"
          >
            Undo
          </button>
          <button
            onClick={onDismiss}
            className="text-text-muted hover:text-text transition-colors text-xs"
          >
            ✕
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
