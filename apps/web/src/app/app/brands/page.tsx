"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Plus,
  Search,
  Building2,
  ArrowRight,
  Megaphone,
  TrendingUp,
  Sparkles,
  Globe,
  CheckCircle2,
  AlertTriangle,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card3D } from "@/components/ui/card-3d";
import { PerformanceRing, Sparkline, ProgressBar } from "@/components/ui/charts";
import { SectionHeader, EmptyState } from "@/components/ui/empty-state";

type Health = "green" | "yellow" | "red";

interface Brand {
  id: string;
  name: string;
  industry: string;
  website: string;
  visibility: number;
  platforms: string[];
  activeCampaigns: number;
  trend: number[];
  aiSummary: string;
  health: Health;
}

const PLATFORM_ICONS: Record<string, string> = {
  Google: "G",
  Meta: "M",
  Instagram: "IG",
  YouTube: "YT",
  TikTok: "TT",
  LinkedIn: "in",
  X: "X",
};

const HEALTH_DOT: Record<Health, string> = {
  green: "bg-success shadow-glow-green",
  yellow: "bg-warning",
  red: "bg-danger shadow-glow-red",
};

const INDUSTRIES = ["All", "F&B", "D2C", "SaaS", "Retail", "Health"];

const MOCK_BRANDS: Brand[] = [
  {
    id: "1",
    name: "Demo Coffee Co",
    industry: "F&B",
    website: "democoffee.in",
    visibility: 24.3,
    platforms: ["Google", "Meta", "Instagram", "YouTube"],
    activeCampaigns: 4,
    trend: [12, 15, 14, 18, 22, 20, 24, 28],
    aiSummary: "Visibility climbing +6.8 pts — Google RSA outperforming Meta by 18% CPA.",
    health: "green",
  },
  {
    id: "2",
    name: "Lumen Skincare",
    industry: "D2C",
    website: "lumenskin.com",
    visibility: 41.7,
    platforms: ["Google", "Meta", "Instagram", "TikTok"],
    activeCampaigns: 6,
    trend: [30, 34, 33, 38, 40, 42, 41, 44],
    aiSummary: "Strong social momentum. TikTok CTR up 31% — recommend budget shift.",
    health: "green",
  },
  {
    id: "3",
    name: "NorthPeak SaaS",
    industry: "SaaS",
    website: "northpeak.io",
    visibility: 18.2,
    platforms: ["Google", "LinkedIn", "X"],
    activeCampaigns: 2,
    trend: [22, 20, 19, 18, 17, 18, 18, 18],
    aiSummary: "LinkedIn lead CPA rising. Pause 2 underperforming ad sets this week.",
    health: "yellow",
  },
  {
    id: "4",
    name: "Verde Organics",
    industry: "Retail",
    website: "verdeorganics.in",
    visibility: 52.1,
    platforms: ["Google", "Meta", "Instagram", "YouTube", "TikTok"],
    activeCampaigns: 8,
    trend: [40, 44, 48, 46, 50, 52, 51, 54],
    aiSummary: "Best-in-class visibility. AI citations up 22% — keep publishing YouTube.",
    health: "green",
  },
  {
    id: "5",
    name: "PulseFit Studios",
    industry: "Health",
    website: "pulsefit.studio",
    visibility: 9.4,
    platforms: ["Meta", "Instagram"],
    activeCampaigns: 1,
    trend: [14, 12, 11, 10, 9, 9, 8, 9],
    aiSummary: "Visibility declining. No Google Ads active — recommend immediate launch.",
    health: "red",
  },
  {
    id: "6",
    name: "Atlas Brew",
    industry: "F&B",
    website: "atlasbrew.co",
    visibility: 33.6,
    platforms: ["Google", "Instagram", "YouTube"],
    activeCampaigns: 3,
    trend: [24, 26, 28, 30, 31, 33, 32, 34],
    aiSummary: "Steady growth. YouTube metadata engine ready — schedule 2 uploads.",
    health: "yellow",
  },
];

