"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { ProgressBar } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Users, Share2, TrendingUp, DollarSign, Award, Plus,
  MessageSquare, Send, Wand2, Filter, Trophy, Medal,
  Instagram, Linkedin, Twitter, Facebook, Sparkles,
  BookOpen, Target, Star, Crown,
} from "lucide-react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const ADVOCATES = [
  { id: 1, name: "Sarah Chen", role: "Sales Lead", dept: "Sales", platforms: ["linkedin", "twitter"], posts: 28, reach: 45000, engagement: 8.2, score: 92, badge: "Champion" },
  { id: 2, name: "Mike Rodriguez", role: "Marketing Manager", dept: "Marketing", platforms: ["linkedin", "twitter", "facebook"], posts: 24, reach: 38000, engagement: 7.5, score: 88, badge: "Champion" },
  { id: 3, name: "Emma Wilson", role: "Product Designer", dept: "Design", platforms: ["linkedin", "instagram"], posts: 18, reach: 22000, engagement: 9.1, score: 85, badge: "Active" },
  { id: 4, name: "James Park", role: "Engineer", dept: "Engineering", platforms: ["linkedin"], posts: 8, reach: 5400, engagement: 4.2, score: 62, badge: "Active" },
  { id: 5, name: "Lisa Brown", role: "Sales Rep", dept: "Sales", platforms: ["linkedin", "twitter"], posts: 22, reach: 31000, engagement: 7.8, score: 84, badge: "Active" },
  { id: 6, name: "David Kim", role: "Data Scientist", dept: "Engineering", platforms: ["twitter"], posts: 3, reach: 1200, engagement: 2.1, score: 35, badge: "Inactive" },
  { id: 7, name: "Nina Patel", role: "Content Strategist", dept: "Marketing", platforms: ["linkedin", "instagram", "twitter"], posts: 31, reach: 52000, engagement: 8.8, score: 95, badge: "Champion" },
  { id: 8, name: "Tom Anderson", role: "Account Manager", dept: "Sales", platforms: ["linkedin"], posts: 12, reach: 8900, engagement: 5.4, score: 58, badge: "New" },
  { id: 9, name: "Rachel Green", role: "HR Specialist", dept: "HR", platforms: ["linkedin", "facebook"], posts: 6, reach: 3400, engagement: 3.8, score: 42, badge: "New" },
  { id: 10, name: "Alex Turner", role: "Growth Lead", dept: "Marketing", platforms: ["linkedin", "twitter", "facebook"], posts: 26, reach: 41000, engagement: 8.0, score: 89, badge: "Champion" },
];

const PLATFORM_ICONS: Record<string, typeof Linkedin> = { linkedin: Linkedin, twitter: Twitter, instagram: Instagram, facebook: Facebook };

const CONTENT_LIBRARY = [
  { id: 1, title: "Q3 Product Launch Announcement", excerpt: "We're thrilled to announce our new AI-powered coffee recommendation engine...", platform: "linkedin", category: "Product Update", shares: 42, reach: 12000, image: "🚀" },
  { id: 2, title: "Company Culture: Remote First", excerpt: "Why we chose remote-first and how it's transformed our team...", platform: "linkedin", category: "Culture", shares: 38, reach: 9500, image: "🏠" },
  { id: 3, title: "Industry Report: Coffee Trends 2026", excerpt: "Our analysis of the top 10 coffee trends shaping the industry this year...", platform: "twitter", category: "Industry Insight", shares: 56, reach: 18000, image: "📊" },
  { id: 4, title: "Customer Success Story", excerpt: "How BeanThere Cafe used PRACHAR to 3x their social engagement...", platform: "facebook", category: "Company News", shares: 31, reach: 7800, image: "⭐" },
  { id: 5, title: "Sustainability Initiative Update", excerpt: "Our journey to 100% compostable packaging and what's next...", platform: "instagram", category: "Company News", shares: 47, reach: 15000, image: "🌱" },
  { id: 6, title: "Upcoming Webinar: AI in Advertising", excerpt: "Join us for a deep dive into how AI is transforming ad creative...", platform: "linkedin", category: "Event", shares: 29, reach: 6500, image: "📅" },
  { id: 7, title: "Blog Post: The Science of Cold Brew", excerpt: "Everything you need to know about the cold brew process...", platform: "twitter", category: "Blog Post", shares: 35, reach: 8200, image: "☕" },
  { id: 8, title: "Team Spotlight: Engineering Team", excerpt: "Meet the engineers building PRACHAR's AI platform...", platform: "linkedin", category: "Culture", shares: 22, reach: 5400, image: "👨‍💻" },
];

