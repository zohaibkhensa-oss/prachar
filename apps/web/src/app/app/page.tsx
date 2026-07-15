"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Metric } from "@/components/ui/metric";
import { Card3D, Card } from "@/components/ui/card-3d";
import { AIStatusBlock, AIRecommendation } from "@/components/ui/ai-blocks";
import { Timeline, ActivityFeed } from "@/components/ui/timeline";
import { PerformanceRing, Sparkline, ProgressBar } from "@/components/ui/charts";
import { SectionHeader, EmptyState } from "@/components/ui/empty-state";
import {
  DollarSign,
  TrendingUp,
  Eye,
  Target,
  Zap,
  Brain,
  Sparkles,
  Rocket,
  AlertTriangle,
  Trophy,
  Activity,
  ArrowRight,
  Plus,
  Wand2,
  FileText,
  Megaphone,
} from "lucide-react";
import Link from "next/link";

const SPARK_DATA = [12, 18, 15, 22, 28, 25, 32, 35, 30, 38, 42, 48];

const TIMELINE_ENTRIES = [
  { id: "1", title: "Weekly loop completed", description: "Brand: Demo Coffee Co · Score improved 17.5 → 24.3", timestamp: "2m ago", status: "done" as const },
  { id: "2", title: "AI generating creatives", description: "3 ad variants for Google RSA campaign", timestamp: "5m ago", status: "active" as const },
  { id: "3", title: "Budget reallocated", description: "Shifted ₹2,000 from Meta → Google (CPA 18% lower)", timestamp: "12m ago", status: "done" as const },
  { id: "4", title: "New competitor detected", description: "BeanThere Coffee ranking for 'specialty coffee mumbai'", timestamp: "1h ago", status: "pending" as const },
  { id: "5", title: "YouTube transcript processed", description: "2 videos transcribed → metadata optimized", timestamp: "2h ago", status: "done" as const },
];

const WINS = [
  { id: "1", icon: <Trophy className="w-3.5 h-3.5" />, title: "CTR up 23% on Google RSA", meta: "Demo Coffee Co", value: "+23%" },
  { id: "2", icon: <Target className="w-3.5 h-3.5" />, title: "5 new conversions today", meta: "Meta Ads", value: "5" },
  { id: "3", icon: <Eye className="w-3.5 h-3.5" />, title: "Organic reach 12.4K", meta: "Instagram", value: "12.4K" },
  { id: "4", icon: <TrendingUp className="w-3.5 h-3.5" />, title: "Visibility score +6.8 pts", meta: "Demo Coffee Co", value: "+6.8" },
];

const RECOMMENDATIONS = [
  {
    title: "Increase Google Ads budget by 15%",
    reasoning: "Google RSA campaign has 18% lower CPA than Meta. Reallocating budget could yield 12 more conversions/week at current efficiency.",
    action: "Reallocate ₹1,500/day → Google Ads",
    confidence: 87,
  },
  {
    title: "Publish 2 YouTube videos this week",
    reasoning: "YouTube channel has 0 uploads in 14 days. Competitors average 3/week. Transcript→metadata engine is ready.",
    action: "Generate video metadata → Schedule upload",
    confidence: 92,
  },
];

const QUICK_ACTIONS = [
  { label: "New Campaign", icon: Megaphone, path: "/app/campaigns", accent: "text-accent" },
  { label: "Generate Creative", icon: Wand2, path: "/app/creative", accent: "text-info" },
  { label: "Run Audit", icon: Brain, path: "/app/brands", accent: "text-success" },
  { label: "View Reports", icon: FileText, path: "/app/reports", accent: "text-warning" },
];

