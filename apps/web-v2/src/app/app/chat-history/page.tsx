"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { MessageSquare, Sparkles, Clock, Plus, ArrowRight, Search } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

interface ChatSession {
  session_id: string;
  title: string;
  preview: string;
  timestamp: string;
  created_at: string;
  event_count: number;
  duration_s: number;
  has_artefacts: boolean;
}

function timeAgo(ts: string): string {
  if (!ts) return "";
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function groupByDate(sessions: ChatSession[]): { label: string; items: ChatSession[] }[] {
  const groups: Record<string, ChatSession[]> = {};
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  for (const s of sessions) {
    const date = new Date(s.timestamp || s.created_at);
    let label: string;
    if (date >= today) label = "Today";
    else if (date >= yesterday) label = "Yesterday";
    else if (date >= weekAgo) label = "Previous 7 days";
    else label = "Older";

    if (!groups[label]) groups[label] = [];
    groups[label]!.push(s);
  }

  const order = ["Today", "Yesterday", "Previous 7 days", "Older"];
  return order
    .filter((l) => groups[l])
    .map((l) => ({ label: l, items: groups[l]! }));
}

export default function ChatHistoryPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ sessions: ChatSession[]; count: number }>(
        "/runtime/sessions?limit=100",
      );
      setSessions(data.sessions || []);
    } catch (err) {
      setError("Failed to load chat history");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleOpenSession = (sessionId: string) => {
    router.push(`/app?session=${sessionId}`);
  };

  const handleNewChat = () => {
    router.push("/app");
  };

  const filtered = search.trim()
    ? sessions.filter(
        (s) =>
          s.title.toLowerCase().includes(search.toLowerCase()) ||
          s.preview.toLowerCase().includes(search.toLowerCase()),
      )
    : sessions;

  const grouped = groupByDate(filtered);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-text">Chat History</h1>
          <p className="text-sm text-text-muted mt-1">
            {sessions.length > 0
              ? `${sessions.length} conversation${sessions.length > 1 ? "s" : ""}`
              : "Your conversations with CURV AI"}
          </p>
        </div>
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent/15 text-accent text-sm font-medium hover:bg-accent/25 transition-all"
        >
          <Plus className="w-4 h-4" />
          New chat
        </button>
      </div>

      {/* Search */}
      {sessions.length > 0 && (
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-bg-surface border border-white/[0.06] text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:border-accent/40 transition-colors"
          />
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="text-center py-16">
          <MessageSquare className="w-12 h-12 text-text-muted/30 mx-auto mb-3" />
          <p className="text-sm text-text-muted">{error}</p>
          <button
            onClick={fetchSessions}
            className="mt-3 text-sm text-accent hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && sessions.length === 0 && (
        <div className="text-center py-20">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            <MessageSquare className="w-16 h-16 text-text-muted/20 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-text mb-1">No conversations yet</h3>
            <p className="text-sm text-text-muted mb-6">
              Start chatting with CURV AI to see your history here
            </p>
            <button
              onClick={handleNewChat}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent/15 text-accent text-sm font-medium hover:bg-accent/25 transition-all"
            >
              <Plus className="w-4 h-4" />
              Start a conversation
            </button>
          </motion.div>
        </div>
      )}

      {/* No search results */}
      {!loading && !error && sessions.length > 0 && filtered.length === 0 && (
        <div className="text-center py-16">
          <Search className="w-10 h-10 text-text-muted/30 mx-auto mb-3" />
          <p className="text-sm text-text-muted">No conversations match "{search}"</p>
        </div>
      )}

      {/* Session list */}
      {!loading && !error && grouped.length > 0 && (
        <div className="space-y-6">
          {grouped.map((group) => (
            <div key={group.label}>
              <div className="px-1 mb-2 text-xs font-semibold text-text-muted/60 uppercase tracking-wider">
                {group.label}
              </div>
              <div className="space-y-2">
                {group.items.map((session, idx) => (
                  <motion.button
                    key={session.session_id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                    onClick={() => handleOpenSession(session.session_id)}
                    className="w-full text-left p-4 rounded-xl bg-bg-surface border border-white/[0.04] hover:border-accent/20 hover:bg-accent/[0.03] transition-all group"
                  >
                    <div className="flex items-start gap-3">
                      {/* Icon */}
                      <div className="flex-shrink-0 mt-0.5">
                        {session.has_artefacts ? (
                          <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                            <Sparkles className="w-4 h-4 text-accent" />
                          </div>
                        ) : (
                          <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center">
                            <MessageSquare className="w-4 h-4 text-text-muted" />
                          </div>
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <h3 className="text-sm font-medium text-text truncate">
                            {session.title}
                          </h3>
                          <span className="text-[10px] text-text-muted/60 flex items-center gap-1 flex-shrink-0">
                            <Clock className="w-3 h-3" />
                            {timeAgo(session.timestamp)}
                          </span>
                        </div>
                        {session.preview && (
                          <p className="text-xs text-text-muted/80 line-clamp-2 mb-2">
                            {session.preview}
                          </p>
                        )}
                        <div className="flex items-center gap-3 text-[10px] text-text-muted/50">
                          <span>{session.event_count} events</span>
                          {session.duration_s > 0 && (
                            <span>{session.duration_s}s duration</span>
                          )}
                          {session.has_artefacts && (
                            <span className="text-accent/70 flex items-center gap-0.5">
                              <Sparkles className="w-2.5 h-2.5" />
                              Has artefacts
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Arrow */}
                      <ArrowRight className="w-4 h-4 text-text-muted/30 group-hover:text-accent group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-2" />
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