const CAMPAIGNS = [
  { id: 1, name: "Product Launch Advocacy", goal: "Drive awareness for AI engine", participants: 8, shares: 142, reach: 89000, progress: 72 },
  { id: 2, name: "Recruitment Boost", goal: "Attract engineering talent", participants: 5, shares: 67, reach: 34000, progress: 45 },
  { id: 3, name: "Brand Awareness Q3", goal: "Increase LinkedIn presence", participants: 12, shares: 198, reach: 125000, progress: 88 },
];

const REACH_TREND = Array.from({ length: 90 }, (_, i) => ({ day: i + 1, reach: 500 + i * 50 + Math.sin(i / 7) * 300 }));

const PLATFORM_ENGAGEMENT = [
  { platform: "LinkedIn", engagement: 8.2 },
  { platform: "Twitter", engagement: 6.5 },
  { platform: "Instagram", engagement: 7.8 },
  { platform: "Facebook", engagement: 4.2 },
];

const DEPT_PARTICIPATION = [
  { dept: "Marketing", pct: 92 },
  { dept: "Sales", pct: 78 },
  { dept: "Design", pct: 65 },
  { dept: "Engineering", pct: 28 },
  { dept: "HR", pct: 35 },
  { dept: "Finance", pct: 15 },
];

const BADGE_STYLES: Record<string, string> = {
  Champion: "badge-accent", Active: "badge-success", New: "badge-info", Inactive: "badge-neutral",
};

