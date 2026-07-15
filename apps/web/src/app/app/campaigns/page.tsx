"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Search,
  LayoutGrid,
  Calendar,
  GitBranch,
  Sparkles,
  Wand2,
  ArrowRight,
  Target,
  DollarSign,
  TrendingUp,
  Eye,
  GripVertical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { SectionHeader } from "@/components/ui/empty-state";

type Column = "draft" | "review" | "active" | "completed";
type View = "kanban" | "timeline" | "calendar";

interface Campaign {
  id: string;
  name: string;
  brand: string;
  network: "Google" | "Meta" | "TikTok" | "YouTube" | "LinkedIn";
  budget: number;
  roas: number;
  ctr: number;
  column: Column;
  thumbnail: string;
}

const NETWORK_BADGE: Record<Campaign["network"], { cls: string; short: string }> = {
  Google: { cls: "badge-info", short: "G" },
  Meta: { cls: "badge-info", short: "M" },
  TikTok: { cls: "badge-neutral", short: "TT" },
  YouTube: { cls: "badge-danger", short: "YT" },
  LinkedIn: { cls: "badge-info", short: "in" },
};

const COLUMNS: { id: Column; label: string; accent: string }[] = [
  { id: "draft", label: "Draft", accent: "bg-text-muted" },
  { id: "review", label: "In Review", accent: "bg-warning" },
  { id: "active", label: "Active", accent: "bg-success" },
  { id: "completed", label: "Completed", accent: "bg-info" },
];

const MOCK_CAMPAIGNS: Campaign[] = [
  { id: "1", name: "Google RSA — Coffee Search", brand: "Demo Coffee Co", network: "Google", budget: 500, roas: 3.2, ctr: 4.8, column: "active", thumbnail: "from-accent/30 to-accent/5" },
  { id: "2", name: "Meta CBO — Retargeting", brand: "Demo Coffee Co", network: "Meta", budget: 300, roas: 1.8, ctr: 2.1, column: "active", thumbnail: "from-info/30 to-info/5" },
  { id: "3", name: "YouTube — Cold Brew Awareness", brand: "Atlas Brew", network: "YouTube", budget: 200, roas: 2.5, ctr: 3.4, column: "active", thumbnail: "from-danger/30 to-danger/5" },
  { id: "4", name: "TikTok — Glow Routine", brand: "Lumen Skincare", network: "TikTok", budget: 180, roas: 0, ctr: 0, column: "review", thumbnail: "from-accent/20 to-info/5" },
  { id: "5", name: "Instagram — Story Ads", brand: "Demo Coffee Co", network: "Meta", budget: 150, roas: 2.1, ctr: 3.0, column: "review", thumbnail: "from-info/20 to-accent/5" },
  { id: "6", name: "LinkedIn — Lead Gen Q3", brand: "NorthPeak SaaS", network: "LinkedIn", budget: 250, roas: 0, ctr: 0, column: "draft", thumbnail: "from-info/20 to-success/5" },
  { id: "7", name: "Google — Organic Push", brand: "Verde Organics", network: "Google", budget: 400, roas: 0, ctr: 0, column: "draft", thumbnail: "from-success/20 to-accent/5" },
  { id: "8", name: "Meta — Summer Sale 2024", brand: "Verde Organics", network: "Meta", budget: 600, roas: 4.1, ctr: 5.2, column: "completed", thumbnail: "from-accent/20 to-danger/5" },
];

const NETWORKS = ["All", "Google", "Meta", "TikTok", "YouTube", "LinkedIn"];
const BRANDS = ["All", "Demo Coffee Co", "Lumen Skincare", "Atlas Brew", "NorthPeak SaaS", "Verde Organics"];

