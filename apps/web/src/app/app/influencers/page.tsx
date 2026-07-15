"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { Sparkline, ProgressBar } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Search, Wand2, Users, TrendingUp, DollarSign, Target,
  Instagram, Youtube, Twitter, Plus, Check, Star, MapPin,
  Sparkles, ArrowRight, Filter, Briefcase, Award,
} from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

const CREATORS = [
  { id: 1, name: "Coffee Queen", handle: "@coffeequeen", platforms: ["instagram", "tiktok"], followers: 245000, engagement: 6.8, price: 1200, location: "Los Angeles", niches: ["Coffee", "Lifestyle"], rating: 4.9, aiMatch: 95 },
  { id: 2, name: "Brew Master Mike", handle: "@brewmaster", platforms: ["youtube", "instagram"], followers: 580000, engagement: 4.2, price: 2800, location: "New York", niches: ["Coffee", "Education"], rating: 4.7, aiMatch: 88 },
  { id: 3, name: "Latte Artist Lisa", handle: "@latteart_lisa", platforms: ["instagram"], followers: 89000, engagement: 8.5, price: 600, location: "Seattle", niches: ["Coffee", "Art"], rating: 5.0, aiMatch: 92 },
  { id: 4, name: "Sustainable Sue", handle: "@sustainable_sue", platforms: ["instagram", "youtube"], followers: 320000, engagement: 5.4, price: 1500, location: "Portland", niches: ["Sustainability", "Coffee"], rating: 4.8, aiMatch: 90 },
  { id: 5, name: "Daily Grind Dan", handle: "@dailygrind", platforms: ["tiktok", "youtube"], followers: 1200000, engagement: 3.8, price: 4500, location: "Austin", niches: ["Coffee", "Comedy"], rating: 4.6, aiMatch: 78 },
  { id: 6, name: "Morning Brew Mia", handle: "@morningbrew", platforms: ["instagram", "tiktok"], followers: 156000, engagement: 7.2, price: 900, location: "Miami", niches: ["Coffee", "Wellness"], rating: 4.9, aiMatch: 94 },
  { id: 7, name: "Espresso Ed", handle: "@espresso_ed", platforms: ["youtube"], followers: 410000, engagement: 5.1, price: 2000, location: "Chicago", niches: ["Coffee", "Tech"], rating: 4.7, aiMatch: 82 },
  { id: 8, name: "Cafe Culture", handle: "@cafeculture", platforms: ["instagram", "twitter"], followers: 220000, engagement: 6.0, price: 1100, location: "San Francisco", niches: ["Coffee", "Culture"], rating: 4.8, aiMatch: 87 },
];

const PLATFORM_ICONS: Record<string, typeof Instagram> = { instagram: Instagram, tiktok: Star, youtube: Youtube, twitter: Twitter };

const CAMPAIGNS = [
  { id: 1, name: "Summer Cold Brew Launch", status: "active", budget: 25000, creators: 6, reach: "1.2M", engagement: 8.4, roas: 4.2, progress: 65 },
  { id: 2, name: "Sustainability Story", status: "active", budget: 12000, creators: 3, reach: "450K", engagement: 6.8, roas: 3.1, progress: 40 },
  { id: 3, name: "Holiday Gift Guide", status: "pending", budget: 35000, creators: 10, reach: "—", engagement: 0, roas: 0, progress: 15 },
  { id: 4, name: "Brand Awareness Q1", status: "completed", budget: 18000, creators: 5, reach: "890K", engagement: 7.2, roas: 3.8, progress: 100 },
];

const PIPELINE = [
  { stage: "Discovered", creators: [{ name: "Coffee Queen", platform: "instagram", followers: 245000, price: 1200 }, { name: "Latte Artist Lisa", platform: "instagram", followers: 89000, price: 600 }] },
  { stage: "Invited", creators: [{ name: "Morning Brew Mia", platform: "tiktok", followers: 156000, price: 900 }] },
  { stage: "Negotiating", creators: [{ name: "Sustainable Sue", platform: "youtube", followers: 320000, price: 1500 }, { name: "Cafe Culture", platform: "instagram", followers: 220000, price: 1100 }] },
  { stage: "Contracted", creators: [{ name: "Brew Master Mike", platform: "youtube", followers: 580000, price: 2800 }] },
  { stage: "Content Review", creators: [] },
  { stage: "Published", creators: [{ name: "Daily Grind Dan", platform: "tiktok", followers: 1200000, price: 4500 }] },
  { stage: "Completed", creators: [] },
];

