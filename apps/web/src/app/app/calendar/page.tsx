"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { AIStatusBlock } from "@/components/ui/ai-blocks";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  ChevronLeft, ChevronRight, Plus, Calendar as CalIcon,
  Instagram, Facebook, Twitter, Youtube, Linkedin, Wand2,
  Clock, Zap, X, Edit3, Trash2, Sparkles, Filter,
} from "lucide-react";

const PLATFORM_ICONS: Record<string, typeof Instagram> = {
  instagram: Instagram, facebook: Facebook, twitter: Twitter, youtube: Youtube, linkedin: Linkedin,
};
const PLATFORM_COLORS: Record<string, string> = {
  instagram: "#E1306C", facebook: "#1877F2", twitter: "#1DA1F2", youtube: "#FF0000", linkedin: "#0A66C2",
};
const TYPE_COLORS: Record<string, string> = {
  organic: "#22C55E", paid: "#FFD400", social: "#3B82F6", urgent: "#EF4444", story: "#A855F7", reel: "#EC4899", video: "#F97316", carousel: "#06B6D4",
};

const MOCK_POSTS = [
  { id: 1, day: 2, title: "Morning Brew Reel", platform: "instagram", type: "reel", time: "08:00", status: "scheduled" },
  { id: 2, day: 2, title: "Customer Testimonial", platform: "facebook", type: "organic", time: "14:00", status: "scheduled" },
  { id: 3, day: 5, title: "Product Launch Teaser", platform: "instagram", type: "paid", time: "10:00", status: "scheduled" },
  { id: 4, day: 5, title: "Behind the Scenes", platform: "youtube", type: "video", time: "16:00", status: "draft" },
  { id: 5, day: 7, title: "Weekend Special Offer", platform: "facebook", type: "paid", time: "09:00", status: "scheduled" },
  { id: 6, day: 8, title: "Latte Art Tutorial", platform: "instagram", type: "reel", time: "11:00", status: "scheduled" },
  { id: 7, day: 10, title: "Industry Insight Post", platform: "linkedin", type: "organic", time: "08:30", status: "scheduled" },
  { id: 8, day: 12, title: "Flash Sale 24h", platform: "instagram", type: "urgent", time: "12:00", status: "scheduled" },
  { id: 9, day: 12, title: "Flash Sale Tweet", platform: "twitter", type: "urgent", time: "12:00", status: "scheduled" },
  { id: 10, day: 14, title: "Brand Story Carousel", platform: "instagram", type: "carousel", time: "15:00", status: "draft" },
  { id: 11, day: 15, title: "Mid-month Recap", platform: "facebook", type: "organic", time: "17:00", status: "scheduled" },
  { id: 12, day: 17, title: "Customer Spotlight", platform: "instagram", type: "story", time: "10:00", status: "scheduled" },
  { id: 13, day: 19, title: "Tutorial Tuesday", platform: "youtube", type: "video", time: "14:00", status: "scheduled" },
  { id: 14, day: 21, title: "Partnership Announcement", platform: "linkedin", type: "organic", time: "09:00", status: "scheduled" },
  { id: 15, day: 22, title: "Weekend Vibes Reel", platform: "instagram", type: "reel", time: "18:00", status: "scheduled" },
  { id: 16, day: 24, title: "Sustainability Story", platform: "facebook", type: "organic", time: "11:00", status: "scheduled" },
  { id: 17, day: 25, title: "Product Feature Ad", platform: "instagram", type: "paid", time: "13:00", status: "scheduled" },
  { id: 18, day: 27, title: "FAQ Friday", platform: "twitter", type: "social", time: "10:00", status: "scheduled" },
  { id: 19, day: 28, title: "Monthly Highlights", platform: "instagram", type: "carousel", time: "16:00", status: "draft" },
  { id: 20, day: 30, title: "End of Month Sale", platform: "facebook", type: "paid", time: "09:00", status: "scheduled" },
];

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const FILTERS = [
  { id: "instagram", label: "Instagram", icon: Instagram },
  { id: "facebook", label: "Facebook", icon: Facebook },
  { id: "twitter", label: "Twitter", icon: Twitter },
  { id: "youtube", label: "YouTube", icon: Youtube },
  { id: "linkedin", label: "LinkedIn", icon: Linkedin },
];

