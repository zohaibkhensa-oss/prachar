"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useTimeline, replayTimelineEntry } from "@/lib/runtime";
import { useActiveBrand } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

const ENTRY_TYPE_ICONS: Record<string, string> = {
  decision_contract: "📋",
  conversation: "💬",
  campaign_created: "📢",
  campaign_analysis: "🔍",
  council_review: "👥",
  creative_generated: "🎨",
  image_generated: "🖼️",
  video_generated: "🎬",
  approval: "✅",
  published: "📤",
  performance_update: "📊",
  proactive_alert: "⚠️",
  budget_reallocated: "💰",
  memory_updated: "🧠",
  repurposed: "♻️",
  automation_run: "🤖",
  session_completed: "✓",
};

const ACTOR_LABELS: Record<string, string> = {
  user: "You",
  ai: "CURV AI",
  system: "System",
};

export default function TimelinePage() {
  const { brand } = useActiveBrand();
  const { items, loading, error, nextCursor, loadMore, refetch } = useTimeline(brand?.id ?? null, 50);
  const [replaying, setReplaying] = useState<string | null>(null);
  const [replayMsg, setReplayMsg] = useState<string | null>(null);

  const handleReplay = async (entryId: string, title: string) => {
    setReplaying(entryId);
    setReplayMsg(null);
    try {
      const res = await replayTimelineEntry(entryId);
      setReplayMsg(`✓ Replayed "${title}" — session ${res.session_id.slice(0, 8)}…`);
      refetch();
    } catch (err: any) {
      setReplayMsg(`✗ Couldn't replay: ${err.message || "unknown error"}`);
    } finally {
      setReplaying(null);
      setTimeout(() => setReplayMsg(null), 4000);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold">Workspace Timeline</h1>
        <p className="text-sm text-text-secondary mt-1">
          Every action, every decision, every learning — your marketing history.
        </p>
      </div>

      {/* Timeline */}
      {loading && items.length === 0 ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : error ? (
        <div className="glass rounded-xl p-6 text-center">
          <p className="text-sm text-text-secondary">{error}</p>
        </div>
      ) : items.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-sm text-text-secondary">
            No activity yet. Start by creating a campaign or asking CURV AI something.
          </p>
        </div>
      ) : (
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-white/[0.06]" />

          <div className="space-y-3">
            {items.map((entry, i) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: Math.min(i * 0.04, 0.4) }}
                className="relative pl-14"
              >
                {/* Icon */}
                <div className="absolute left-0 top-3 w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-lg">
                  {ENTRY_TYPE_ICONS[entry.entry_type] || "•"}
                </div>

                {/* Content */}
                <div className="glass rounded-xl p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold">{entry.title}</span>
                      {entry.replayable && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">
                          REPLAYABLE
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-text-muted flex-shrink-0">
                      {timeAgo(entry.created_at)}
                    </span>
                  </div>

                  {entry.summary && (
                    <p className="text-xs text-text-secondary mt-1.5 line-clamp-2">
                      {entry.summary}
                    </p>
                  )}

                  <div className="mt-2 flex items-center gap-2 text-[10px] text-text-muted">
                    <span className="px-1.5 py-0.5 rounded bg-white/[0.04]">
                      {ACTOR_LABELS[entry.actor] || entry.actor}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-white/[0.04]">
                      {entry.entry_type.replace(/_/g, " ")}
                    </span>
                  </div>

                  {/* Replay button — wired to backend */}
                  {entry.replayable && (
                    <button
                      onClick={() => handleReplay(entry.id, entry.title)}
                      disabled={replaying === entry.id}
                      className="mt-2 text-[10px] text-accent hover:text-accent/80 transition-colors disabled:opacity-40"
                    >
                      {replaying === entry.id ? "↻ Replaying…" : "↻ Replay this action"}
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Load more */}
          {nextCursor && (
            <div className="mt-4 text-center">
              <button
                onClick={loadMore}
                className="px-4 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-sm text-text-secondary hover:text-text transition-colors"
              >
                Load more
              </button>
            </div>
          )}
        </div>
      )}

      {/* Replay status toast */}
      {replayMsg && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-20 left-1/2 -translate-x-1/2 glass-strong rounded-xl px-4 py-2 text-xs text-text z-50"
        >
          {replayMsg}
        </motion.div>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
