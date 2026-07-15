"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { Sparkline } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Radio, MessageCircle, TrendingUp, TrendingDown, Minus, Filter,
  Bell, Flag, Archive, UserPlus, Reply, Twitter, MessageSquare,
  Globe, Newspaper, Hash, ThumbsUp, ThumbsDown, AlertTriangle,
} from "lucide-react";
import { AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

type Sentiment = "positive" | "negative" | "neutral";
const SENTIMENT_COLOR: Record<Sentiment, string> = { positive: "#22C55E", negative: "#EF4444", neutral: "#94A3B8" };
const SENTIMENT_ICON: Record<Sentiment, typeof ThumbsUp> = { positive: ThumbsUp, negative: ThumbsDown, neutral: Minus };

const SOURCES = [
  { id: "twitter", label: "Twitter/X", icon: Twitter, color: "#1DA1F2" },
  { id: "reddit", label: "Reddit", icon: MessageSquare, color: "#FF4500" },
  { id: "news", label: "News", icon: Newspaper, color: "#94A3B8" },
  { id: "blog", label: "Blogs", icon: Globe, color: "#3B82F6" },
  { id: "forum", label: "Forums", icon: Hash, color: "#A855F7" },
  { id: "review", label: "Reviews", icon: Star, color: "#FFD400" },
];

const MENTIONS = [
  { id: 1, source: "twitter", author: "@coffee_lover_92", content: "Just tried @pracharcoffee's new cold brew and it's absolutely incredible. Best coffee I've had this year!", sentiment: "positive" as Sentiment, time: "2m ago", engagement: 142, lang: "EN" },
  { id: 2, source: "reddit", author: "u/brewmaster_42", content: "Anyone else think the new Prachar blend is overpriced? $7 for a small bag seems steep compared to competitors.", sentiment: "negative" as Sentiment, time: "15m ago", engagement: 89, lang: "EN" },
  { id: 3, source: "news", author: "Coffee Weekly", content: "Prachar Coffee named 'Most Innovative Brand 2026' by Industry Awards committee", sentiment: "positive" as Sentiment, time: "1h ago", engagement: 1240, lang: "EN" },
  { id: 4, source: "twitter", author: "@marketing_pro", content: "Prachar's marketing campaign is genius. The AI-generated content feels so authentic.", sentiment: "positive" as Sentiment, time: "2h ago", engagement: 567, lang: "EN" },
  { id: 5, source: "review", author: "Sarah M.", content: "Shipping took 2 weeks. Product is good but the wait was frustrating. Customer service was slow to respond.", sentiment: "negative" as Sentiment, time: "3h ago", engagement: 34, lang: "EN" },
  { id: 6, source: "blog", author: "The Daily Grind", content: "Prachar Coffee's sustainability initiatives set a new standard for the industry", sentiment: "positive" as Sentiment, time: "5h ago", engagement: 234, lang: "EN" },
  { id: 7, source: "forum", author: "CoffeeGeek42", content: "Has anyone compared Prachar's espresso beans to Blue Bottle? Looking for recommendations.", sentiment: "neutral" as Sentiment, time: "6h ago", engagement: 67, lang: "EN" },
  { id: 8, source: "twitter", author: "@sustainable_sue", content: "Love that Prachar uses 100% compostable packaging. This is the future of coffee brands.", sentiment: "positive" as Sentiment, time: "8h ago", engagement: 890, lang: "EN" },
  { id: 9, source: "reddit", author: "u/frustrated_customer", content: "Third time my order arrived damaged. Packaging quality has really gone downhill.", sentiment: "negative" as Sentiment, time: "10h ago", engagement: 156, lang: "EN" },
  { id: 10, source: "news", author: "TechCrunch", content: "Prachar raises $15M Series A to expand AI-powered advertising platform", sentiment: "positive" as Sentiment, time: "12h ago", engagement: 3400, lang: "EN" },
  { id: 11, source: "blog", author: "Coffee Trends 2026", content: "Prachar's cold brew is trending among Gen Z consumers, with 300% YoY growth", sentiment: "positive" as Sentiment, time: "14h ago", engagement: 412, lang: "EN" },
  { id: 12, source: "twitter", author: "@neutral_nancy", content: "Just ordered Prachar coffee for the first time. Will update once I try it.", sentiment: "neutral" as Sentiment, time: "16h ago", engagement: 12, lang: "EN" },
];

const SENTIMENT_TREND = Array.from({ length: 30 }, (_, i) => ({
  day: i + 1,
  positive: 60 + Math.sin(i / 3) * 15 + Math.random() * 10,
  negative: 20 + Math.cos(i / 4) * 8 + Math.random() * 5,
  neutral: 100 - 60 - Math.sin(i / 3) * 15 - 20 - Math.cos(i / 4) * 8,
}));

const SOV_DATA = [
  { name: "Prachar", value: 35, color: "#FFD400" },
  { name: "Blue Bottle", value: 22, color: "#3B82F6" },
  { name: "Stumptown", value: 18, color: "#22C55E" },
  { name: "La Colombe", value: 15, color: "#A855F7" },
  { name: "Others", value: 10, color: "#94A3B8" },
];

const COMPETITORS = [
  { name: "Prachar", mentions: 4200, sentiment: 78, reach: "2.1M", growth: 12, isYou: true },
  { name: "Blue Bottle", mentions: 3800, sentiment: 71, reach: "1.8M", growth: 5 },
  { name: "Stumptown", mentions: 2900, sentiment: 69, reach: "1.4M", growth: -3 },
  { name: "La Colombe", mentions: 2400, sentiment: 65, reach: "1.1M", growth: 8 },
  { name: "Intelligentsia", mentions: 1800, sentiment: 72, reach: "0.9M", growth: 2 },
];

const TRENDING = [
  { topic: "#ColdBrewSeason", volume: 12400, growth: 45, keywords: ["cold brew", "summer", "iced coffee"], ai: true },
  { topic: "#SustainableCoffee", volume: 8900, growth: 28, keywords: ["eco", "compostable", "green"], ai: true },
  { topic: "#CoffeeArt", volume: 6700, growth: 15, keywords: ["latte art", "barista", "design"], ai: false },
  { topic: "#HomeBrewing", volume: 5200, growth: 22, keywords: ["french press", "pour over", "v60"], ai: true },
  { topic: "#CoffeeSubscription", volume: 3100, growth: 8, keywords: ["delivery", "monthly", "fresh"], ai: false },
];

const POSITIVE_KEYWORDS = [
  { word: "delicious", size: 28, count: 340 },
  { word: "fresh", size: 24, count: 280 },
  { word: "sustainable", size: 22, count: 210 },
  { word: "innovative", size: 20, count: 180 },
  { word: "quality", size: 18, count: 165 },
  { word: "smooth", size: 16, count: 140 },
  { word: "authentic", size: 14, count: 110 },
  { word: "premium", size: 13, count: 95 },
];

const NEGATIVE_KEYWORDS = [
  { word: "expensive", size: 26, count: 220 },
  { word: "slow shipping", size: 22, count: 180 },
  { word: "packaging", size: 18, count: 130 },
  { word: "customer service", size: 16, count: 105 },
  { word: "small size", size: 14, count: 80 },
  { word: "bitter", size: 12, count: 60 },
];

function Star(props: any) { return <MessageSquare {...props} />; }

export default function ListeningPage() {
  const [filterSentiment, setFilterSentiment] = useState<Sentiment | "all">("all");
  const [filterSource, setFilterSource] = useState("all");
  const [alerts, setAlerts] = useState({ mention: true, sentimentDrop: true, competitor: false, trending: true, spike: true });
  const [sentimentThreshold, setSentimentThreshold] = useState(60);

  const filteredMentions = MENTIONS.filter(m => {
    if (filterSentiment !== "all" && m.sentiment !== filterSentiment) return false;
    if (filterSource !== "all" && m.source !== filterSource) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Social Listening</h1>
          <p className="text-sm text-text-secondary mt-1">Real-time brand intelligence across the web</p>
        </div>
        <span className="badge badge-success"><span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" /> Live</span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Mentions (24h)" value={342} delta={18} icon={<Radio className="w-4 h-4" />} accent="info" />
        <Metric label="Sentiment Score" value={72} suffix="%" delta={5} icon={<ThumbsUp className="w-4 h-4" />} accent="success" />
        <Metric label="Reach" value={2100000} format="compact" delta={22} icon={<TrendingUp className="w-4 h-4" />} accent="accent" />
        <Metric label="Share of Voice" value={35} suffix="%" delta={8} icon={<Radio className="w-4 h-4" />} accent="accent" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Mentions Stream */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <SectionHeader title="Mentions Stream" subtitle={`${filteredMentions.length} mentions`} icon={<MessageCircle className="w-4 h-4" />} />
              <div className="flex gap-2">
                <select value={filterSentiment} onChange={(e) => setFilterSentiment(e.target.value as any)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Sentiment</option>
                  <option value="positive">Positive</option>
                  <option value="negative">Negative</option>
                  <option value="neutral">Neutral</option>
                </select>
                <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Sources</option>
                  {SOURCES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            </div>
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {filteredMentions.map((m, i) => {
                const source = SOURCES.find(s => s.id === m.source)!;
                const SentIcon = SENTIMENT_ICON[m.sentiment];
                return (
                  <motion.div key={m.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${source.color}20` }}>
                        <source.icon className="w-4 h-4" style={{ color: source.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-text">{m.author}</span>
                          <span className="text-[10px] text-text-muted">· {m.time}</span>
                          <span className="badge badge-neutral text-[9px] ml-auto">{m.lang}</span>
                        </div>
                        <p className="text-xs text-text-secondary leading-relaxed mb-2">{m.content}</p>
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1 text-[10px]" style={{ color: SENTIMENT_COLOR[m.sentiment] }}>
                            <SentIcon className="w-3 h-3" /> {m.sentiment}
                          </span>
                          <span className="text-[10px] text-text-muted">{m.engagement} engagement</span>
                          <div className="flex gap-1 ml-auto">
                            <button className="p-1 rounded hover:bg-white/[0.06] text-text-muted hover:text-accent transition-all" title="Reply"><Reply className="w-3 h-3" /></button>
                            <button className="p-1 rounded hover:bg-white/[0.06] text-text-muted hover:text-warning transition-all" title="Flag"><Flag className="w-3 h-3" /></button>
                            <button className="p-1 rounded hover:bg-white/[0.06] text-text-muted hover:text-info transition-all" title="Assign"><UserPlus className="w-3 h-3" /></button>
                            <button className="p-1 rounded hover:bg-white/[0.06] text-text-muted hover:text-danger transition-all" title="Archive"><Archive className="w-3 h-3" /></button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>

          {/* Sentiment Analysis */}
          <Card>
            <SectionHeader title="Sentiment Analysis" subtitle="30-day trend" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="flex flex-col items-center">
                <div className="text-xs text-text-secondary mb-2">Overall Positive</div>
                <div className="relative w-24 h-24">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={[{ value: 72 }, { value: 28 }]} dataKey="value" innerRadius={32} outerRadius={44} startAngle={90} endAngle={-270} paddingAngle={2}>
                        <Cell fill="#22C55E" />
                        <Cell fill="#1F2937" />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="font-display text-xl font-bold text-success">72%</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col justify-center gap-2">
                <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><span className="w-2 h-2 rounded-full bg-success" /> Positive</span><span className="font-mono text-xs text-text">72%</span></div>
                <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><span className="w-2 h-2 rounded-full bg-danger" /> Negative</span><span className="font-mono text-xs text-text">18%</span></div>
                <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><span className="w-2 h-2 rounded-full bg-text-muted" /> Neutral</span><span className="font-mono text-xs text-text">10%</span></div>
              </div>
              <div className="flex flex-col justify-center gap-1.5">
                <div className="text-xs text-text-secondary mb-1">By Platform</div>
                {[{ p: "Twitter", v: 78 }, { p: "Reddit", v: 54 }, { p: "News", v: 91 }, { p: "Reviews", v: 62 }].map(s => (
                  <div key={s.p} className="flex items-center gap-2">
                    <span className="text-[10px] text-text-muted w-12">{s.p}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-white/[0.04]"><div className="h-full rounded-full bg-gradient-to-r from-success to-accent" style={{ width: `${s.v}%` }} /></div>
                    <span className="font-mono text-[10px] text-text w-8 text-right">{s.v}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={SENTIMENT_TREND}>
                  <defs>
                    <linearGradient id="gPos" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#22C55E" stopOpacity={0.4} /><stop offset="100%" stopColor="#22C55E" stopOpacity={0} /></linearGradient>
                    <linearGradient id="gNeg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#EF4444" stopOpacity={0.3} /><stop offset="100%" stopColor="#EF4444" stopOpacity={0} /></linearGradient>
                    <linearGradient id="gNeu" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#94A3B8" stopOpacity={0.2} /><stop offset="100%" stopColor="#94A3B8" stopOpacity={0} /></linearGradient>
                  </defs>
                  <XAxis dataKey="day" tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                  <Area type="monotone" dataKey="positive" stroke="#22C55E" strokeWidth={2} fill="url(#gPos)" />
                  <Area type="monotone" dataKey="negative" stroke="#EF4444" strokeWidth={2} fill="url(#gNeg)" />
                  <Area type="monotone" dataKey="neutral" stroke="#94A3B8" strokeWidth={1.5} fill="url(#gNeu)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            {/* Word clouds */}
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <div className="text-xs text-success mb-2 flex items-center gap-1"><ThumbsUp className="w-3 h-3" /> Positive Keywords</div>
                <div className="flex flex-wrap gap-2">
                  {POSITIVE_KEYWORDS.map(k => <span key={k.word} className="text-success/80 hover:text-success cursor-pointer transition-all" style={{ fontSize: k.size }}>{k.word}</span>)}
                </div>
              </div>
              <div>
                <div className="text-xs text-danger mb-2 flex items-center gap-1"><ThumbsDown className="w-3 h-3" /> Negative Keywords</div>
                <div className="flex flex-wrap gap-2">
                  {NEGATIVE_KEYWORDS.map(k => <span key={k.word} className="text-danger/80 hover:text-danger cursor-pointer transition-all" style={{ fontSize: k.size }}>{k.word}</span>)}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Share of Voice */}
          <Card>
            <SectionHeader title="Share of Voice" subtitle="You vs competitors" />
            <div className="h-40 mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={SOV_DATA} dataKey="value" innerRadius={40} outerRadius={70} paddingAngle={2}>
                    {SOV_DATA.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2">
              {COMPETITORS.map(c => (
                <div key={c.name} className={cn("flex items-center justify-between p-2 rounded-lg", c.isYou ? "bg-accent/5 border border-accent/10" : "bg-white/[0.02]")}>
                  <div className="flex items-center gap-2">
                    <span className={cn("text-xs", c.isYou ? "text-accent font-medium" : "text-text")}>{c.name}</span>
                    {c.isYou && <span className="badge badge-accent text-[8px]">You</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <Sparkline data={[20, 25, 22, 30, 28, 35]} width={40} height={16} color={c.isYou ? "#FFD400" : "#94A3B8"} />
                    <span className={cn("text-[10px] flex items-center gap-0.5", c.growth > 0 ? "text-success" : "text-danger")}>
                      {c.growth > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{Math.abs(c.growth)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Trending Topics */}
          <Card>
            <SectionHeader title="Trending Topics" subtitle="In your industry" icon={<Hash className="w-4 h-4" />} />
            <div className="space-y-2">
              {TRENDING.map(t => (
                <div key={t.topic} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-text">{t.topic}</span>
                    {t.ai && <span className="badge badge-accent text-[8px]">AI Opportunity</span>}
                  </div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-[10px] text-text-muted">{t.volume.toLocaleString()} mentions</span>
                    <span className="text-[10px] text-success flex items-center gap-0.5"><TrendingUp className="w-2.5 h-2.5" />{t.growth}%</span>
                    <Sparkline data={Array.from({ length: 7 }, () => Math.random() * 100)} width={50} height={14} color="#FFD400" />
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {t.keywords.map(k => <span key={k} className="text-[9px] text-text-muted px-1.5 py-0.5 rounded bg-white/[0.03]">{k}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Alert Config */}
          <Card>
            <SectionHeader title="Alert Configuration" icon={<Bell className="w-4 h-4" />} />
            <div className="space-y-3">
              {(Object.keys(alerts) as (keyof typeof alerts)[]).map(key => {
                const labels: Record<string, string> = { mention: "Mention alerts", sentimentDrop: "Sentiment drop alerts", competitor: "Competitor mention alerts", trending: "Trending topic alerts", spike: "Spike alerts" };
                return (
                  <label key={key} className="flex items-center justify-between cursor-pointer">
                    <span className="text-xs text-text-secondary">{labels[key]}</span>
                    <button onClick={() => setAlerts(a => ({ ...a, [key]: !a[key] }))} className={cn("w-9 h-5 rounded-full transition-all relative", alerts[key] ? "bg-accent" : "bg-white/[0.08]")}>
                      <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all", alerts[key] ? "left-4.5" : "left-0.5")} style={{ left: alerts[key] ? "18px" : "2px" }} />
                    </button>
                  </label>
                );
              })}
              <div>
                <label className="label-field block mb-1.5">Sentiment drop threshold: {sentimentThreshold}%</label>
                <input type="range" min={30} max={90} value={sentimentThreshold} onChange={(e) => setSentimentThreshold(Number(e.target.value))} className="w-full accent-accent" />
              </div>
            </div>
          </Card>

          {/* AI Insights */}
          <div className="space-y-2">
            <AIRecommendation
              title="Sentiment Drop on Reddit"
              reasoning="Sentiment dropped 15% on r/coffee — a negative thread about pricing is gaining traction. Consider a response strategy or promotional offer."
             
            />
            <AIRecommendation
              title="Competitor Surge"
              reasoning="Blue Bottle mentioned 3x more this week due to their new product launch. Consider counter-campaign or content push."
             
            />
            <AIRecommendation
              title="Trending Opportunity"
              reasoning="#ColdBrewSeason is trending with 45% growth. Your cold brew content could capture significant share of voice."
             
            />
          </div>
        </div>
      </div>
    </div>
  );
}
