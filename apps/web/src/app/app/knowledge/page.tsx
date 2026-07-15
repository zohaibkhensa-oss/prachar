"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  BookOpen,
  Rocket,
  Eye,
  Repeat,
  ArrowRight,
  Clock,
  User,
  Sparkles,
  Send,
  Zap,
  BarChart3,
  Code2,
  Lightbulb,
} from "lucide-react";
import { Card, Card3D, GlassCard } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { id: "getting-started", label: "Getting Started", icon: Rocket },
  { id: "channels", label: "Channels", icon: Zap },
  { id: "campaigns", label: "Campaigns", icon: BookOpen },
  { id: "creative-ai", label: "Creative AI", icon: Sparkles },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "api", label: "API Reference", icon: Code2 },
  { id: "best-practices", label: "Best Practices", icon: Lightbulb },
];

const FEATURED = [
  {
    id: "f1",
    title: "Getting Started with AI Advertising",
    excerpt: "Learn how PRACHAR's AI engine optimizes your campaigns end-to-end — from audience discovery to creative generation.",
    category: "Getting Started",
    readTime: "8 min",
    author: "Aarav Mehta",
    gradient: "from-accent/30 via-accent/5 to-transparent",
    icon: Rocket,
  },
  {
    id: "f2",
    title: "Understanding Visibility Score",
    excerpt: "Deep dive into how PRACHAR calculates your brand's visibility score across channels and what moves the needle.",
    category: "Analytics",
    readTime: "12 min",
    author: "Priya Sharma",
    gradient: "from-info/30 via-info/5 to-transparent",
    icon: Eye,
  },
  {
    id: "f3",
    title: "Mastering the Weekly Loop",
    excerpt: "The weekly optimization loop is PRACHAR's secret weapon. Here's how to set it up and get the most out of it.",
    category: "Best Practices",
    readTime: "15 min",
    author: "Rohan Kapoor",
    gradient: "from-success/30 via-success/5 to-transparent",
    icon: Repeat,
  },
];

const ARTICLES = [
  { id: "a1", title: "Connecting Your First Ad Channel", excerpt: "Step-by-step guide to linking Google, Meta, and Amazon ad accounts.", category: "Channels", readTime: "5 min", author: "Sara Khan" },
  { id: "a2", title: "Writing Prompts for Creative AI", excerpt: "Best practices for crafting prompts that generate high-converting ad creative.", category: "Creative AI", readTime: "7 min", author: "Aarav Mehta" },
  { id: "a3", title: "Setting CPA Targets by Channel", excerpt: "How to configure max CPA per channel and let AI manage within bounds.", category: "Campaigns", readTime: "6 min", author: "Priya Sharma" },
  { id: "a4", title: "Reading the Performance Funnel", excerpt: "Understand each stage of the funnel and where to optimize for max impact.", category: "Analytics", readTime: "9 min", author: "Rohan Kapoor" },
  { id: "a5", title: "Webhooks & Real-time Events", excerpt: "Integrate PRACHAR events into your stack with webhook subscriptions.", category: "API Reference", readTime: "11 min", author: "Vikram Nair" },
  { id: "a6", title: "Audience Lookalike Seeds Explained", excerpt: "How lookalike modeling works and which seed audiences perform best.", category: "Best Practices", readTime: "8 min", author: "Sara Khan" },
  { id: "a7", title: "Multi-region Campaign Strategy", excerpt: "Run coordinated campaigns across India, SEA, and MENA with localized creative.", category: "Campaigns", readTime: "13 min", author: "Aarav Mehta" },
  { id: "a8", title: "Budget Pacing & AI Reallocation", excerpt: "How PRACHAR paces spend and reallocates budget across channels automatically.", category: "Best Practices", readTime: "10 min", author: "Priya Sharma" },
];

const CATEGORY_COLORS: Record<string, string> = {
  "Getting Started": "badge-accent",
  Channels: "badge",
  Campaigns: "badge",
  "Creative AI": "badge-accent",
  Analytics: "badge",
  "API Reference": "badge",
  "Best Practices": "badge",
};

