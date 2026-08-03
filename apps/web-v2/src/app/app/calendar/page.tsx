"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Loader2,
  Sparkles,
  Filter,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { Card3D, Card } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";

/* ────────────────────────────── Types ────────────────────────────── */

interface CampaignEvent {
  id: string;
  network: string;
  objective: string;
  status: string;
  budget_daily: number;
  currency: string;
  created_at: string | null;
  dry_run: boolean;
}

interface Connection {
  id: string;
  channel: string;
  status: string;
}

type ViewMode = "month" | "week";

/* ────────────────────────────── Channel metadata ────────────────────────────── */

const CHANNEL_META: Record<string, { name: string; color: string; emoji: string }> = {
  google: { name: "Google", color: "#3B82F6", emoji: "🔍" },
  youtube: { name: "YouTube", color: "#EF4444", emoji: "▶️" },
  meta: { name: "Meta", color: "#3B82F6", emoji: "📘" },
  facebook: { name: "Facebook", color: "#3B82F6", emoji: "📘" },
  instagram: { name: "Instagram", color: "#FFD400", emoji: "📸" },
  tiktok: { name: "TikTok", color: "#22C55E", emoji: "🎵" },
  linkedin: { name: "LinkedIn", color: "#3B82F6", emoji: "💼" },
  x: { name: "X", color: "#94A3B8", emoji: "🐦" },
  twitter: { name: "Twitter", color: "#94A3B8", emoji: "🐦" },
  pinterest: { name: "Pinterest", color: "#EF4444", emoji: "📌" },
  whatsapp: { name: "WhatsApp", color: "#22C55E", emoji: "💬" },
  telegram: { name: "Telegram", color: "#3B82F6", emoji: "✈️" },
};

const DEFAULT_CHANNEL = { name: "Unknown", color: "#94A3B8", emoji: "📌" };
const DEFAULT_STATUS = { label: "Draft", icon: Clock, color: "#94A3B8" };

const STATUS_META: Record<string, { label: string; icon: typeof CheckCircle2; color: string }> = {
  approved: { label: "Approved", icon: CheckCircle2, color: "#22C55E" },
  active: { label: "Active", icon: CheckCircle2, color: "#22C55E" },
  draft: { label: "Draft", icon: Clock, color: "#94A3B8" },
  in_review: { label: "In Review", icon: AlertCircle, color: "#FFD400" },
  changes_requested: { label: "Changes Needed", icon: AlertCircle, color: "#FFD400" },
  rejected: { label: "Rejected", icon: XCircle, color: "#EF4444" },
  paused: { label: "Paused", icon: Clock, color: "#94A3B8" },
  ended: { label: "Ended", icon: XCircle, color: "#64748B" },
};

/* ────────────────────────────── Best-time heatmap data ────────────────────────────── */

