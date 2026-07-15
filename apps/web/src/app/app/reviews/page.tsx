"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { Sparkline } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Star, Filter, Search, MessageSquare, Send, Wand2, Check,
  Clock, TrendingUp, TrendingDown, Plus, ThumbsUp, ThumbsDown,
  AlertTriangle, Sparkles, Edit3, Copy,
} from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const PLATFORMS = [
  { id: "google", label: "Google Business", color: "#4285F4", avg: 4.6, total: 1240, trend: 0.3, connected: true },
  { id: "yelp", label: "Yelp", color: "#D32323", avg: 4.1, total: 380, trend: -0.1, connected: true },
  { id: "trustpilot", label: "Trustpilot", color: "#00B67A", avg: 4.5, total: 890, trend: 0.2, connected: true },
  { id: "g2", label: "G2", color: "#FF492C", avg: 4.7, total: 156, trend: 0.4, connected: false },
  { id: "capterra", label: "Capterra", color: "#FF9D28", avg: 4.4, total: 92, trend: 0.1, connected: false },
  { id: "producthunt", label: "ProductHunt", color: "#DA552F", avg: 4.8, total: 340, trend: 0.5, connected: true },
  { id: "amazon", label: "Amazon", color: "#FF9900", avg: 4.3, total: 2100, trend: 0.1, connected: true },
  { id: "appstore", label: "App Store", color: "#0D96F6", avg: 4.5, total: 870, trend: 0.2, connected: false },
];

const REVIEWS = [
  { id: 1, platform: "google", reviewer: "Sarah M.", rating: 5, text: "Absolutely love Prachar coffee! The cold brew is smooth and the packaging is beautiful. Fast shipping too!", date: "2h ago", responded: true, sentiment: "positive" },
  { id: 2, platform: "yelp", reviewer: "Mike R.", rating: 2, text: "Coffee is decent but shipping took 2 weeks. Customer service was slow to respond. Expected better.", date: "5h ago", responded: false, sentiment: "negative" },
  { id: 3, platform: "trustpilot", reviewer: "Emma L.", rating: 5, text: "Best coffee subscription I've tried. The AI-recommended blends are always spot on. Highly recommend!", date: "8h ago", responded: true, sentiment: "positive" },
  { id: 4, platform: "amazon", reviewer: "James K.", rating: 4, text: "Great quality coffee beans. Would be 5 stars but the bag could be bigger for the price.", date: "12h ago", responded: false, sentiment: "neutral" },
  { id: 5, platform: "producthunt", reviewer: "Alex T.", rating: 5, text: "The AI advertising platform is revolutionary. Saved us 20 hours/week on content creation.", date: "1d ago", responded: true, sentiment: "positive" },
  { id: 6, platform: "google", reviewer: "Lisa B.", rating: 1, text: "Order arrived damaged. Third time this has happened. Packaging quality has really gone downhill.", date: "1d ago", responded: false, sentiment: "negative" },
  { id: 7, platform: "appstore", reviewer: "David W.", rating: 4, text: "Great app, love the voice assistant feature. Sometimes crashes on startup though.", date: "2d ago", responded: false, sentiment: "neutral" },
  { id: 8, platform: "trustpilot", reviewer: "Nina P.", rating: 5, text: "Sustainable packaging, ethical sourcing, AND amazing coffee? Prachar is doing everything right.", date: "2d ago", responded: true, sentiment: "positive" },
  { id: 9, platform: "yelp", reviewer: "Tom H.", rating: 3, text: "Coffee is good but a bit pricey compared to other specialty brands. Decent but not amazing value.", date: "3d ago", responded: false, sentiment: "neutral" },
  { id: 10, platform: "amazon", reviewer: "Rachel G.", rating: 5, text: "Been ordering for 6 months now. Consistent quality, always fresh. The subscription is worth every penny.", date: "3d ago", responded: true, sentiment: "positive" },
];