export default function AdvocacyPage() {
  const [filterDept, setFilterDept] = useState("all");
  const [filterActivity, setFilterActivity] = useState("all");

  const filtered = ADVOCATES.filter(a => {
    if (filterDept !== "all" && a.dept !== filterDept) return false;
    if (filterActivity !== "all" && a.badge !== filterActivity) return false;
    return true;
  });

  const sorted = [...ADVOCATES].sort((a, b) => b.score - a.score);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Employee Advocacy</h1>
          <p className="text-sm text-text-secondary mt-1">Turn your team into brand ambassadors</p>
        </div>
        <button className="btn-primary text-sm"><Plus className="w-4 h-4" />Create Campaign</button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Active Advocates" value={8} delta={3} icon={<Users className="w-4 h-4" />} accent="info" />
        <Metric label="Posts Shared" value={178} delta={24} icon={<Share2 className="w-4 h-4" />} accent="accent" />
        <Metric label="Total Reach" value={248000} format="compact" delta={32} icon={<TrendingUp className="w-4 h-4" />} accent="success" />
        <Metric label="Earned Media Value" value={42000} format="compact" prefix="$" delta={18} icon={<DollarSign className="w-4 h-4" />} accent="accent" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Advocates */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <SectionHeader title="Advocate Directory" subtitle={`${filtered.length} employees`} icon={<Users className="w-4 h-4" />} />
              <div className="flex gap-2">
                <select value={filterDept} onChange={(e) => setFilterDept(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Depts</option>
                  {["Sales", "Marketing", "Design", "Engineering", "HR", "Finance"].map(d => <option key={d}>{d}</option>)}
                </select>
                <select value={filterActivity} onChange={(e) => setFilterActivity(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Levels</option>
                  {["Champion", "Active", "New", "Inactive"].map(b => <option key={b}>{b}</option>)}
                </select>
              </div>
            </div>
            <div className="space-y-2">
              {filtered.map((a, i) => (
                <motion.div key={a.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-info flex items-center justify-center text-sm font-bold text-bg shrink-0">{a.name[0]}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-text">{a.name}</span>
                      <span className={cn("badge text-[8px]", BADGE_STYLES[a.badge])}>{a.badge}</span>
                    </div>
                    <div className="text-xs text-text-muted">{a.role} · {a.dept}</div>
                  </div>
                  <div className="flex gap-1">{a.platforms.map(p => { const Icon = PLATFORM_ICONS[p]; return Icon ? <Icon key={p} className="w-3 h-3 text-text-muted" /> : null; })}</div>
                  <div className="hidden md:grid grid-cols-4 gap-3 text-center">
                    <div><div className="font-mono text-xs text-text">{a.posts}</div><div className="text-[8px] text-text-muted">posts</div></div>
                    <div><div className="font-mono text-xs text-text">{(a.reach / 1000).toFixed(0)}K</div><div className="text-[8px] text-text-muted">reach</div></div>
                    <div><div className="font-mono text-xs text-success">{a.engagement}%</div><div className="text-[8px] text-text-muted">eng</div></div>
                    <div><div className="font-mono text-xs text-accent">{a.score}</div><div className="text-[8px] text-text-muted">score</div></div>
                  </div>
                  <div className="flex gap-1">
                    <button className="p-1.5 rounded hover:bg-white/[0.06] text-text-muted hover:text-accent transition-all" title="Message"><MessageSquare className="w-3.5 h-3.5" /></button>
                    <button className="p-1.5 rounded hover:bg-white/[0.06] text-text-muted hover:text-info transition-all" title="Invite"><Send className="w-3.5 h-3.5" /></button>
                  </div>
                </motion.div>
              ))}
            </div>
          </Card>

          {/* Content Library */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <SectionHeader title="Content Library" subtitle="Pre-approved for sharing" icon={<BookOpen className="w-4 h-4" />} />
              <button className="btn-secondary text-xs"><Wand2 className="w-3 h-3 inline mr-1" />AI Generate</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {CONTENT_LIBRARY.map((c, i) => (
                <motion.div key={c.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all">
                  <div className="flex items-start gap-3">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-accent/10 to-info/10 flex items-center justify-center text-2xl shrink-0">{c.image}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge badge-neutral text-[8px]">{c.category}</span>
                      </div>
                      <h4 className="text-xs font-medium text-text mb-1 truncate">{c.title}</h4>
                      <p className="text-[10px] text-text-muted line-clamp-2 mb-2">{c.excerpt}</p>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-text-muted">{c.shares} shares · {(c.reach / 1000).toFixed(0)}K reach</span>
                        <button className="btn-secondary text-[10px] px-2 py-1"><Share2 className="w-2.5 h-2.5 inline mr-1" />Share</button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Leaderboard */}
          <Card>
            <SectionHeader title="Leaderboard" subtitle="Top advocates" icon={<Trophy className="w-4 h-4" />} />
            <div className="space-y-2">
              {sorted.slice(0, 5).map((a, i) => (
                <div key={a.id} className={cn("flex items-center gap-3 p-2 rounded-lg", i < 3 ? "bg-white/[0.04] border border-white/[0.06]" : "bg-white/[0.02]")}>
                  <div className={cn("w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0", i === 0 ? "bg-accent text-bg" : i === 1 ? "bg-text-muted text-bg" : i === 2 ? "bg-orange-700 text-white" : "bg-white/[0.06] text-text-muted")}>
                    {i === 0 ? <Crown className="w-3.5 h-3.5" /> : i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-text truncate">{a.name}</div>
                    <div className="text-[10px] text-text-muted">{a.posts} posts · {(a.reach / 1000).toFixed(0)}K reach</div>
                  </div>
                  <span className="font-mono text-xs text-accent">{a.score}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Campaigns */}
          <Card>
            <SectionHeader title="Active Campaigns" icon={<Target className="w-4 h-4" />} />
            <div className="space-y-3">
              {CAMPAIGNS.map(c => (
                <div key={c.id} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="text-sm font-medium text-text mb-1">{c.name}</div>
                  <div className="text-[10px] text-text-muted mb-2">{c.goal}</div>
                  <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                    <div><div className="font-mono text-text">{c.participants}</div><div className="text-[8px] text-text-muted">advocates</div></div>
                    <div><div className="font-mono text-text">{c.shares}</div><div className="text-[8px] text-text-muted">shares</div></div>
                    <div><div className="font-mono text-text">{(c.reach / 1000).toFixed(0)}K</div><div className="text-[8px] text-text-muted">reach</div></div>
                  </div>
                  <ProgressBar value={c.progress} accent="accent" />
                </div>
              ))}
            </div>
          </Card>

          {/* Analytics */}
          <Card>
            <SectionHeader title="Reach Trend" subtitle="90 days" icon={<TrendingUp className="w-4 h-4" />} />
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={REACH_TREND}>
                  <defs><linearGradient id="advReach" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FFD400" stopOpacity={0.4} /><stop offset="100%" stopColor="#FFD400" stopOpacity={0} /></linearGradient></defs>
                  <XAxis dataKey="day" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                  <Area type="monotone" dataKey="reach" stroke="#FFD400" strokeWidth={2} fill="url(#advReach)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <SectionHeader title="Engagement by Platform" />
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={PLATFORM_ENGAGEMENT}>
                  <XAxis dataKey="platform" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="engagement" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <SectionHeader title="Department Participation" />
            <div className="space-y-2">
              {DEPT_PARTICIPATION.map(d => (
                <div key={d.dept} className="flex items-center gap-2">
                  <span className="text-xs text-text-secondary w-20">{d.dept}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-white/[0.04]"><div className="h-full rounded-full bg-gradient-to-r from-info to-accent" style={{ width: `${d.pct}%` }} /></div>
                  <span className="font-mono text-[10px] text-text w-8 text-right">{d.pct}%</span>
                </div>
              ))}
            </div>
          </Card>

          {/* AI Insights */}
          <div className="space-y-2">
            <AIRecommendation title="Department Gap" reasoning="Engineering team has 5x lower participation than Sales. Consider creating targeted technical content to boost engagement." />
            <AIRecommendation title="Optimal Share Time" reasoning="Tuesday 10am is the optimal share time for your audience. Schedule content accordingly for maximum reach." />
          </div>
        </div>
      </div>
    </div>
  );
}