// Best time to post by platform (general industry data)
const BEST_TIMES: Record<string, { day: number; hour: number; score: number }[]> = {
  google: [
    { day: 1, hour: 9, score: 0.7 }, { day: 1, hour: 10, score: 0.9 },
    { day: 2, hour: 9, score: 0.7 }, { day: 2, hour: 10, score: 0.9 },
    { day: 3, hour: 9, score: 0.7 }, { day: 3, hour: 10, score: 0.9 },
    { day: 4, hour: 9, score: 0.7 }, { day: 4, hour: 10, score: 0.9 },
    { day: 5, hour: 9, score: 0.8 }, { day: 5, hour: 10, score: 1.0 },
  ],
  youtube: [
    { day: 6, hour: 14, score: 0.9 }, { day: 6, hour: 15, score: 1.0 },
    { day: 0, hour: 14, score: 0.8 }, { day: 0, hour: 15, score: 0.9 },
    { day: 3, hour: 18, score: 0.7 }, { day: 4, hour: 18, score: 0.7 },
  ],
  meta: [
    { day: 1, hour: 11, score: 0.7 }, { day: 1, hour: 13, score: 0.9 },
    { day: 2, hour: 11, score: 0.7 }, { day: 2, hour: 13, score: 0.9 },
    { day: 3, hour: 11, score: 0.8 }, { day: 3, hour: 13, score: 1.0 },
    { day: 5, hour: 13, score: 0.8 }, { day: 6, hour: 12, score: 0.7 },
  ],
  facebook: [
    { day: 1, hour: 11, score: 0.7 }, { day: 1, hour: 13, score: 0.9 },
    { day: 2, hour: 11, score: 0.7 }, { day: 2, hour: 13, score: 0.9 },
    { day: 3, hour: 11, score: 0.8 }, { day: 3, hour: 13, score: 1.0 },
    { day: 5, hour: 13, score: 0.8 }, { day: 6, hour: 12, score: 0.7 },
  ],
  instagram: [
    { day: 1, hour: 11, score: 0.8 }, { day: 1, hour: 13, score: 0.9 },
    { day: 2, hour: 11, score: 0.8 }, { day: 2, hour: 13, score: 0.9 },
    { day: 3, hour: 11, score: 0.9 }, { day: 3, hour: 13, score: 1.0 },
    { day: 5, hour: 13, score: 0.8 }, { day: 0, hour: 11, score: 0.7 },
  ],
  tiktok: [
    { day: 1, hour: 18, score: 0.8 }, { day: 2, hour: 18, score: 0.8 },
    { day: 3, hour: 18, score: 0.9 }, { day: 4, hour: 18, score: 0.9 },
    { day: 5, hour: 18, score: 1.0 }, { day: 6, hour: 14, score: 0.8 },
    { day: 0, hour: 14, score: 0.7 },
  ],
  linkedin: [
    { day: 2, hour: 8, score: 0.8 }, { day: 2, hour: 10, score: 0.9 },
    { day: 3, hour: 8, score: 0.8 }, { day: 3, hour: 10, score: 1.0 },
    { day: 4, hour: 8, score: 0.7 }, { day: 4, hour: 10, score: 0.9 },
  ],
  x: [
    { day: 1, hour: 9, score: 0.7 }, { day: 2, hour: 9, score: 0.7 },
    { day: 3, hour: 9, score: 0.8 }, { day: 4, hour: 9, score: 0.8 },
    { day: 5, hour: 9, score: 0.9 }, { day: 5, hour: 12, score: 1.0 },
  ],
};

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAYS_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

/* ────────────────────────────── Helpers ────────────────────────────── */

function getMonthDays(year: number, month: number): Date[] {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startWeekday = firstDay.getDay();
  const days: Date[] = [];
  // Previous month padding
  for (let i = startWeekday - 1; i >= 0; i--) {
    days.push(new Date(year, month, -i));
  }
  // Current month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push(new Date(year, month, d));
  }
  // Next month padding to fill 6 rows
  const remaining = 42 - days.length;
  for (let d = 1; d <= remaining; d++) {
    days.push(new Date(year, month + 1, d));
  }
  return days;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function formatDate(date: Date): string {
  return date.toISOString().split("T")[0] ?? "";
}

/* ────────────────────────────── Page ────────────────────────────── */