const RATING_DIST = [
  { rating: "5★", count: 4200, fill: "#22C55E" },
  { rating: "4★", count: 1800, fill: "#84CC16" },
  { rating: "3★", count: 600, fill: "#FFD400" },
  { rating: "2★", count: 280, fill: "#F97316" },
  { rating: "1★", count: 160, fill: "#EF4444" },
];

const RATING_TREND = Array.from({ length: 12 }, (_, i) => ({
  month: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][i],
  rating: +(4.2 + Math.sin(i / 3) * 0.2 + i * 0.02).toFixed(2),
}));

const POSITIVE_THEMES = [
  { theme: "Great product quality", count: 1240, trend: 12, sentiment: 92 },
  { theme: "Fast delivery", count: 890, trend: 8, sentiment: 88 },
  { theme: "Good value", count: 670, trend: 5, sentiment: 85 },
  { theme: "Sustainable packaging", count: 540, trend: 22, sentiment: 94 },
  { theme: "Excellent customer service", count: 420, trend: 3, sentiment: 90 },
];

const NEGATIVE_THEMES = [
  { theme: "Slow shipping", count: 180, trend: -15, sentiment: 28 },
  { theme: "Price too high", count: 145, trend: -8, sentiment: 35 },
  { theme: "Damaged packaging", count: 92, trend: -22, sentiment: 20 },
  { theme: "Missing features", count: 67, trend: -5, sentiment: 40 },
  { theme: "App crashes", count: 45, trend: -10, sentiment: 30 },
];

const TEMPLATES = [
  { stars: 5, title: "5-Star Thank You", body: "Thank you so much for the wonderful review! We're thrilled you love our coffee. As a thank you, here's 15% off your next order: THANKS15 ☕" },
  { stars: 4, title: "4-Star Appreciation", body: "Thanks for the great review and feedback! We're always improving — stay tuned for bigger bag sizes coming soon. Use code UPGRADE10 for 10% off!" },
  { stars: 3, title: "3-Star Response", body: "Thank you for your honest feedback. We're sorry we didn't fully meet expectations. We'd love to make it right — please reach out at hello@prachar.coffee" },
  { stars: 2, title: "2-Star Recovery", body: "We sincerely apologize for the experience. This isn't our standard. Please contact us at hello@prachar.coffee so we can resolve this immediately." },
  { stars: 1, title: "1-Star Resolution", body: "We're truly sorry to hear about this experience. We take this very seriously. Please email our CEO directly at ceo@prachar.coffee — we'll make this right." },
];

function Stars({ rating, size = "sm" }: { rating: number; size?: "sm" | "md" }) {
  const s = size === "sm" ? "w-3 h-3" : "w-4 h-4";
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <Star key={i} className={cn(s, i <= rating ? "text-accent fill-accent" : "text-white/15")} />
      ))}
    </div>
  );
}

