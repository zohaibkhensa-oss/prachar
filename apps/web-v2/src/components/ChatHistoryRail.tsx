"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Plus, Search } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ChatSession {
  session_id: string;
  title: string;
  preview: string;
  timestamp: string;
  created_at: string;
}

function groupByDate(sessions: ChatSession[]): { label: string; items: ChatSession[] }[] {
  const groups: Record<string, ChatSession[]> = {};
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  for (const s of sessions) {
    const date = new Date(s.timestamp || s.created_at);
    const label =
      date >= today ? "Today"
      : date >= yesterday ? "Yesterday"
      : date >= weekAgo ? "Previous 7 days"
      : "Older";
    (groups[label] ??= []).push(s);
  }

  return ["Today", "Yesterday", "Previous 7 days", "Older"]
    .filter((l) => groups[l])
    .map((l) => ({ label: l, items: groups[l]! }));
}

/** ChatGPT/Gemini-style conversation rail: New chat + grouped session list. */
export function ChatHistoryRail({
  activeSessionId,
  onNewChat,
  refreshKey = 0,
}: {
  activeSessionId: string | null;
  onNewChat: () => void;
  /** bump to refetch (e.g. message count — a completed session gains a title) */
  refreshKey?: number;
}) {
  const router = useRouter();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiGet<{ sessions: ChatSession[]; count: number }>(
        "/runtime/sessions?limit=50",
      );
      setSessions(data.sessions || []);
    } catch {
      // silent — rail is supplementary navigation
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions, refreshKey]);

  const filtered = search.trim()
    ? sessions.filter((s) =>
        `${s.title} ${s.preview}`.toLowerCase().includes(search.toLowerCase()),
      )
    : sessions;
  const grouped = groupByDate(filtered);

  return (
    <aside className="hidden lg:flex w-60 xl:w-64 flex-col border-r border-white/[0.05] flex-shrink-0 bg-bg/50">
      {/* New chat */}
      <div className="p-3 pb-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-accent/15 text-accent text-sm font-medium hover:bg-accent/25 transition-all"
        >
          <Plus className="w-4 h-4" />
          New chat
        </button>
      </div>

      {/* Search */}
      {sessions.length > 3 && (
        <div className="px-3 pb-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search"
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:border-accent/40 transition-colors"
            />
          </div>
        </div>
      )}

      {/* Session list */}
      <div className="flex-1 overflow-y-auto scrollbar-none px-2 pb-3">
        {loading && (
          <div className="space-y-2 pt-1">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-8 w-full rounded-lg" />
            ))}
          </div>
        )}

        {!loading && grouped.length === 0 && (
          <div className="px-2 pt-6 text-center">
            <MessageSquare className="w-5 h-5 text-text-muted/30 mx-auto mb-2" />
            <p className="text-[11px] text-text-muted/60">
              {search ? "No matches" : "No conversations yet"}
            </p>
          </div>
        )}

        {!loading &&
          grouped.map((group) => (
            <div key={group.label} className="pt-3 first:pt-1">
              <div className="px-2 pb-1.5 text-[10px] font-semibold text-text-muted/50 uppercase tracking-wider">
                {group.label}
              </div>
              {group.items.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => router.push(`/app?session=${s.session_id}`)}
                  title={s.title}
                  className={cn(
                    "w-full text-left px-2.5 py-2 rounded-lg text-[13px] truncate transition-colors mb-0.5",
                    s.session_id === activeSessionId
                      ? "bg-accent/15 text-text"
                      : "text-text-secondary hover:bg-white/[0.04] hover:text-text",
                  )}
                >
                  {s.title || "New conversation"}
                </button>
              ))}
            </div>
          ))}
      </div>
    </aside>
  );
}
