"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { AIOrb } from "@/components/AIOrb";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, ArrowRight, Sparkles } from "lucide-react";
import { useDashboardOverview } from "@/lib/runtime";
import { useActiveBrand } from "@/lib/hooks";

// Map orb suggestion strings → real routes
const SUGGESTION_ROUTES: Record<string, string> = {
  "Create a campaign": "/app/campaigns",
  "How are my ads doing?": "/app/performance",
  "Generate an image": "/app/images",
  "What needs attention?": "/app/review",
};

// Map action button intents → real routes
const INTENT_ROUTES: Record<string, string> = {
  "campaign.create": "/app/campaigns",
  "campaign.review": "/app/review",
  "analytics.view": "/app/analytics",
  "performance.view": "/app/performance",
};

export default function DashboardPage() {
  const router = useRouter();
  const { brand } = useActiveBrand();
  const { data, loading, error } = useDashboardOverview(brand?.id ?? null);

  if (loading && !data) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col items-center text-center pt-6 pb-8">
          <AIOrb state="understanding" size={110} showWaves />
          <Skeleton className="h-8 w-64 mt-6" />
          <Skeleton className="h-20 w-full max-w-xl mt-4" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col items-center text-center pt-6 pb-8">
          <AIOrb state="error" size={110} />
          <p className="mt-6 text-sm text-text-secondary">
            Couldn't load your dashboard. The AI Runtime might not be running.
          </p>
        </div>
      </div>
    );
  }

  const { greeting, performance, campaigns, tasks, memory, activity, orb } = data;
  const pendingCount = campaigns.pending.length;
  const activeCount = campaigns.active.length;

  // Graceful brand-name handling — the API greets with the brand name, but
  // some brands have placeholder names like "Restaurant (not specified)".
  // Strip the placeholder so the greeting stays warm and professional.
  const BAD_NAME_PATTERN = /\(not specified\)|\(unknown\)|^test\s/i;
  const displayGreeting = (() => {
    let text = greeting.text;
    // Remove the ", <bad name>" suffix when the brand name is a placeholder.
    const commaIdx = text.lastIndexOf(", ");
    if (commaIdx !== -1) {
      const namePart = text.slice(commaIdx + 2).split(".")[0]?.trim() ?? "";
      if (BAD_NAME_PATTERN.test(namePart)) {
        text = text.slice(0, commaIdx) + text.slice(commaIdx).replace(/, .+?(\.|$)/, "$1");
      }
    }
    return text;
  })();
  const brandNameIsPlaceholder = BAD_NAME_PATTERN.test(brand?.name ?? "");

  return (
    <div className="max-w-5xl mx-auto">
      {/* ═══ AI Greeting — the v2 hero ═══ */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center text-center pt-6 pb-8"
      >
        <AIOrb state="idle" size={110} showWaves />

        <h1 className="mt-6 font-display text-2xl lg:text-3xl font-bold">
          {displayGreeting}
        </h1>

        {brandNameIsPlaceholder && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            onClick={() => router.push("/app/brands")}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-accent/80 hover:text-accent transition-colors"
          >
            <Sparkles className="w-3 h-3" />
            Set your business name
          </motion.button>
        )}

        {/* AI caption */}
        <div className="mt-4 max-w-xl">
          <div className="glass rounded-2xl p-4 border-l-2 border-l-accent/50 text-left">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center shrink-0">
                <Sparkles className="w-3.5 h-3.5 text-bg" />
              </div>
              <p className="text-sm text-text leading-relaxed">
                {activeCount > 0 ? (
                  <>
                    I analysed your campaigns overnight.{" "}
                    <span className="text-text font-medium">{activeCount} campaigns</span> are running.{" "}
                    {pendingCount > 0 ? (
                      <>
                        <span className="text-accent font-medium">{pendingCount} need your approval.</span>{" "}
                        Would you like me to show them?
                      </>
                    ) : (
                      "Everything looks healthy. What are we building today?"
                    )}
                  </>
                ) : (
                  <>
                    Your marketing team is ready. I can create campaigns, generate content, analyse performance, and manage your channels.{" "}
                    <span className="text-accent font-medium">What are we building today?</span>
                  </>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Action buttons — wired to real navigation */}
        <div className="mt-5 flex gap-2 flex-wrap justify-center">
          {greeting.action_buttons.map((btn, i) => {
            const href = btn.href || INTENT_ROUTES[btn.intent || ""];
            return (
              <button
                key={i}
                onClick={() => href && router.push(href)}
                disabled={!href}
                className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 transition-all ${
                  i === 0
                    ? "bg-gradient-to-br from-accent to-orange-500 text-bg"
                    : "bg-white/[0.03] border border-white/[0.06] text-text-secondary hover:text-text"
                } ${!href ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
              >
                {btn.label}
                {i === 0 && <ArrowRight className="w-3.5 h-3.5" />}
              </button>
            );
          })}
        </div>

        {/* Orb suggestions — wired to real navigation */}
        <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-2xl">
          {orb.suggestions.map((s) => {
            const href = SUGGESTION_ROUTES[s];
            return (
              <button
                key={s}
                onClick={() => href && router.push(href)}
                disabled={!href}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06] text-xs text-text-secondary transition-all ${
                  href ? "hover:bg-white/[0.06] hover:text-text cursor-pointer" : "opacity-50 cursor-default"
                }`}
              >
                <span>✦</span>
                {s}
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* ═══ KPI row ═══ */}
      <div
        className={`grid gap-3 mb-6 ${
          performance.kpis.length === 3
            ? "grid-cols-3"
            : performance.kpis.length === 2
              ? "grid-cols-2"
              : "grid-cols-2 lg:grid-cols-4"
        }`}
      >
        {performance.kpis.map((kpi, i) => (
          <motion.div
            key={kpi.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 + i * 0.05 }}
            whileHover={{ y: -2 }}
            className="glass rounded-xl p-4 transition-shadow hover:shadow-glow/30"
          >
            <div className="text-[10px] text-text-muted uppercase tracking-wider">{kpi.label}</div>
            <div className="font-display text-2xl font-bold mt-1">{kpi.value}</div>
            <div className={`text-[11px] mt-1 flex items-center gap-1 ${kpi.trend_up ? "text-success" : "text-text-muted"}`}>
              {kpi.trend_up && <TrendingUp className="w-3 h-3" />}
              {kpi.trend}
            </div>
          </motion.div>
        ))}
      </div>

      {/* ═══ AI Team mini-grid ═══ */}
      <div className="mb-6">
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          Your AI Team — working now
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {tasks.ai_team.map((agent, i) => (
            <motion.div
              key={agent.agent}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.2 + i * 0.05 }}
              whileHover={{ y: -2 }}
              className="glass rounded-xl p-4 text-center transition-shadow hover:shadow-glow/20"
            >
              <div className="text-2xl mb-2">{agent.icon}</div>
              <div className="text-xs font-semibold">{agent.agent}</div>
              <div className={`text-[10px] mt-1 ${agent.status === "working" ? "text-success" : "text-text-muted"}`}>
                ● {agent.status}
              </div>
              <div className="text-[10px] text-text-muted mt-1.5">{agent.detail}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ═══ Live AI Activity feed (from timeline) ═══ */}
      <div className="mb-6">
        <div className="text-[10px] text-text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
          Live AI Activity
        </div>
        <div className="space-y-2">
          {activity.items.length === 0 ? (
            <div className="glass rounded-xl p-4 text-sm text-text-muted text-center">
              No activity yet. Start by creating a campaign!
            </div>
          ) : (
            activity.items.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: 0.3 + i * 0.08 }}
                className="glass rounded-xl p-4 flex gap-3"
              >
                <div className="w-10 h-10 rounded-xl bg-white/[0.04] flex items-center justify-center text-lg flex-shrink-0">
                  {item.actor === "ai" ? "✦" : item.actor === "user" ? "👤" : "⚙"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold">{item.title}</span>
                    <span className="text-[10px] text-text-muted">{timeAgo(item.created_at)}</span>
                  </div>
                  {item.summary && (
                    <p className="text-xs text-text-secondary mt-1 line-clamp-2">{item.summary}</p>
                  )}
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>

      {/* ═══ Memory section ═══ */}
      {memory.recent_learnings && memory.recent_learnings.length > 0 && (
        <div className="mb-6">
          <div className="text-[10px] text-text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            What I've learned about your business
          </div>
          <div className="glass rounded-xl p-4">
            <div className="flex flex-wrap gap-2">
              {memory.recent_learnings.map((learning, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/[0.06] border border-accent/20 text-xs text-text-secondary"
                >
                  🧠 {learning}
                </span>
              ))}
            </div>
            {memory.total_campaigns > 0 && (
              <div className="mt-3 text-[10px] text-text-muted">
                {memory.total_campaigns} campaigns run · Average ROI: {memory.average_roi}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