const REACH_DATA = CREATORS.slice(0, 6).map(c => ({ name: c.handle.slice(1, 11), reach: c.followers }));
const ENGAGEMENT_DATA = Array.from({ length: 14 }, (_, i) => ({ day: i + 1, engagement: 5 + Math.sin(i / 3) * 2 + Math.random() }));

export default function InfluencersPage() {
  const [showBuilder, setShowBuilder] = useState(false);
  const [search, setSearch] = useState("");
  const [filterNiche, setFilterNiche] = useState("all");

  const filteredCreators = CREATORS.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase()) && !c.handle.includes(search.toLowerCase())) return false;
    if (filterNiche !== "all" && !c.niches.includes(filterNiche)) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Influencer Marketing</h1>
          <p className="text-sm text-text-secondary mt-1">Discover, manage, and measure creator campaigns</p>
        </div>
        <button onClick={() => setShowBuilder(!showBuilder)} className="btn-primary text-sm"><Plus className="w-4 h-4" />New Campaign</button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Active Campaigns" value={2} delta={1} icon={<Briefcase className="w-4 h-4" />} accent="info" />
        <Metric label="Total Reach" value={1650000} format="compact" delta={28} icon={<Users className="w-4 h-4" />} accent="accent" />
        <Metric label="Avg Engagement" value={7.6} suffix="%" delta={1.2} icon={<TrendingUp className="w-4 h-4" />} accent="success" />
        <Metric label="ROAS" value={3.9} suffix="x" delta={0.4} icon={<DollarSign className="w-4 h-4" />} accent="accent" />
      </div>

      {/* Creator Discovery */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <SectionHeader title="Creator Discovery" subtitle={`${filteredCreators.length} creators`} icon={<Search className="w-4 h-4" />} />
          <div className="flex gap-2">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search creators..." className="input-field text-xs py-1.5 w-40" />
            <select value={filterNiche} onChange={(e) => setFilterNiche(e.target.value)} className="input-field text-xs py-1.5 w-28">
              <option value="all">All Niches</option>
              {["Coffee", "Lifestyle", "Sustainability", "Wellness", "Education", "Art", "Comedy", "Tech", "Culture"].map(n => <option key={n}>{n}</option>)}
            </select>
            <button className="btn-secondary text-xs"><Wand2 className="w-3 h-3 inline mr-1" />AI Match</button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {filteredCreators.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card3D className="text-center">
                <div className="relative inline-block mb-3">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-accent to-info flex items-center justify-center text-xl font-bold text-bg">{c.name[0]}</div>
                  <span className="absolute -top-1 -right-1 badge badge-accent text-[8px] px-1.5 py-0.5">{c.aiMatch}%</span>
                </div>
                <h3 className="font-display text-sm font-medium text-text">{c.name}</h3>
                <p className="text-xs text-text-muted mb-2">{c.handle}</p>
                <div className="flex justify-center gap-1.5 mb-2">
                  {c.platforms.map(p => { const Icon = PLATFORM_ICONS[p] || Star; return <Icon key={p} className="w-3 h-3 text-text-muted" />; })}
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs mb-3">
                  <div><div className="font-mono text-text">{(c.followers / 1000).toFixed(0)}K</div><div className="text-[9px] text-text-muted">followers</div></div>
                  <div><div className="font-mono text-success">{c.engagement}%</div><div className="text-[9px] text-text-muted">engagement</div></div>
                </div>
                <div className="flex items-center justify-center gap-1 mb-2">
                  <Star className="w-3 h-3 text-accent fill-accent" /><span className="text-xs text-text">{c.rating}</span>
                  <span className="text-[10px] text-text-muted ml-2"><MapPin className="w-2.5 h-2.5 inline" />{c.location}</span>
                </div>
                <div className="flex flex-wrap justify-center gap-1 mb-3">
                  {c.niches.map(n => <span key={n} className="badge badge-neutral text-[8px]">{n}</span>)}
                </div>
                <div className="text-xs text-text-secondary mb-2">~${c.price}/post</div>
                <button className="btn-secondary text-xs w-full">Invite to Campaign</button>
              </Card3D>
            </motion.div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Campaigns */}
        <Card>
          <SectionHeader title="Active Campaigns" subtitle={`${CAMPAIGNS.length} campaigns`} icon={<Briefcase className="w-4 h-4" />} />
          <div className="space-y-3">
            {CAMPAIGNS.map(c => (
              <div key={c.id} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-text">{c.name}</span>
                  <span className={cn("badge text-[9px]", c.status === "active" ? "badge-success" : c.status === "pending" ? "badge-warning" : "badge-neutral")}>{c.status}</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs mb-2">
                  <div><div className="text-text-muted text-[9px]">Budget</div><div className="font-mono text-text">${(c.budget / 1000).toFixed(0)}K</div></div>
                  <div><div className="text-text-muted text-[9px]">Creators</div><div className="font-mono text-text">{c.creators}</div></div>
                  <div><div className="text-text-muted text-[9px]">Reach</div><div className="font-mono text-text">{c.reach}</div></div>
                  <div><div className="text-text-muted text-[9px]">ROAS</div><div className="font-mono text-success">{c.roas}x</div></div>
                </div>
                <ProgressBar value={c.progress} accent={c.status === "active" ? "success" : c.status === "pending" ? "warning" : "accent"} />
              </div>
            ))}
          </div>
        </Card>

        {/* Performance Analytics */}
        <Card>
          <SectionHeader title="Performance Analytics" icon={<TrendingUp className="w-4 h-4" />} />
          <div className="space-y-4">
            <div>
              <div className="text-xs text-text-secondary mb-2">Reach by Creator</div>
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={REACH_DATA}>
                    <XAxis dataKey="name" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                    <Bar dataKey="reach" fill="#FFD400" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <div className="text-xs text-text-secondary mb-2">Engagement Over Campaign</div>
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={ENGAGEMENT_DATA}>
                    <XAxis dataKey="day" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                    <Line type="monotone" dataKey="engagement" stroke="#22C55E" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Creator Pipeline */}
      <Card>
        <SectionHeader title="Creator Pipeline" subtitle="Kanban board" icon={<Users className="w-4 h-4" />} />
        <div className="flex gap-3 overflow-x-auto pb-2">
          {PIPELINE.map(col => (
            <div key={col.stage} className="shrink-0 w-52">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-text">{col.stage}</span>
                <span className="badge badge-neutral text-[9px]">{col.creators.length}</span>
              </div>
              <div className="space-y-2 min-h-[80px] p-2 rounded-lg bg-white/[0.01] border border-white/[0.04]">
                {col.creators.map(c => {
                  const Icon = PLATFORM_ICONS[c.platform] || Star;
                  return (
                    <motion.div key={c.name} drag whileDrag={{ scale: 1.05 }} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] cursor-grab active:cursor-grabbing">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-3 h-3 text-text-muted" />
                        <span className="text-xs text-text truncate">{c.name}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-text-muted">
                        <span>{(c.followers / 1000).toFixed(0)}K</span>
                        <span className="text-accent">${c.price}</span>
                      </div>
                    </motion.div>
                  );
                })}
                {col.creators.length === 0 && <div className="text-[10px] text-text-muted text-center py-4">Drop here</div>}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* AI Insights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <AIRecommendation title="Top Creator Opportunity" reasoning="@coffeequeen has 3.2x higher engagement than your campaign average. Consider increasing budget allocation to her content." />
        <AIRecommendation title="Content Format Insight" reasoning="Reels content outperforms static posts by 4.1x in your campaigns. Shift deliverable mix toward short-form video." />
      </div>
    </div>
  );
}