export default function ReviewsPage() {
  const [filterRating, setFilterRating] = useState(0);
  const [filterPlatform, setFilterPlatform] = useState("all");
  const [filterResponded, setFilterResponded] = useState("all");
  const [sortBy, setSortBy] = useState("newest");
  const [respondingTo, setRespondingTo] = useState<number | null>(null);
  const [responseText, setResponseText] = useState("");
  const [showTemplates, setShowTemplates] = useState(false);

  const filtered = REVIEWS.filter(r => {
    if (filterRating > 0 && r.rating !== filterRating) return false;
    if (filterPlatform !== "all" && r.platform !== filterPlatform) return false;
    if (filterResponded === "responded" && !r.responded) return false;
    if (filterResponded === "unresponded" && r.responded) return false;
    return true;
  }).sort((a, b) => {
    if (sortBy === "highest") return b.rating - a.rating;
    if (sortBy === "lowest") return a.rating - b.rating;
    return 0;
  });

  function aiDraft(review: typeof REVIEWS[0]) {
    setResponseText(
      review.rating >= 4
        ? `Hi ${review.reviewer}, thank you so much for your kind words! We're thrilled you're enjoying Prachar. As a thank you, here's 15% off your next order: THANKS15. ☕`
        : `Hi ${review.reviewer}, we're truly sorry for the experience you described. This doesn't meet our standards. Please reach out to us at hello@prachar.coffee and we'll make it right immediately.`
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Review Management</h1>
          <p className="text-sm text-text-secondary mt-1">Unified inbox for all your review platforms</p>
        </div>
        <span className="badge badge-accent"><Sparkles className="w-3 h-3" /> AI-Powered Responses</span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Avg Rating" value={4.4} suffix="★" delta={0.2} icon={<Star className="w-4 h-4" />} accent="accent" />
        <Metric label="Total Reviews" value={6068} format="compact" delta={12} icon={<MessageSquare className="w-4 h-4" />} accent="info" />
        <Metric label="Response Rate" value={68} suffix="%" delta={8} icon={<Send className="w-4 h-4" />} accent="success" />
        <Metric label="Reviews This Month" value={142} delta={22} icon={<TrendingUp className="w-4 h-4" />} accent="accent" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Review Stream */}
        <div className="lg:col-span-2 space-y-4">
          {/* Review Sources */}
          <Card>
            <SectionHeader title="Review Sources" subtitle="Connected platforms" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {PLATFORMS.map(p => (
                <div key={p.id} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${p.color}20` }}>
                      <Star className="w-3.5 h-3.5" style={{ color: p.color }} />
                    </div>
                    <span className={cn("badge text-[8px]", p.connected ? "badge-success" : "badge-neutral")}>{p.connected ? "Connected" : "Connect"}</span>
                  </div>
                  <div className="text-xs text-text font-medium">{p.label}</div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="font-mono text-xs text-accent">{p.avg}★</span>
                    <span className="text-[10px] text-text-muted">{p.total}</span>
                    <span className={cn("text-[10px] flex items-center gap-0.5", p.trend > 0 ? "text-success" : "text-danger")}>
                      {p.trend > 0 ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}{Math.abs(p.trend)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Review Stream */}
          <Card>
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <SectionHeader title="Review Stream" subtitle={`${filtered.length} reviews`} />
              <div className="flex flex-wrap gap-2 ml-auto">
                <select value={filterRating} onChange={(e) => setFilterRating(Number(e.target.value))} className="input-field text-xs py-1.5 w-24">
                  <option value={0}>All Ratings</option>
                  {[5, 4, 3, 2, 1].map(r => <option key={r} value={r}>{r}★</option>)}
                </select>
                <select value={filterPlatform} onChange={(e) => setFilterPlatform(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Platforms</option>
                  {PLATFORMS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
                <select value={filterResponded} onChange={(e) => setFilterResponded(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="all">All Status</option>
                  <option value="responded">Responded</option>
                  <option value="unresponded">Unresponded</option>
                </select>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="input-field text-xs py-1.5 w-28">
                  <option value="newest">Newest</option>
                  <option value="highest">Highest</option>
                  <option value="lowest">Lowest</option>
                </select>
              </div>
            </div>
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {filtered.map((r, i) => {
                const platform = PLATFORMS.find(p => p.id === r.platform)!;
                return (
                  <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${platform.color}20` }}>
                        <Star className="w-4 h-4" style={{ color: platform.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-text">{r.reviewer}</span>
                          <Stars rating={r.rating} />
                          <span className="text-[10px] text-text-muted ml-auto">{r.date}</span>
                        </div>
                        <p className="text-xs text-text-secondary leading-relaxed mb-2">{r.text}</p>
                        <div className="flex items-center gap-2">
                          <span className="badge badge-neutral text-[9px]">{platform.label}</span>
                          <span className={cn("badge text-[9px]", r.responded ? "badge-success" : "badge-warning")}>{r.responded ? "Responded" : "Pending"}</span>
                          <span className={cn("flex items-center gap-0.5 text-[10px]", r.sentiment === "positive" ? "text-success" : r.sentiment === "negative" ? "text-danger" : "text-text-muted")}>
                            {r.sentiment === "positive" ? <ThumbsUp className="w-3 h-3" /> : r.sentiment === "negative" ? <ThumbsDown className="w-3 h-3" /> : null}
                            {r.sentiment}
                          </span>
                          {!r.responded && (
                            <button onClick={() => { setRespondingTo(respondingTo === r.id ? null : r.id); setResponseText(""); }} className="ml-auto btn-secondary text-xs px-2 py-1">
                              <Reply className="w-3 h-3 inline mr-1" />Respond
                            </button>
                          )}
                        </div>
                        <AnimatePresence>
                          {respondingTo === r.id && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="mt-3 overflow-hidden">
                              <textarea value={responseText} onChange={(e) => setResponseText(e.target.value)} placeholder="Type your response..." className="input-field h-20 resize-none mb-2" />
                              <div className="flex gap-2">
                                <button onClick={() => aiDraft(r)} className="btn-secondary text-xs"><Wand2 className="w-3 h-3 inline mr-1" />AI Draft</button>
                                <button onClick={() => setShowTemplates(!showTemplates)} className="btn-secondary text-xs"><Copy className="w-3 h-3 inline mr-1" />Templates</button>
                                <button className="btn-primary text-xs ml-auto"><Send className="w-3 h-3 inline mr-1" />Send</button>
                              </div>
                              {showTemplates && (
                                <div className="mt-2 space-y-1">
                                  {TEMPLATES.map(t => (
                                    <button key={t.stars} onClick={() => setResponseText(t.body)} className="w-full text-left p-2 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-all">
                                      <div className="flex items-center gap-2 mb-0.5"><Stars rating={t.stars} /><span className="text-xs text-text">{t.title}</span></div>
                                      <p className="text-[10px] text-text-muted truncate">{t.body}</p>
                                    </button>
                                  ))}
                                </div>
                              )}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Right: Analytics */}
        <div className="space-y-4">
          {/* Rating Distribution */}
          <Card>
            <SectionHeader title="Rating Distribution" />
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={RATING_DIST} layout="vertical">
                  <XAxis type="number" tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="rating" tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {RATING_DIST.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Rating Trend */}
          <Card>
            <SectionHeader title="Rating Trend" subtitle="12-month average" />
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={RATING_TREND}>
                  <XAxis dataKey="month" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[4, 5]} tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                  <Line type="monotone" dataKey="rating" stroke="#FFD400" strokeWidth={2} dot={{ fill: "#FFD400", r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Sentiment Themes */}
          <Card>
            <SectionHeader title="AI Theme Analysis" subtitle="What customers say" />
            <div className="space-y-3">
              <div>
                <div className="text-xs text-success mb-2 flex items-center gap-1"><ThumbsUp className="w-3 h-3" /> Positive Themes</div>
                {POSITIVE_THEMES.map(t => (
                  <div key={t.theme} className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
                    <span className="text-xs text-text-secondary">{t.theme}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-text-muted">{t.count}</span>
                      <span className="text-[10px] text-success flex items-center gap-0.5"><TrendingUp className="w-2.5 h-2.5" />{t.trend}%</span>
                    </div>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-xs text-danger mb-2 flex items-center gap-1"><ThumbsDown className="w-3 h-3" /> Negative Themes</div>
                {NEGATIVE_THEMES.map(t => (
                  <div key={t.theme} className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
                    <span className="text-xs text-text-secondary">{t.theme}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-text-muted">{t.count}</span>
                      <span className="text-[10px] text-danger flex items-center gap-0.5"><TrendingDown className="w-2.5 h-2.5" />{Math.abs(t.trend)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* AI Insights */}
          <div className="space-y-2">
            <AIRecommendation
              title="Shipping Complaints Pattern"
              reasoning="3 negative reviews mention 'slow shipping' — consider addressing this in your next campaign or improving fulfillment."
             
            />
            <AIRecommendation
              title="Rating Improvement"
              reasoning="Your Google rating improved 0.3 points this month — highlight this social proof in your ads!"
             
            />
            <AIRecommendation
              title="Response Rate Alert"
              reasoning="32% of reviews are unresponded. Aim for 90%+ response rate to boost customer trust."
             
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Reply(props: any) { return <Send {...props} />; }
