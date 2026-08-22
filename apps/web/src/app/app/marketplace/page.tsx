"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  Music2,
  Sparkles,
  MessageCircle,
  Flame,
  FlaskConical,
  Eye,
  Mic,
  Users,
  Check,
  Settings2,
  Star,
} from "lucide-react";
import { Card, Card3D } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

const CATEGORIES = ["All", "Channels", "AI Models", "Creative Tools", "Analytics", "Automation"];

interface Item {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: typeof Music2;
  installed: boolean;
  rating: number;
  installs: string;
  accent: string;
}

const ITEMS: Item[] = [
  { id: "tiktok", name: "TikTok Ads Pro", description: "Advanced TikTok campaign management with Spark Ads and creator marketplace integration.", category: "Channels", icon: Music2, installed: true, rating: 4.8, installs: "12.4K", accent: "#FFD400" },
  { id: "gpt4o", name: "GPT-4o Creative Engine", description: "Generate ad copy, headlines, and full creative briefs with GPT-4o multimodal AI.", category: "AI Models", icon: Sparkles, installed: true, rating: 4.9, installs: "28.1K", accent: "#22C55E" },
  { id: "whatsapp", name: "WhatsApp Business API", description: "Send transactional and marketing messages via WhatsApp with template approval flow.", category: "Channels", icon: MessageCircle, installed: false, rating: 4.6, installs: "8.9K", accent: "#22C55E" },
  { id: "heatmap", name: "Heatmap Analytics", description: "Visualize user attention on your landing pages with AI-powered heatmap predictions.", category: "Analytics", icon: Flame, installed: false, rating: 4.5, installs: "5.2K", accent: "#EF4444" },
  { id: "abtest", name: "Auto-A/B Testing", description: "Automatically test creative variants and route budget to winners in real-time.", category: "Automation", icon: FlaskConical, installed: true, rating: 4.7, installs: "15.8K", accent: "#3B82F6" },
  { id: "spy", name: "Competitor Spy", description: "Track competitor ad spend, creative changes, and landing page iterations.", category: "Analytics", icon: Eye, installed: false, rating: 4.3, installs: "3.1K", accent: "#A855F7" },
  { id: "voice", name: "Voice Ad Generator", description: "Create natural-sounding voiceover ads in 30+ languages with neural TTS.", category: "Creative Tools", icon: Mic, installed: false, rating: 4.4, installs: "2.7K", accent: "#FFD400" },
  { id: "influencer", name: "Influencer Matcher", description: "AI-matched influencer discovery based on audience overlap and brand safety scores.", category: "Creative Tools", icon: Users, installed: false, rating: 4.6, installs: "6.3K", accent: "#3B82F6" },
];

const FEATURED = [
  {
    id: "f1",
    name: "GPT-4o Creative Engine",
    tagline: "Generate entire campaigns in seconds",
    description: "Multimodal AI that writes copy, designs layouts, and produces creative briefs tailored to each channel.",
    icon: Sparkles,
    gradient: "from-accent/20 via-accent/5 to-transparent",
    badge: "Most Popular",
  },
  {
    id: "f2",
    name: "Auto-A/B Testing Suite",
    tagline: "Never guess again — let AI find winners",
    description: "Continuous multivariate testing with automatic budget routing to top-performing creative variants.",
    icon: FlaskConical,
    gradient: "from-info/20 via-info/5 to-transparent",
    badge: "Editor's Pick",
  },
];

export default function MarketplacePage() {
  const [category, setCategory] = useState("All");
  const [query, setQuery] = useState("");

  const filtered = ITEMS.filter(
    (i) =>
      (category === "All" || i.category === category) &&
      (i.name.toLowerCase().includes(query.toLowerCase()) ||
        i.description.toLowerCase().includes(query.toLowerCase())),
  );

  return (
    <div className="p-8 max-w-[1600px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-4xl tracking-wide text-text mb-1">
            Marketplace
          </h1>
          <p className="text-sm text-text-secondary">
            Extend CURV AI with channels, AI models, and creative tools.
          </p>
        </div>
        <div className="relative w-full lg:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search integrations..."
            className="input-field pl-10"
          />
        </div>
      </div>

      {/* Featured */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {FEATURED.map((f, i) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={f.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card3D glow className={cn("bg-gradient-to-br", f.gradient)}>
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-white/[0.06] flex items-center justify-center shrink-0">
                    <Icon className="w-7 h-7 text-accent" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-display text-xl font-semibold text-text">{f.name}</h3>
                      <span className="badge badge-accent">{f.badge}</span>
                    </div>
                    <p className="text-sm text-accent font-medium mb-2">{f.tagline}</p>
                    <p className="text-sm text-text-secondary leading-relaxed mb-4">
                      {f.description}
                    </p>
                    <button className="btn-primary text-sm">Install Now</button>
                  </div>
                </div>
              </Card3D>
            </motion.div>
          );
        })}
      </div>

      {/* Categories */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-1">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
              c === category
                ? "bg-accent text-white"
                : "bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08]",
            )}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((item, i) => {
          const Icon = item.icon;
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card3D className="h-full flex flex-col">
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{ backgroundColor: `${item.accent}15` }}
                  >
                    <Icon className="w-6 h-6" style={{ color: item.accent }} />
                  </div>
                  {item.installed && (
                    <span className="badge badge-success flex items-center gap-1">
                      <Check className="w-3 h-3" /> Installed
                    </span>
                  )}
                </div>
                <h3 className="font-display text-base font-medium text-text mb-1">{item.name}</h3>
                <span className="badge text-[10px] mb-3 self-start">{item.category}</span>
                <p className="text-xs text-text-secondary leading-relaxed flex-1 mb-4">
                  {item.description}
                </p>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-1">
                    <Star className="w-3.5 h-3.5 text-accent fill-accent" />
                    <span className="font-mono text-xs text-text">{item.rating}</span>
                    <span className="font-mono text-xs text-text-muted">· {item.installs}</span>
                  </div>
                </div>
                {item.installed ? (
                  <button className="btn-secondary text-xs flex items-center justify-center gap-1.5">
                    <Settings2 className="w-3.5 h-3.5" /> Configure
                  </button>
                ) : (
                  <button className="btn-primary text-xs flex items-center justify-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" /> Install
                  </button>
                )}
              </Card3D>
            </motion.div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <Card className="text-center py-12">
          <p className="text-text-secondary">No integrations found for "{query}"</p>
        </Card>
      )}
    </div>
  );
}