const CONTENT_TYPES = ["Organic", "Paid", "Story", "Reel", "Video", "Carousel"];

export default function CalendarPage() {
  const [monthIdx, setMonthIdx] = useState(6); // July
  const [view, setView] = useState<"month" | "week">("month");
  const [selectedPost, setSelectedPost] = useState<typeof MOCK_POSTS[0] | null>(null);
  const [showCompose, setShowCompose] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [platformFilters, setPlatformFilters] = useState<string[]>([]);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const year = 2026;
  const firstDay = new Date(year, monthIdx, 1).getDay();
  const daysInMonth = new Date(year, monthIdx + 1, 0).getDate();
  const weeks = Math.ceil((firstDay + daysInMonth) / 7);
  const days = Array.from({ length: weeks * 7 }, (_, i) => {
    const dayNum = i - firstDay + 1;
    return dayNum >= 1 && dayNum <= daysInMonth ? dayNum : null;
  });

  const filteredPosts = MOCK_POSTS.filter(p => {
    if (platformFilters.length > 0 && !platformFilters.includes(p.platform)) return false;
    if (typeFilter !== "all" && p.type !== typeFilter.toLowerCase()) return false;
    return true;
  });

  function getPostsForDay(day: number | null) {
    if (!day) return [];
    return filteredPosts.filter(p => p.day === day);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Content Calendar</h1>
          <p className="text-sm text-text-secondary mt-1">Visual drag-and-drop scheduling across all platforms</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowHeatmap(!showHeatmap)} className={cn("btn-secondary text-sm", showHeatmap && "bg-accent/10 text-accent border-accent/30")}>
            <Zap className="w-4 h-4" />Best Times
          </button>
          <button className="btn-secondary text-sm"><Wand2 className="w-4 h-4" />AI Optimize</button>
          <button onClick={() => setShowCompose(true)} className="btn-primary text-sm"><Plus className="w-4 h-4" />New Post</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <SectionHeader title="Filters" />
            <div className="space-y-3">
              <div>
                <label className="label-field block mb-1.5">Brand</label>
                <select className="input-field text-xs py-1.5"><option>Prachar Coffee</option><option>BeanThere</option></select>
              </div>
              <div>
                <label className="label-field block mb-1.5">Platforms</label>
                <div className="space-y-1">
                  {FILTERS.map(f => (
                    <label key={f.id} className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={platformFilters.includes(f.id)} onChange={(e) => setPlatformFilters(e.target.checked ? [...platformFilters, f.id] : platformFilters.filter(p => p !== f.id))} className="accent-accent" />
                      <f.icon className="w-3 h-3" style={{ color: PLATFORM_COLORS[f.id] }} />
                      <span className="text-xs text-text-secondary">{f.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-1.5">Content Type</label>
                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input-field text-xs py-1.5">
                  <option value="all">All Types</option>
                  {CONTENT_TYPES.map(t => <option key={t} value={t.toLowerCase()}>{t}</option>)}
                </select>
              </div>
              <button className="btn-secondary text-xs w-full"><Sparkles className="w-3 h-3 inline mr-1" />AI Auto-Fill</button>
            </div>
          </Card>

          <Card>
            <SectionHeader title="This Month" />
            <div className="space-y-2">
              <div className="flex justify-between text-xs"><span className="text-text-secondary">Total posts</span><span className="font-mono text-text">{MOCK_POSTS.length}</span></div>
              <div className="flex justify-between text-xs"><span className="text-text-secondary">Scheduled</span><span className="font-mono text-success">{MOCK_POSTS.filter(p => p.status === "scheduled").length}</span></div>
              <div className="flex justify-between text-xs"><span className="text-text-secondary">Drafts</span><span className="font-mono text-warning">{MOCK_POSTS.filter(p => p.status === "draft").length}</span></div>
              <div className="divider my-2" />
              <div className="text-[10px] text-text-muted mb-1">By Platform</div>
              {Object.keys(PLATFORM_ICONS).map(p => {
                const count = MOCK_POSTS.filter(post => post.platform === p).length;
                return <div key={p} className="flex justify-between text-xs"><span className="text-text-secondary capitalize">{p}</span><span className="font-mono text-text">{count}</span></div>;
              })}
            </div>
          </Card>
        </div>

        {/* Calendar */}
        <div className="lg:col-span-10 space-y-4">
          {/* Top bar */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <button onClick={() => setMonthIdx((monthIdx - 1 + 12) % 12)} className="p-1.5 rounded-lg hover:bg-white/[0.04] transition-all"><ChevronLeft className="w-4 h-4 text-text-secondary" /></button>
                <h2 className="font-display text-lg font-semibold text-text">{MONTHS[monthIdx]} {year}</h2>
                <button onClick={() => setMonthIdx((monthIdx + 1) % 12)} className="p-1.5 rounded-lg hover:bg-white/[0.04] transition-all"><ChevronRight className="w-4 h-4 text-text-secondary" /></button>
                <button className="btn-ghost text-xs ml-2">Today</button>
              </div>
              <div className="flex gap-1 p-1 rounded-lg bg-bg-surface">
                {(["month", "week"] as const).map(v => (
                  <button key={v} onClick={() => setView(v)} className={cn("px-3 py-1 rounded-md text-xs font-medium capitalize transition-all", view === v ? "bg-accent/10 text-accent" : "text-text-secondary")}>{v}</button>
                ))}
              </div>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 gap-1 mb-1">
              {DAYS.map(d => <div key={d} className="text-center text-[10px] font-medium text-text-muted py-2">{d}</div>)}
            </div>

            {/* Calendar grid */}
            <div className="grid grid-cols-7 gap-1">
              {days.map((day, i) => {
                const posts = getPostsForDay(day);
                const isToday = day === 16;
                return (
                  <div
                    key={i}
                    className={cn(
                      "min-h-[100px] rounded-lg border p-1.5 transition-all relative group",
                      day === null ? "border-transparent bg-transparent" : "border-white/[0.04] bg-white/[0.01] hover:bg-white/[0.03]",
                      isToday && "border-accent/30 bg-accent/5",
                    )}
                  >
                    {day !== null && (
                      <>
                        <div className="flex items-center justify-between mb-1">
                          <span className={cn("text-xs font-medium", isToday ? "text-accent" : "text-text-secondary")}>{day}</span>
                          {posts.length > 0 && <span className="flex gap-0.5">{posts.slice(0, 3).map(p => <span key={p.id} className="w-1.5 h-1.5 rounded-full" style={{ background: TYPE_COLORS[p.type] }} />)}</span>}
                          <button className="opacity-0 group-hover:opacity-100 transition-opacity text-text-muted hover:text-accent"><Plus className="w-3 h-3" /></button>
                        </div>
                        <div className="space-y-0.5">
                          {posts.slice(0, 3).map(p => {
                            const Icon = PLATFORM_ICONS[p.platform] || Instagram;
                            return (
                              <motion.div
                                key={p.id}
                                drag
                                dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
                                whileDrag={{ scale: 1.05, zIndex: 10 }}
                                onClick={() => setSelectedPost(p)}
                                className="p-1 rounded text-[9px] cursor-pointer flex items-center gap-1 hover:scale-[1.02] transition-transform"
                                style={{ background: `${TYPE_COLORS[p.type]}15`, borderLeft: `2px solid ${TYPE_COLORS[p.type]}` }}
                              >
                                <Icon className="w-2.5 h-2.5 shrink-0" style={{ color: PLATFORM_COLORS[p.platform] }} />
                                <span className="text-text-secondary truncate">{p.title}</span>
                              </motion.div>
                            );
                          })}
                          {posts.length > 3 && <div className="text-[9px] text-text-muted pl-1">+{posts.length - 3} more</div>}
                        </div>
                        {showHeatmap && day !== null && (
                          <div className="absolute inset-0 rounded-lg pointer-events-none" style={{ background: `rgba(34, 197, 94, ${Math.random() * 0.15})` }} />
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Upcoming This Week */}
          <Card>
            <SectionHeader title="Upcoming This Week" subtitle="Next 7 days" icon={<Clock className="w-4 h-4" />} />
            <div className="flex gap-3 overflow-x-auto pb-2">
              {Array.from({ length: 7 }, (_, i) => {
                const day = 16 + i;
                const posts = MOCK_POSTS.filter(p => p.day === day);
                return (
                  <div key={i} className="shrink-0 w-32 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <div className="text-xs text-text-secondary mb-1">{DAYS[(3 + i) % 7]} {day}</div>
                    {posts.length === 0 ? (
                      <div className="text-[10px] text-text-muted py-3 text-center">No posts</div>
                    ) : (
                      posts.map(p => {
                        const Icon = PLATFORM_ICONS[p.platform] || Instagram;
                        return <div key={p.id} className="p-1 rounded text-[9px] mb-1 flex items-center gap-1" style={{ background: `${TYPE_COLORS[p.type]}15` }}><Icon className="w-2.5 h-2.5 shrink-0" style={{ color: PLATFORM_COLORS[p.platform] }} /><span className="text-text-secondary truncate">{p.title}</span></div>;
                      })
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>

      {/* Post Detail Modal */}
      <AnimatePresence>
        {selectedPost && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelectedPost(null)} className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} onClick={(e) => e.stopPropagation()} className="w-full max-w-md">
              <Card3D glow>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-display text-lg font-semibold text-text">Post Details</h3>
                  <button onClick={() => setSelectedPost(null)} className="text-text-muted hover:text-text"><X className="w-4 h-4" /></button>
                </div>
                {(() => {
                  const Icon = PLATFORM_ICONS[selectedPost.platform] || Instagram;
                  return (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${PLATFORM_COLORS[selectedPost.platform]}20` }}><Icon className="w-4 h-4" style={{ color: PLATFORM_COLORS[selectedPost.platform] }} /></div>
                        <div><div className="text-sm text-text">{selectedPost.title}</div><div className="text-xs text-text-muted capitalize">{selectedPost.platform} · {selectedPost.type}</div></div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-2 rounded-lg bg-white/[0.02]"><div className="text-[10px] text-text-muted">Time</div><div className="text-xs text-text font-mono">{selectedPost.time}</div></div>
                        <div className="p-2 rounded-lg bg-white/[0.02]"><div className="text-[10px] text-text-muted">Status</div><div className="text-xs text-text capitalize">{selectedPost.status}</div></div>
                      </div>
                      <div className="p-3 rounded-lg bg-accent/5 border border-accent/10"><div className="text-[10px] text-accent mb-1 flex items-center gap-1"><Sparkles className="w-3 h-3" />AI Suggestion</div><p className="text-xs text-text-secondary">Consider adding 3-5 trending hashtags: #CoffeeLovers #MorningBrew #PracharCoffee</p></div>
                      <div className="flex gap-2">
                        <button className="btn-secondary text-xs flex-1"><Edit3 className="w-3 h-3 inline mr-1" />Edit</button>
                        <button className="btn-secondary text-xs flex-1 text-danger"><Trash2 className="w-3 h-3 inline mr-1" />Delete</button>
                      </div>
                    </div>
                  );
                })()}
              </Card3D>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Compose Modal */}
      <AnimatePresence>
        {showCompose && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowCompose(false)} className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} onClick={(e) => e.stopPropagation()} className="w-full max-w-lg">
              <Card3D glow>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-display text-lg font-semibold text-text">Compose New Post</h3>
                  <button onClick={() => setShowCompose(false)} className="text-text-muted hover:text-text"><X className="w-4 h-4" /></button>
                </div>
                <div className="space-y-3">
                  <div><label className="label-field block mb-1.5">Post Title</label><input className="input-field" placeholder="Enter post title..." /></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="label-field block mb-1.5">Platform</label><select className="input-field">{Object.keys(PLATFORM_ICONS).map(p => <option key={p} value={p} className="capitalize">{p}</option>)}</select></div>
                    <div><label className="label-field block mb-1.5">Type</label><select className="input-field">{CONTENT_TYPES.map(t => <option key={t}>{t}</option>)}</select></div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="label-field block mb-1.5">Date</label><input type="date" className="input-field" /></div>
                    <div><label className="label-field block mb-1.5">Time</label><input type="time" className="input-field" /></div>
                  </div>
                  <div><label className="label-field block mb-1.5">Content</label><textarea className="input-field h-24 resize-none" placeholder="Write your post content..." /></div>
                  <button className="btn-secondary text-xs w-full"><Wand2 className="w-3 h-3 inline mr-1" />AI Generate Content</button>
                  <div className="flex gap-2">
                    <button className="btn-secondary text-sm flex-1">Save Draft</button>
                    <button className="btn-primary text-sm flex-1">Schedule Post</button>
                  </div>
                </div>
              </Card3D>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