export default function CampaignStudioPage() {
  const [view, setView] = useState<View>("kanban");
  const [networkFilter, setNetworkFilter] = useState("All");
  const [brandFilter, setBrandFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [prompt, setPrompt] = useState("");

  const filtered = useMemo(() => {
    return MOCK_CAMPAIGNS.filter((c) => {
      const matchesQuery = c.name.toLowerCase().includes(query.toLowerCase());
      const matchesNetwork = networkFilter === "All" || c.network === networkFilter;
      const matchesBrand = brandFilter === "All" || c.brand === brandFilter;
      return matchesQuery && matchesNetwork && matchesBrand;
    });
  }, [query, networkFilter, brandFilter]);

  const activeCount = MOCK_CAMPAIGNS.filter((c) => c.column === "active").length;
  const totalSpend = MOCK_CAMPAIGNS.filter((c) => c.column === "active").reduce((s, c) => s + c.budget, 0);
  const activeRoas = MOCK_CAMPAIGNS.filter((c) => c.column === "active" && c.roas > 0);
  const avgRoas = activeRoas.length ? activeRoas.reduce((s, c) => s + c.roas, 0) / activeRoas.length : 0;

  return (
    <div className="space-y-6">
      {/* ─── Header ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Campaign Studio</h1>
          <p className="text-sm text-text-secondary mt-1">
            Plan, launch, and optimize campaigns across every network
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center gap-0.5 p-1 rounded-lg bg-white/[0.04] border border-white/[0.06]">
            {([
              { id: "kanban", icon: LayoutGrid, label: "Kanban" },
              { id: "timeline", icon: GitBranch, label: "Timeline" },
              { id: "calendar", icon: Calendar, label: "Calendar" },
            ] as { id: View; icon: typeof LayoutGrid; label: string }[]).map((v) => (
              <button
                key={v.id}
                onClick={() => setView(v.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all",
                  view === v.id
                    ? "bg-accent/10 text-accent"
                    : "text-text-secondary hover:text-text",
                )}
              >
                <v.icon className="w-3.5 h-3.5" />
                {v.label}
              </button>
            ))}
          </div>
          <button className="btn-primary group">
            <Plus className="w-4 h-4" />
            New Campaign
          </button>
        </div>
      </div>

      {/* ─── Metrics Summary ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Active Campaigns" value={activeCount} icon={<Target className="w-4 h-4" />} accent="success" />
        <Metric label="Daily Spend" value={totalSpend} format="currency" icon={<DollarSign className="w-4 h-4" />} accent="accent" />
        <Metric label="Avg ROAS" value={avgRoas} suffix="x" delta={12.4} deltaLabel="vs last wk" icon={<TrendingUp className="w-4 h-4" />} accent="info" />
        <Metric label="Total Conversions" value={127} delta={23} deltaLabel="vs last wk" icon={<Eye className="w-4 h-4" />} />
      </div>

      {/* ─── Filters ─── */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search campaigns..."
            className="input-field pl-10 w-full"
          />
        </div>
        <select
          value={networkFilter}
          onChange={(e) => setNetworkFilter(e.target.value)}
          className="input-field md:w-40 cursor-pointer"
        >
          {NETWORKS.map((n) => (
            <option key={n} value={n} className="bg-bg-card">
              {n === "All" ? "All networks" : n}
            </option>
          ))}
        </select>
        <select
          value={brandFilter}
          onChange={(e) => setBrandFilter(e.target.value)}
          className="input-field md:w-48 cursor-pointer"
        >
          {BRANDS.map((b) => (
            <option key={b} value={b} className="bg-bg-card">
              {b === "All" ? "All brands" : b}
            </option>
          ))}
        </select>
      </div>

      {/* ─── Main: Board + AI Sidebar ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6">
        {/* Kanban Board */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {COLUMNS.map((col) => {
            const items = filtered.filter((c) => c.column === col.id);
            return (
              <div key={col.id} className="flex flex-col gap-3">
                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <span className={cn("w-2 h-2 rounded-full", col.accent)} />
                    <span className="font-display text-sm font-medium text-text">{col.label}</span>
                  </div>
                  <span className="font-mono text-xs text-text-muted">{items.length}</span>
                </div>
                <div className="space-y-3 min-h-[120px]">
                  {items.map((c, i) => (
                    <motion.div
                      key={c.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      whileHover={{ y: -3, scale: 1.01 }}
                      drag
                      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
                      dragElastic={0.15}
                      className="card-3d rounded-xl p-3 cursor-grab active:cursor-grabbing"
                    >
                      {/* Thumbnail */}
                      <div className={cn("h-16 rounded-lg bg-gradient-to-br mb-3 relative overflow-hidden", c.thumbnail)}>
                        <div className="absolute top-2 left-2">
                          <span className={cn("badge text-[9px]", NETWORK_BADGE[c.network].cls)}>
                            {c.network}
                          </span>
                        </div>
                        <div className="absolute top-2 right-2 text-text-muted/60">
                          <GripVertical className="w-3.5 h-3.5" />
                        </div>
                        <div className="absolute bottom-2 left-2 w-6 h-6 rounded-md bg-bg/60 backdrop-blur flex items-center justify-center font-mono text-[10px] font-medium text-text">
                          {NETWORK_BADGE[c.network].short}
                        </div>
                      </div>

                      <div className="text-sm font-medium text-text leading-snug mb-1">{c.name}</div>
                      <div className="text-[11px] text-text-muted mb-3">{c.brand}</div>

                      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.04]">
                        <div>
                          <div className="label-field text-[9px]">Budget</div>
                          <div className="font-mono text-[11px] text-text">₹{c.budget}</div>
                        </div>
                        <div>
                          <div className="label-field text-[9px]">ROAS</div>
                          <div className="font-mono text-[11px] text-text">
                            {c.roas > 0 ? `${c.roas}x` : "—"}
                          </div>
                        </div>
                        <div>
                          <div className="label-field text-[9px]">CTR</div>
                          <div className="font-mono text-[11px] text-text">
                            {c.ctr > 0 ? `${c.ctr}%` : "—"}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                  {items.length === 0 && (
                    <div className="rounded-xl border border-dashed border-white/[0.06] p-6 text-center">
                      <span className="text-xs text-text-muted">Drop campaigns here</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* AI Campaign Builder Sidebar */}
        <div className="space-y-4">
          <Card3D glow className="sticky top-4">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Wand2 className="w-4 h-4 text-accent" />
              </div>
              <div>
                <h3 className="font-display text-sm font-semibold text-text">AI Campaign Builder</h3>
                <p className="text-[11px] text-text-muted">Describe your goal — AI builds the rest</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <label className="label-field">Campaign goal</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={4}
                  placeholder="e.g. Launch a Google Search campaign for Demo Coffee Co targeting 'specialty coffee mumbai' with ₹500/day budget, focused on conversions..."
                  className="input-field resize-none mt-1.5"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label-field">Network</label>
                  <select className="input-field mt-1.5 cursor-pointer text-xs">
                    <option className="bg-bg-card">Google</option>
                    <option className="bg-bg-card">Meta</option>
                    <option className="bg-bg-card">YouTube</option>
                    <option className="bg-bg-card">TikTok</option>
                  </select>
                </div>
                <div>
                  <label className="label-field">Budget/day</label>
                  <input className="input-field mt-1.5 text-xs" placeholder="₹500" />
                </div>
              </div>

              <button className="btn-primary w-full group">
                <Sparkles className="w-4 h-4" />
                Generate Campaign
              </button>
            </div>

            <div className="mt-4 pt-4 border-t border-white/[0.04] space-y-2">
              <div className="label-field mb-2">Suggested by AI</div>
              {[
                "Retarget cart abandoners on Meta · ₹300/day",
                "YouTube awareness for cold brew launch",
                "Google RSA — competitor keyword conquest",
              ].map((s) => (
                <button
                  key={s}
                  onClick={() => setPrompt(s)}
                  className="group flex items-center justify-between w-full p-2.5 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] transition-colors text-left"
                >
                  <span className="text-xs text-text-secondary group-hover:text-text transition-colors">
                    {s}
                  </span>
                  <ArrowRight className="w-3 h-3 text-text-muted group-hover:text-accent transition-colors shrink-0" />
                </button>
              ))}
            </div>
          </Card3D>
        </div>
      </div>
    </div>
  );
}
