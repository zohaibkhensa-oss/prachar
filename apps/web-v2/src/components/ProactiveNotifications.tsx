"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  X,
  Check,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Minus,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getPracharMessages, launchRecommendation, type PracharMessage } from "@/lib/proactive";
import { useActiveBrand } from "@/lib/hooks";

interface ProactiveNotificationsProps {
  open: boolean;
  onClose: () => void;
}

export function ProactiveNotifications({ open, onClose }: ProactiveNotificationsProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { brand } = useActiveBrand();
  const [launching, setLaunching] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["prachar-messages"],
    queryFn: getPracharMessages,
    enabled: open,
    staleTime: 30 * 1000,
  });

  const messages = data?.messages ?? [];

  async function handleAccept(msg: PracharMessage) {
    if (!brand) return;
    setLaunching(true);
    try {
      const result = await launchRecommendation(msg.id);
      // Navigate to campaign creation with pre-fill data via query params.
      const params = new URLSearchParams({
        recommendation_id: result.recommendation_id,
        goal: result.goal,
        budget: result.budget,
        prachar_message: result.prachar_message,
      });
      if (result.creative_directions.length > 0) {
        params.set("directions", result.creative_directions.join("|"));
      }
      onClose();
      router.push(`/app/brands/${brand.id}/campaigns/new?${params.toString()}`);
    } catch {
      // Silently fail — the user can retry.
    } finally {
      setLaunching(false);
    }
  }

  function handleDismiss(msg: PracharMessage) {
    // Optimistically remove from the list by invalidating the query.
    queryClient.setQueryData<{ messages: PracharMessage[]; count: number }>(
      ["prachar-messages"],
      (old) => {
        if (!old) return old;
        const filtered = old.messages.filter((m) => m.id !== msg.id);
        return { messages: filtered, count: filtered.length };
      },
    );
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="fixed right-0 top-0 z-50 h-screen w-full max-w-md bg-bg-surface border-l border-white/[0.06] flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-accent" />
                <h2 className="font-display text-base font-semibold text-text">
                  Notifications
                </h2>
                {messages.length > 0 && (
                  <span className="badge badge-accent text-[10px]">{messages.length}</span>
                )}
              </div>
              <button
                onClick={onClose}
                className="text-text-muted hover:text-text transition-colors p-2 min-w-[40px] min-h-[40px] flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoading ? (
                <div className="space-y-3">
                  {[1, 2].map((i) => (
                    <div
                      key={i}
                      className="glass rounded-xl p-4 animate-pulse"
                    >
                      <div className="h-3 w-20 rounded bg-white/[0.06] mb-3" />
                      <div className="h-4 w-full rounded bg-white/[0.04] mb-2" />
                      <div className="h-4 w-3/4 rounded bg-white/[0.04]" />
                    </div>
                  ))}
                </div>
              ) : messages.length === 0 ? (
                <EmptyState />
              ) : (
                messages.map((msg) => (
                  <NotificationCard
                    key={msg.id}
                    message={msg}
                    onAccept={() => handleAccept(msg)}
                    onDismiss={() => handleDismiss(msg)}
                    launching={launching}
                  />
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ─── Notification card ──────────────────────────────────────────────────────

function NotificationCard({
  message,
  onAccept,
  onDismiss,
  launching,
}: {
  message: PracharMessage;
  onAccept: () => void;
  onDismiss: () => void;
  launching: boolean;
}) {
  const direction = message.anomaly.direction;
  const severityColor =
    message.severity === "high"
      ? "text-danger"
      : message.severity === "medium"
        ? "text-warning"
        : "text-text-muted";

  const DirectionIcon =
    direction === "drop" ? TrendingDown : direction === "spike" ? TrendingUp : Minus;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 50 }}
      className="glass rounded-xl p-4 space-y-3"
    >
      {/* Severity indicator */}
      <div className="flex items-center gap-2">
        <DirectionIcon className={cn("w-3.5 h-3.5", severityColor)} />
        <span className={cn("font-mono text-[10px] uppercase tracking-wider", severityColor)}>
          {message.severity} · {direction}
        </span>
      </div>

      {/* CURV AI message */}
      <p className="text-sm text-text leading-relaxed">{message.prachar_message}</p>

      {/* Creative directions preview */}
      {message.recommendation.creative_directions?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {message.recommendation.creative_directions.slice(0, 3).map((d, i) => (
            <span
              key={i}
              className="text-[11px] px-2 py-1 rounded-md bg-accent/10 text-accent/90"
            >
              {d}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onAccept}
          disabled={launching}
          className="btn-primary flex-1 text-xs group disabled:opacity-50"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {launching ? "Preparing…" : "Launch campaign"}
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
        <button
          onClick={onDismiss}
          className="btn-secondary text-xs px-3"
          title="Dismiss"
        >
          <Check className="w-3.5 h-3.5" />
          Dismiss
        </button>
      </div>
    </motion.div>
  );
}

// ─── Empty state ────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mb-4">
        <Check className="w-6 h-6 text-success" />
      </div>
      <p className="text-sm text-text font-medium mb-1">All clear</p>
      <p className="text-xs text-text-muted max-w-[240px]">
        No notifications — CURV AI is watching your campaigns and will ping you if anything needs attention.
      </p>
    </div>
  );
}