export default function BrandsListPage() {
  const [query, setQuery] = useState("");
  const [industry, setIndustry] = useState("All");

  const filtered = useMemo(() => {
    return MOCK_BRANDS.filter((b) => {
      const matchesQuery =
        b.name.toLowerCase().includes(query.toLowerCase()) ||
        b.website.toLowerCase().includes(query.toLowerCase());
      const matchesIndustry = industry === "All" || b.industry === industry;
      return matchesQuery && matchesIndustry;
    });
  }, [query, industry]);

  return (
    <div className="space-y-6">
      {/* ─── Header ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Brands</h1>
          <p className="text-sm text-text-secondary mt-1">
            {MOCK_BRANDS.length} brands · AI managing visibility across 16+ platforms
          </p>
        </div>
        <button className="btn-primary group">
          <Plus className="w-4 h-4" />
          Add Brand
        </button>
      </div>

      {/* ─── Controls ─── */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search brands or websites..."
            className="input-field pl-10 w-full"
          />
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {INDUSTRIES.map((ind) => (
            <button
              key={ind}
              onClick={() => setIndustry(ind)}
              className={cn(
                "px-3 py-2 rounded-lg text-xs font-mono whitespace-nowrap transition-all",
                industry === ind
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "text-text-secondary hover:text-text hover:bg-white/[0.04] border border-transparent",
              )}
            >
              {ind}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Grid or Empty ─── */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Building2 className="w-6 h-6 text-accent" />}
          title="No brands yet"
          description="Add your first brand to let AI start managing your visibility across 16+ platforms — Google, Meta, YouTube, TikTok, and more."
          actionLabel="Add your first brand"
          action={() => setQuery("")}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map((brand, i) => (
            <motion.div
              key={brand.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            >
              <Card3D glow={brand.health === "green"} className="h-full">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center shrink-0 border border-accent/10">
                      <span className="font-display text-lg font-semibold text-accent">
                        {brand.name.charAt(0)}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-display text-base font-semibold text-text truncate">
                        {brand.name}
                      </h3>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="badge badge-neutral text-[10px]">{brand.industry}</span>
                        <span className="flex items-center gap-1 text-[11px] text-text-muted">
                          <Globe className="w-3 h-3" />
                          {brand.website}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="relative shrink-0">
                    <span className={cn("block w-2.5 h-2.5 rounded-full", HEALTH_DOT[brand.health])} />
                    {brand.health === "green" && (
                      <motion.span
                        className="absolute inset-0 rounded-full bg-success"
                        animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
                        transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
                      />
                    )}
                  </div>
                </div>

                {/* Visibility + trend */}
                <div className="flex items-center gap-4 mb-4">
                  <PerformanceRing
                    value={brand.visibility}
                    size={72}
                    strokeWidth={6}
                    sublabel="vis"
                    accent={brand.health === "red" ? "#EF4444" : brand.health === "yellow" ? "#F59E0B" : "#FFD400"}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="label-field mb-1">7-day trend</div>
                    <Sparkline
                      data={brand.trend}
                      width={140}
                      height={36}
                      color={brand.health === "red" ? "#EF4444" : "#FFD400"}
                    />
                    <div className="flex items-center gap-1 mt-1">
                      <TrendingUp className="w-3 h-3 text-success" />
                      <span className="font-mono text-[11px] text-success">
                        +{(((brand.trend[brand.trend.length - 1] ?? 0) - (brand.trend[0] ?? 0)) / (brand.trend[0] || 1) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Platforms */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="label-field">Connected platforms</span>
                    <span className="font-mono text-[11px] text-text-secondary">
                      {brand.platforms.length}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {brand.platforms.map((p) => (
                      <span
                        key={p}
                        className="w-7 h-7 rounded-md bg-white/[0.04] border border-white/[0.06] flex items-center justify-center font-mono text-[10px] font-medium text-text-secondary"
                        title={p}
                      >
                        {PLATFORM_ICONS[p] ?? p.slice(0, 2)}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Active campaigns */}
                <div className="flex items-center justify-between py-2.5 border-y border-white/[0.04] mb-3">
                  <div className="flex items-center gap-2">
                    <Megaphone className="w-3.5 h-3.5 text-text-secondary" />
                    <span className="text-xs text-text-secondary">Active campaigns</span>
                  </div>
                  <span className="font-mono text-sm font-medium text-text">
                    {brand.activeCampaigns}
                  </span>
                </div>

                {/* AI summary */}
                <div className="flex items-start gap-2 mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
                  <p className="text-xs text-text-secondary leading-relaxed">{brand.aiSummary}</p>
                </div>

                {/* CTA */}
                <Link
                  href={`/app/brands/${brand.id}`}
                  className="group flex items-center justify-between w-full pt-3 border-t border-white/[0.04]"
                >
                  <span className="text-xs font-mono text-text-secondary group-hover:text-text transition-colors">
                    View Workspace
                  </span>
                  <ArrowRight className="w-4 h-4 text-text-secondary group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
                </Link>
              </Card3D>
            </motion.div>
          ))}
        </div>
      )}

      {/* ─── Footer summary ─── */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
          {[
            { label: "Total brands", value: MOCK_BRANDS.length, icon: <Building2 className="w-3.5 h-3.5" /> },
            { label: "Healthy", value: MOCK_BRANDS.filter((b) => b.health === "green").length, icon: <CheckCircle2 className="w-3.5 h-3.5" />, accent: "text-success" },
            { label: "Needs attention", value: MOCK_BRANDS.filter((b) => b.health === "yellow").length, icon: <AlertTriangle className="w-3.5 h-3.5" />, accent: "text-warning" },
            { label: "At risk", value: MOCK_BRANDS.filter((b) => b.health === "red").length, icon: <Circle className="w-3.5 h-3.5" />, accent: "text-danger" },
          ].map((s) => (
            <div key={s.label} className="card-3d rounded-xl p-4 flex items-center gap-3">
              <div className={cn("text-text-secondary", s.accent)}>{s.icon}</div>
              <div>
                <div className="font-mono text-lg font-semibold text-text">{s.value}</div>
                <div className="label-field">{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