export default function MissionControl() {
  return (
    <div className="space-y-6">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Mission Control</h1>
          <p className="text-sm text-text-secondary mt-1">
            Your AI advertising operating system · Live
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge badge-success">
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full bg-success"
            />
            All systems operational
          </span>
        </div>
      </div>

      {/* ─── AI Status Bar ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <AIStatusBlock
          status="generating"
          label="AI Generating Creatives"
          detail="3 variants for Google RSA · Demo Coffee Co"
          confidence={87}
        />
        <AIStatusBlock
          status="analyzing"
          label="AI Analyzing Competitors"
          detail="Scanning 4 competitors across 6 channels"
          confidence={74}
        />
        <AIStatusBlock
          status="done"
          label="Weekly Loop Complete"
          detail="Score improved 17.5 → 24.3 (+6.8 pts)"
        />
      </div>

      {/* ─── Key Metrics ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Total Spend (30d)" value={45200} format="currency" delta={12.5} deltaLabel="vs last month" icon={<DollarSign className="w-4 h-4" />} accent="accent" />
        <Metric label="Conversions" value={127} delta={23} deltaLabel="vs last week" icon={<Target className="w-4 h-4" />} accent="success" />
        <Metric label="Impressions" value={284000} format="compact" delta={8.3} icon={<Eye className="w-4 h-4" />} accent="info" />
        <Metric label="Avg CPA" value={356} format="currency" delta={-18} deltaLabel="improved" icon={<TrendingUp className="w-4 h-4" />} accent="success" />
      </div>

      {/* ─── Main Grid ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Visibility + Campaign Health */}
        <div className="space-y-6">
          <Card3D glow className="flex flex-col items-center">
            <SectionHeader title="Visibility Score" subtitle="Weighted across all channels" />
            <PerformanceRing value={24.3} size={140} strokeWidth={10} sublabel="out of 100" accent="#FFD400" />
            <div className="grid grid-cols-2 gap-3 w-full mt-4">
              <div className="text-center">
                <div className="label-field">Organic Rank</div>
                <div className="font-mono text-sm text-text mt-1">18.2</div>
                <ProgressBar value={18.2} accent="success" className="mt-1.5" />
              </div>
              <div className="text-center">
                <div className="label-field">AI Citation</div>
                <div className="font-mono text-sm text-text mt-1">12.0</div>
                <ProgressBar value={12.0} accent="info" className="mt-1.5" />
              </div>
              <div className="text-center">
                <div className="label-field">Social Reach</div>
                <div className="font-mono text-sm text-text mt-1">31.5</div>
                <ProgressBar value={31.5} accent="accent" className="mt-1.5" />
              </div>
              <div className="text-center">
                <div className="label-field">Momentum</div>
                <div className="font-mono text-sm text-text mt-1">28.0</div>
                <ProgressBar value={28.0} accent="warning" className="mt-1.5" />
              </div>
            </div>
          </Card3D>

          <Card>
            <SectionHeader title="Campaign Health" subtitle="Active campaigns across networks" />
            <div className="space-y-3">
              {[
                { name: "Google RSA — Coffee", status: "healthy", roas: 3.2, budget: 500 },
                { name: "Meta CBO — Retarget", status: "warning", roas: 1.8, budget: 300 },
                { name: "YouTube — Awareness", status: "healthy", roas: 2.5, budget: 200 },
              ].map((c) => (
                <div key={c.name} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                  <div className="flex items-center gap-2">
                    <span className={cn("w-2 h-2 rounded-full", c.status === "healthy" ? "bg-success" : "bg-warning")} />
                    <span className="text-sm text-text">{c.name}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-xs text-text-secondary">ROAS {c.roas}x</span>
                    <span className="font-mono text-xs text-accent">₹{c.budget}/d</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Center: Live Timeline + Today's Wins */}
        <div className="space-y-6">
          <Card>
            <SectionHeader
              title="Live Timeline"
              subtitle="Real-time AI activity"
              icon={<Activity className="w-4 h-4" />}
            />
            <Timeline entries={TIMELINE_ENTRIES} />
          </Card>

          <Card>
            <SectionHeader title="Today's Wins" subtitle="AI-identified achievements" icon={<Trophy className="w-4 h-4" />} />
            <ActivityFeed items={WINS} />
          </Card>
        </div>

        {/* Right: AI Recommendations + Quick Actions + Budget */}
        <div className="space-y-6">
          <div>
            <SectionHeader title="AI Recommendations" subtitle="Suggested actions" icon={<Sparkles className="w-4 h-4" />} />
            <div className="space-y-3">
              {RECOMMENDATIONS.map((rec, i) => (
                <AIRecommendation key={i} {...rec} />
              ))}
            </div>
          </div>

          <Card>
            <SectionHeader title="Quick Actions" />
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ACTIONS.map((action) => (
                <Link
                  key={action.label}
                  href={action.path}
                  className="group flex flex-col items-center gap-2 p-4 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.04] hover:border-white/[0.08] transition-all"
                >
                  <action.icon className={cn("w-5 h-5 transition-transform group-hover:scale-110", action.accent)} />
                  <span className="text-xs text-text-secondary group-hover:text-text transition-colors text-center">
                    {action.label}
                  </span>
                </Link>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeader title="Budget Utilization" subtitle="This month" />
            <div className="space-y-3">
              <div>
                <div className="flex justify-between mb-1.5">
                  <span className="text-xs text-text-secondary">AI Tokens</span>
                  <span className="font-mono text-xs text-text">2,847 / 10,000</span>
                </div>
                <ProgressBar value={2847} max={10000} accent="accent" />
              </div>
              <div>
                <div className="flex justify-between mb-1.5">
                  <span className="text-xs text-text-secondary">Ad Spend</span>
                  <span className="font-mono text-xs text-text">₹45,200 / ₹50,000</span>
                </div>
                <ProgressBar value={45200} max={50000} accent="warning" />
              </div>
              <div className="pt-2 border-t border-white/[0.04]">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Next reset</span>
                  <span className="font-mono text-xs text-text-secondary">14 days</span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* ─── Bottom: Alerts + Market Trends ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <SectionHeader title="Alerts & Opportunities" icon={<AlertTriangle className="w-4 h-4" />} />
          <div className="space-y-2">
            {[
              { type: "warning", title: "Meta CPA above target", desc: "CPA ₹420 vs target ₹350. Consider pausing low-performing ad sets." },
              { type: "info", title: "New keyword opportunity", desc: "'specialty coffee subscription' trending +340% in your geo." },
              { type: "success", title: "YouTube video ranking #3", desc: "'Best cold brew recipe' hit page 1 for 3 target keywords." },
            ].map((alert, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className={cn(
                  "flex items-start gap-3 p-3 rounded-lg border",
                  alert.type === "warning" && "bg-warning/5 border-warning/10",
                  alert.type === "info" && "bg-info/5 border-info/10",
                  alert.type === "success" && "bg-success/5 border-success/10",
                )}
              >
                <div className={cn(
                  "w-6 h-6 rounded-md flex items-center justify-center shrink-0",
                  alert.type === "warning" && "bg-warning/10 text-warning",
                  alert.type === "info" && "bg-info/10 text-info",
                  alert.type === "success" && "bg-success/10 text-success",
                )}>
                  <AlertTriangle className="w-3 h-3" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text font-medium">{alert.title}</div>
                  <div className="text-xs text-text-secondary mt-0.5">{alert.desc}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionHeader title="Market Trends" subtitle="7-day performance trend" icon={<TrendingUp className="w-4 h-4" />} />
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="font-display text-3xl font-semibold text-text">48.2K</span>
              <span className="text-xs text-success ml-2 font-mono">+12.3%</span>
            </div>
            <Sparkline data={SPARK_DATA} width={120} height={40} color="#FFD400" />
          </div>
          <div className="space-y-2">
            {[
              { label: "Organic Traffic", value: "18.4K", trend: "+8%", color: "success" },
              { label: "Paid Clicks", value: "12.1K", trend: "+15%", color: "success" },
              { label: "Social Engagement", value: "9.2K", trend: "+22%", color: "success" },
              { label: "AI Citations", value: "8.5K", trend: "-3%", color: "danger" },
            ].map((row) => (
              <div key={row.label} className="flex items-center justify-between py-2 border-b border-white/[0.03] last:border-0">
                <span className="text-sm text-text-secondary">{row.label}</span>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm text-text">{row.value}</span>
                  <span className={cn("font-mono text-xs", row.color === "success" ? "text-success" : "text-danger")}>
                    {row.trend}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