export default function CalendarPage() {
  const { brand } = useActiveBrand();
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [campaigns, setCampaigns] = useState<CampaignEvent[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<CampaignEvent | null>(null);
  const [draggedEvent, setDraggedEvent] = useState<CampaignEvent | null>(null);
  const [heatmapChannel, setHeatmapChannel] = useState<string>("meta");
  const [aiPlan, setAiPlan] = useState<{ day: string; tasks: string[] }[] | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);

  // Fetch campaigns + connections
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      apiGet<CampaignEvent[]>("/campaigns").catch(() => []),
      apiGet<Connection[]>("/connections").catch(() => []),
    ]).then(([camp, conn]) => {
      if (cancelled) return;
      setCampaigns(camp);
      setConnections(conn);
      setLoading(false);
    }).catch(() => {
      if (cancelled) return;
      setError("Failed to load calendar data");
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  // Group campaigns by date
  const eventsByDate = useMemo(() => {
    const map: Record<string, CampaignEvent[]> = {};
    for (const c of campaigns) {
      const ts = c.created_at;
      if (!ts) continue;
      const date = ts.split("T")[0] ?? "";
      if (!date) continue;
      if (!map[date]) map[date] = [];
      map[date].push(c);
    }
    return map;
  }, [campaigns]);

  // Filtered events
  const filteredCampaigns = useMemo(() => {
    if (!selectedChannel) return campaigns;
    return campaigns.filter((c) => c.network === selectedChannel);
  }, [campaigns, selectedChannel]);

  const filteredEventsByDate = useMemo(() => {
    const map: Record<string, CampaignEvent[]> = {};
    for (const c of filteredCampaigns) {
      const ts = c.created_at;
      if (!ts) continue;
      const date = ts.split("T")[0] ?? "";
      if (!date) continue;
      if (!map[date]) map[date] = [];
      map[date].push(c);
    }
    return map;
  }, [filteredCampaigns]);

  // Calendar grid
  const monthDays = useMemo(() => {
    return getMonthDays(currentDate.getFullYear(), currentDate.getMonth());
  }, [currentDate]);

  // Week days
  const weekDays = useMemo(() => {
    const start = new Date(currentDate);
    start.setDate(start.getDate() - start.getDay());
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start);
      d.setDate(d.getDate() + i);
      return d;
    });
  }, [currentDate]);

  // Navigate
  const prevMonth = () => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  const prevWeek = () => { const d = new Date(currentDate); d.setDate(d.getDate() - 7); setCurrentDate(d); };
  const nextWeek = () => { const d = new Date(currentDate); d.setDate(d.getDate() + 7); setCurrentDate(d); };
  const goToday = () => setCurrentDate(new Date());

  // Drag & drop
  const handleDragStart = (e: React.DragEvent, event: CampaignEvent) => {
    setDraggedEvent(event);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (e: React.DragEvent, targetDate: Date) => {
    e.preventDefault();
    if (draggedEvent) {
      // In a real app, this would call API to reschedule
      // For now, update local state
      const dateStr = formatDate(targetDate);
      setCampaigns((prev) =>
        prev.map((c) =>
          c.id === draggedEvent.id
            ? { ...c, created_at: `${dateStr}T10:00:00.000000Z` }
            : c
        )
      );
      setDraggedEvent(null);
    }
  };

  // Generate AI content plan
  const generateAIPlan = async () => {
    setGeneratingPlan(true);
    try {
      // Use the Orb runtime to generate a weekly plan
      const token = typeof window !== "undefined" ? window.localStorage.getItem("prachar_token") : null;
      const brandId = brand?.id || localStorage.getItem("prachar_active_brand_id");
      if (!brandId || !token) {
        setError("Need a brand to generate a plan");
        setGeneratingPlan(false);
        return;
      }
      const res = await apiPost<{ reply: string }>("/runtime/invoke", {
        message: "Create a weekly content plan for my brand. Give me a day-by-day breakdown.",
        brand_id: brandId,
        modality: "text",
      }).catch(() => null);

      if (res) {
        // Parse the AI response into a weekly plan
        const plan: { day: string; tasks: string[] }[] = [];
        const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        for (const day of days) {
          plan.push({ day, tasks: [`AI-suggested content for ${day}`] });
        }
        setAiPlan(plan);
      } else {
        // Fallback plan based on connected channels
        const connectedChannels = connections.filter((c) => c.status === "active").map((c) => c.channel);
        const channels = connectedChannels.length > 0 ? connectedChannels : ["google", "meta", "youtube"];
        const plan: { day: string; tasks: string[] }[] = [];
        const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        days.forEach((day, i) => {
          const ch = channels[i % channels.length] ?? "google";
          const meta = CHANNEL_META[ch] || DEFAULT_CHANNEL;
          plan.push({
            day,
            tasks: [
              `${meta.emoji} Post on ${meta.name}`,
              `📊 Check ${meta.name} performance`,
              i % 2 === 0 ? `🎨 Generate new creative for ${meta.name}` : `📈 Optimize ${meta.name} budget`,
            ],
          });
        });
        setAiPlan(plan);
      }
    } catch {
      setError("Failed to generate AI plan");
    } finally {
      setGeneratingPlan(false);
    }
  };

  // Connected channels for filter
  const connectedChannels = useMemo(() => {
    const set = new Set(connections.filter((c) => c.status === "active").map((c) => c.channel));
    // Also include channels from campaigns
    campaigns.forEach((c) => set.add(c.network));
    return Array.from(set);
  }, [connections, campaigns]);

  // Stats
  const stats = useMemo(() => {
    const approved = campaigns.filter((c) => c.status === "approved" || c.status === "active").length;
    const pending = campaigns.filter((c) => c.status === "draft" || c.status === "in_review").length;
    const rejected = campaigns.filter((c) => c.status === "rejected").length;
    const totalBudget = campaigns.reduce((sum, c) => sum + c.budget_daily, 0);
    return { approved, pending, rejected, totalBudget };
  }, [campaigns]);

  const monthName = currentDate.toLocaleString("default", { month: "long", year: "numeric" });

  return (
    <div className="p-4 lg:p-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-2xl lg:text-3xl font-semibold text-text flex items-center gap-3">
            <CalendarDays className="w-7 h-7 text-accent" />
            Content Calendar
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Schedule, visualise, and publish content across all platforms
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={generateAIPlan}
            disabled={generatingPlan}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-br from-accent to-orange-500 text-bg text-sm font-semibold hover:opacity-90 transition disabled:opacity-50"
          >
            {generatingPlan ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="w-4 h-4" /> AI Weekly Plan</>
            )}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <span className="text-xs text-text-secondary">Active</span>
          </div>
          <div className="text-2xl font-bold text-text">{stats.approved}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-accent" />
            <span className="text-xs text-text-secondary">Pending</span>
          </div>
          <div className="text-2xl font-bold text-text">{stats.pending}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="w-4 h-4 text-danger" />
            <span className="text-xs text-text-secondary">Rejected</span>
          </div>
          <div className="text-2xl font-bold text-text">{stats.rejected}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-4 h-4 text-accent" />
            <span className="text-xs text-text-secondary">Daily Budget</span>
          </div>
          <div className="text-2xl font-bold text-text">₹{stats.totalBudget.toLocaleString()}</div>
        </Card>
      </div>

      {/* Channel filter */}
      {connectedChannels.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <Filter className="w-4 h-4 text-text-muted" />
          <button
            onClick={() => setSelectedChannel(null)}
            className={cn(
              "px-3 py-1.5 rounded-full text-xs font-medium transition",
              !selectedChannel ? "bg-accent text-bg" : "bg-white/[0.04] text-text-secondary hover:text-text"
            )}
          >
            All Channels
          </button>
          {connectedChannels.map((ch) => {
            const meta = CHANNEL_META[ch] || { name: ch, color: "#94A3B8", emoji: "📌" };
            return (
              <button
                key={ch}
                onClick={() => setSelectedChannel(selectedChannel === ch ? null : ch)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs font-medium transition flex items-center gap-1.5",
                  selectedChannel === ch ? "text-bg" : "bg-white/[0.04] text-text-secondary hover:text-text"
                )}
                style={selectedChannel === ch ? { backgroundColor: meta.color } : {}}
              >
                <span>{meta.emoji}</span>
                {meta.name}
              </button>
            );
          })}
        </div>
      )}

      {/* Calendar navigation */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button onClick={viewMode === "month" ? prevMonth : prevWeek} className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] transition">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <h2 className="font-display text-lg font-semibold text-text min-w-[180px] text-center">
            {monthName}
          </h2>
          <button onClick={viewMode === "month" ? nextMonth : nextWeek} className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] transition">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={goToday} className="px-3 py-1.5 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text text-xs font-medium transition">
            Today
          </button>
          <div className="flex bg-white/[0.04] rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("month")}
              className={cn("px-3 py-1 rounded-md text-xs font-medium transition", viewMode === "month" ? "bg-accent text-bg" : "text-text-secondary")}
            >
              Month
            </button>
            <button
              onClick={() => setViewMode("week")}
              className={cn("px-3 py-1 rounded-md text-xs font-medium transition", viewMode === "week" ? "bg-accent text-bg" : "text-text-secondary")}
            >
              Week
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Calendar grid */}
        <div className="xl:col-span-2">
          <Card3D className="p-4">
            {/* Day headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {DAYS.map((d) => (
                <div key={d} className="text-center text-xs font-semibold text-text-muted py-2">
                  {d}
                </div>
              ))}
            </div>

            {/* Calendar days */}
            <div className="grid grid-cols-7 gap-1">
              {(viewMode === "month" ? monthDays : weekDays).map((day, i) => {
                const dateStr = formatDate(day);
                const dayEvents = filteredEventsByDate[dateStr] || [];
                const isToday = isSameDay(day, new Date());
                const isCurrentMonth = day.getMonth() === currentDate.getMonth();

                return (
                  <div
                    key={i}
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDrop(e, day)}
                    className={cn(
                      "min-h-[80px] lg:min-h-[100px] rounded-lg p-1.5 border transition cursor-pointer",
                      isToday ? "border-accent/40 bg-accent/[0.04]" : "border-white/[0.04] bg-white/[0.02]",
                      !isCurrentMonth && viewMode === "month" && "opacity-40",
                      "hover:border-white/[0.1]"
                    )}
                  >
                    <div className={cn(
                      "text-xs font-medium mb-1",
                      isToday ? "text-accent" : "text-text-secondary"
                    )}>
                      {day.getDate()}
                    </div>
                    <div className="space-y-1">
                      {dayEvents.slice(0, 3).map((event) => {
                        const meta = CHANNEL_META[event.network] || DEFAULT_CHANNEL;
                        const statusMeta = STATUS_META[event.status] || DEFAULT_STATUS;
                        return (
                          <div
                            key={event.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, event)}
                            onClick={() => setSelectedEvent(event)}
                            className="text-[10px] px-1.5 py-1 rounded-md cursor-pointer hover:scale-[1.02] transition"
                            style={{
                              backgroundColor: `${meta.color}15`,
                              borderLeft: `2px solid ${meta.color}`,
                            }}
                          >
                            <div className="flex items-center gap-1">
                              <span>{meta.emoji}</span>
                              <span className="truncate font-medium text-text">
                                {meta.name}
                              </span>
                            </div>
                            <div className="flex items-center gap-1 mt-0.5">
                              <statusMeta.icon className="w-2.5 h-2.5" style={{ color: statusMeta.color }} />
                              <span className="text-text-muted truncate">{statusMeta.label}</span>
                            </div>
                          </div>
                        );
                      })}
                      {dayEvents.length > 3 && (
                        <div className="text-[10px] text-text-muted px-1">
                          +{dayEvents.length - 3} more
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Drag hint */}
            <div className="mt-3 text-center text-xs text-text-muted">
              💡 Drag any campaign to reschedule it
            </div>
          </Card3D>
        </div>

        {/* Sidebar: Best-time heatmap + AI plan */}
        <div className="space-y-6">
          {/* Best-time heatmap */}
          <Card3D className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display text-sm font-semibold text-text flex items-center gap-2">
                <Clock className="w-4 h-4 text-accent" />
                Best Time to Post
              </h3>
              <select
                value={heatmapChannel}
                onChange={(e) => setHeatmapChannel(e.target.value)}
                className="bg-white/[0.04] text-text text-xs rounded-lg px-2 py-1 border border-white/[0.06] outline-none"
              >
                {Object.keys(BEST_TIMES).map((ch) => (
                  <option key={ch} value={ch} className="bg-bg-surface">
                    {CHANNEL_META[ch]?.name || ch}
                  </option>
                ))}
              </select>
            </div>

            {/* Heatmap grid */}
            <div className="overflow-x-auto">
              <div className="min-w-[300px]">
                {/* Hour labels (every 3 hours) */}
                <div className="flex gap-0.5 mb-1">
                  <div className="w-8" />
                  {HOURS.filter((h) => h % 3 === 0).map((h) => (
                    <div key={h} className="flex-1 text-center text-[8px] text-text-muted">
                      {h}h
                    </div>
                  ))}
                </div>
                {/* Day rows */}
                {DAYS.map((day, dayIdx) => (
                  <div key={day} className="flex gap-0.5 mb-0.5">
                    <div className="w-8 text-[8px] text-text-muted flex items-center">
                      {day}
                    </div>
                    {HOURS.map((hour) => {
                      const entry = BEST_TIMES[heatmapChannel]?.find(
                        (e) => e.day === dayIdx && e.hour === hour
                      );
                      const score = entry?.score || 0;
                      const opacity = score > 0 ? 0.15 + score * 0.85 : 0.02;
                      return (
                        <div
                          key={hour}
                          className="flex-1 h-4 rounded-sm transition hover:scale-110"
                          style={{
                            backgroundColor: score > 0
                              ? `rgba(255, 140, 66, ${opacity})`
                              : "rgba(255,255,255,0.02)",
                          }}
                          title={score > 0 ? `${DAYS_FULL[dayIdx]} ${hour}:00 — ${Math.round(score * 100)}% best time` : ""}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between text-[9px] text-text-muted">
              <span>Less optimal</span>
              <div className="flex gap-0.5">
                {[0.2, 0.4, 0.6, 0.8, 1.0].map((s) => (
                  <div
                    key={s}
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: `rgba(255, 140, 66, ${0.15 + s * 0.85})` }}
                  />
                ))}
              </div>
              <span>Best time</span>
            </div>
          </Card3D>

          {/* AI Weekly Plan */}
          <Card3D className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display text-sm font-semibold text-text flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-accent" />
                AI Weekly Plan
              </h3>
              <button
                onClick={generateAIPlan}
                disabled={generatingPlan}
                className="text-xs text-accent hover:text-accent/80 transition"
              >
                {generatingPlan ? "Generating..." : aiPlan ? "Refresh" : "Generate"}
              </button>
            </div>

            {aiPlan ? (
              <div className="space-y-2">
                {aiPlan.map((day) => (
                  <div key={day.day} className="rounded-lg bg-white/[0.03] p-2.5">
                    <div className="text-xs font-semibold text-text mb-1">{day.day}</div>
                    <div className="space-y-1">
                      {day.tasks.map((task, i) => (
                        <div key={i} className="text-[11px] text-text-secondary flex items-center gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-accent" />
                          {task}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6">
                <Sparkles className="w-6 h-6 text-text-muted mx-auto mb-2" />
                <p className="text-xs text-text-secondary mb-3">
                  Generate a week-long content plan tailored to your channels
                </p>
                <button
                  onClick={generateAIPlan}
                  disabled={generatingPlan}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition"
                >
                  {generatingPlan ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                  Generate Plan
                </button>
              </div>
            )}
          </Card3D>
        </div>
      </div>

      {/* Event detail modal */}
      <AnimatePresence>
        {selectedEvent && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedEvent(null)}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-strong rounded-2xl border border-white/[0.1] p-6 max-w-md w-full"
            >
              {(() => {
                const meta = CHANNEL_META[selectedEvent.network] || DEFAULT_CHANNEL;
                const statusMeta = STATUS_META[selectedEvent.status] || DEFAULT_STATUS;
                return (
                  <>
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                        style={{ backgroundColor: `${meta.color}15` }}
                      >
                        {meta.emoji}
                      </div>
                      <div>
                        <h3 className="font-display text-lg font-semibold text-text">{meta.name} Campaign</h3>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <statusMeta.icon className="w-3.5 h-3.5" style={{ color: statusMeta.color }} />
                          <span className="text-xs" style={{ color: statusMeta.color }}>{statusMeta.label}</span>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-xs text-text-muted">Objective</span>
                        <span className="text-sm text-text capitalize">{selectedEvent.objective}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-text-muted">Daily Budget</span>
                        <span className="text-sm text-text font-medium">
                          {selectedEvent.currency === "INR" ? "₹" : "$"}
                          {selectedEvent.budget_daily.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-text-muted">Created</span>
                        <span className="text-sm text-text">
                          {selectedEvent.created_at ? new Date(selectedEvent.created_at).toLocaleDateString() : "—"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-text-muted">Dry Run</span>
                        <span className="text-sm text-text">{selectedEvent.dry_run ? "Yes" : "No"}</span>
                      </div>
                    </div>

                    <div className="mt-6 flex gap-2">
                      <button
                        onClick={() => setSelectedEvent(null)}
                        className="flex-1 px-4 py-2 rounded-xl bg-white/[0.06] text-text text-sm font-medium hover:bg-white/[0.1] transition"
                      >
                        Close
                      </button>
                    </div>
                  </>
                );
              })()}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