export default function KnowledgePage() {
  const [activeCat, setActiveCat] = useState("getting-started");
  const [query, setQuery] = useState("");
  const [aiInput, setAiInput] = useState("");

  const filteredArticles = ARTICLES.filter(
    (a) =>
      a.title.toLowerCase().includes(query.toLowerCase()) ||
      a.excerpt.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="p-8 max-w-[1600px] mx-auto animate-fade-in pb-32">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-4xl tracking-wide text-text mb-1">
            Knowledge Base
          </h1>
          <p className="text-sm text-text-secondary">
            Guides, tutorials, and references to master PRACHAR.
          </p>
        </div>
        <div className="relative w-full lg:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search articles..."
            className="input-field pl-10"
          />
        </div>
      </div>

      {/* Featured guides */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        {FEATURED.map((f, i) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={f.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card3D glow className={cn("bg-gradient-to-br h-full", f.gradient)}>
                <div className="mb-6">
                  <div className="w-12 h-12 rounded-xl bg-white/[0.08] flex items-center justify-center mb-4">
                    <Icon className="w-6 h-6 text-text" />
                  </div>
                  <span className={cn("badge mb-3", CATEGORY_COLORS[f.category])}>{f.category}</span>
                  <h3 className="font-display text-xl font-semibold text-text leading-snug mb-2">
                    {f.title}
                  </h3>
                  <p className="text-sm text-text-secondary leading-relaxed">{f.excerpt}</p>
                </div>
                <div className="flex items-center justify-between pt-4 border-t border-white/[0.06]">
                  <div className="flex items-center gap-3 text-xs text-text-muted font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {f.readTime}
                    </span>
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" /> {f.author}
                    </span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-accent" />
                </div>
              </Card3D>
            </motion.div>
          );
        })}
      </div>

      {/* Main content with sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <Card>
            <p className="label-field mb-3">Categories</p>
            <div className="space-y-1">
              {CATEGORIES.map((c) => {
                const Icon = c.icon;
                return (
                  <button
                    key={c.id}
                    onClick={() => setActiveCat(c.id)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all text-left",
                      activeCat === c.id
                        ? "bg-accent/10 text-accent"
                        : "text-text-secondary hover:text-text hover:bg-white/[0.03]",
                    )}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    {c.label}
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Articles grid */}
        <div className="lg:col-span-3">
          <SectionHeader
            title="All Articles"
            subtitle={`${filteredArticles.length} articles`}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filteredArticles.map((a, i) => (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card hover className="h-full group cursor-pointer">
                  <div className="flex items-center gap-2 mb-3">
                    <span className={cn("badge text-[10px]", CATEGORY_COLORS[a.category])}>
                      {a.category}
                    </span>
                    <span className="font-mono text-[10px] text-text-muted flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {a.readTime}
                    </span>
                  </div>
                  <h3 className="font-display text-base font-medium text-text leading-snug mb-2 group-hover:text-accent transition-colors">
                    {a.title}
                  </h3>
                  <p className="text-xs text-text-secondary leading-relaxed mb-4">{a.excerpt}</p>
                  <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
                    <span className="font-mono text-[10px] text-text-muted flex items-center gap-1">
                      <User className="w-3 h-3" /> {a.author}
                    </span>
                    <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>

          {filteredArticles.length === 0 && (
            <Card className="text-center py-12">
              <p className="text-text-secondary">No articles found for "{query}"</p>
            </Card>
          )}
        </div>
      </div>

      {/* AI Assistant floating card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="fixed bottom-6 right-6 z-40 w-[380px] max-w-[calc(100vw-3rem)]"
      >
        <GlassCard className="glass-strong border border-accent/20 glow-ring">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <div>
              <p className="font-display text-sm font-medium text-text">AI Assistant</p>
              <p className="text-[10px] text-text-muted">Ask anything about PRACHAR</p>
            </div>
          </div>
          <div className="relative">
            <input
              value={aiInput}
              onChange={(e) => setAiInput(e.target.value)}
              placeholder="How do I set up a lookalike audience?"
              className="input-field pr-10"
            />
            <button className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-lg bg-accent flex items-center justify-center hover:scale-105 transition-transform">
              <Send className="w-3.5 h-3.5 text-bg" />
            </button>
          </div>
        </GlassCard>
      </motion.div>
    </div>
  );
}
