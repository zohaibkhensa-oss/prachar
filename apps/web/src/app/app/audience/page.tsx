"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapPin,
  Users,
  Tag,
  Languages,
  Search,
  Sparkles,
  Save,
  Send,
  X,
  Plus,
  Brain,
  TrendingUp,
} from "lucide-react";
import { Card, Card3D } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { PerformanceRing, ProgressBar } from "@/components/ui/charts";
import { cn } from "@/lib/utils";

const GEO_OPTIONS = ["India", "United States", "United Kingdom", "UAE", "Singapore", "Australia"];
const INTEREST_SUGGESTIONS = [
  "Coffee",
  "Specialty Coffee",
  "Espresso",
  "Cold Brew",
  "Home Brewing",
  "Cafe Culture",
  "Sustainability",
  "Premium Lifestyle",
];
const LANGUAGE_OPTIONS = ["English", "Hindi", "Marathi", "Tamil", "Kannada", "Bengali"];
const GENDERS = ["All", "Male", "Female", "Non-binary"];

const SAVED_AUDIENCES = [
  { id: "a1", name: "Mumbai Coffee Lovers", reach: "1.2M", score: 84 },
  { id: "a2", name: "Premium Skincare — Women 25-40", reach: "840K", score: 91 },
  { id: "a3", name: "Tech Early Adopters — Tier 1", reach: "2.1M", score: 76 },
  { id: "a4", name: "Festive Gifting Shoppers", reach: "3.4M", score: 69 },
];

const AI_SUGGESTIONS = [
  {
    title: "Add 'Cold Brew' to interests",
    reasoning: "Cold Brew searches spiked 34% in Mumbai this week. Adding it could expand reach by ~180K with high intent.",
    action: "Add interest",
    confidence: 82,
  },
  {
    title: "Narrow age to 22-38",
    reasoning: "Purchase data shows 78% of conversions come from this band. Tightening the range improves CPA by ~14%.",
    action: "Apply range",
    confidence: 89,
  },
  {
    title: "Add Marathi language",
    reasoning: "42% of your Mumbai audience prefers Marathi creative. Including it unlocks localized ad formats.",
    action: "Add language",
    confidence: 74,
  },
];

export default function AudiencePage() {
  const [geo, setGeo] = useState<string[]>(["India"]);
  const [ageRange, setAgeRange] = useState<[number, number]>([18, 45]);
  const [gender, setGender] = useState("All");
  const [interests, setInterests] = useState<string[]>(["Coffee", "Specialty Coffee", "Cafe Culture"]);
  const [interestInput, setInterestInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [keywords, setKeywords] = useState<string[]>(["buy coffee online", "best espresso beans"]);
  const [keywordInput, setKeywordInput] = useState("");
  const [languages, setLanguages] = useState<string[]>(["English", "Hindi"]);
  const [lookalikeSeed, setLookalikeSeed] = useState("");

  const reach = 1240000;
  const reachPct = Math.min((reach / 3000000) * 100, 100);

  function toggle<T>(arr: T[], set: (v: T[]) => void, val: T) {
    set(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);
  }

  const filteredSuggestions = INTEREST_SUGGESTIONS.filter(
    (s) => !interests.includes(s) && s.toLowerCase().includes(interestInput.toLowerCase()),
  );

  return (
    <div className="p-8 max-w-[1600px] mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display uppercase text-4xl tracking-wide text-text mb-1">
          Audience Builder
        </h1>
        <p className="text-sm text-text-secondary">
          Craft precision audiences with AI-assisted targeting.
        </p>
      </div>

      {/* Saved audiences */}
      <div className="mb-8">
        <SectionHeader title="Saved Audiences" subtitle="Your recent audience segments" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {SAVED_AUDIENCES.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <Card hover>
                <div className="flex items-start justify-between mb-3">
                  <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                    <Users className="w-4 h-4 text-accent" />
                  </div>
                  <span className="badge badge-accent">{a.score}</span>
                </div>
                <p className="font-display text-sm text-text leading-snug mb-2">{a.name}</p>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-text-secondary">Reach</span>
                  <span className="font-mono text-sm font-medium text-text">{a.reach}</span>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Main 3-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Config form */}
        <Card className="lg:col-span-4">
          <SectionHeader title="Configuration" subtitle="Define your audience" />
          <div className="space-y-6">
            {/* Geo */}
            <div>
              <label className="label-field flex items-center gap-1.5 mb-2">
                <MapPin className="w-3.5 h-3.5" /> Geography
              </label>
              <div className="flex flex-wrap gap-2">
                {geo.map((g) => (
                  <span key={g} className="badge badge-accent flex items-center gap-1.5">
                    {g}
                    <button onClick={() => toggle(geo, setGeo, g)}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {GEO_OPTIONS.filter((g) => !geo.includes(g)).map((g) => (
                  <button
                    key={g}
                    onClick={() => toggle(geo, setGeo, g)}
                    className="badge hover:bg-white/10 transition-colors text-text-secondary"
                  >
                    + {g}
                  </button>
                ))}
              </div>
            </div>

            {/* Age range */}
            <div>
              <label className="label-field mb-2 block">Age Range</label>
              <div className="flex items-center gap-3 mb-2">
                <span className="font-mono text-sm text-accent">{ageRange[0]}</span>
                <div className="flex-1 h-2 bg-white/[0.06] rounded-full relative">
                  <div
                    className="absolute h-2 bg-accent/30 rounded-full"
                    style={{
                      left: `${((ageRange[0] - 13) / (65 - 13)) * 100}%`,
                      right: `${100 - ((ageRange[1] - 13) / (65 - 13)) * 100}%`,
                    }}
                  />
                </div>
                <span className="font-mono text-sm text-accent">{ageRange[1]}</span>
              </div>
              <div className="flex gap-3">
                <input
                  type="range"
                  min={13}
                  max={65}
                  value={ageRange[0]}
                  onChange={(e) =>
                    setAgeRange([Math.min(Number(e.target.value), ageRange[1] - 1), ageRange[1]])
                  }
                  className="input-field !p-0 accent-accent"
                />
                <input
                  type="range"
                  min={13}
                  max={65}
                  value={ageRange[1]}
                  onChange={(e) =>
                    setAgeRange([ageRange[0], Math.max(Number(e.target.value), ageRange[0] + 1)])
                  }
                  className="input-field !p-0 accent-accent"
                />
              </div>
            </div>

            {/* Gender */}
            <div>
              <label className="label-field mb-2 block">Gender</label>
              <div className="grid grid-cols-4 gap-2">
                {GENDERS.map((g) => (
                  <button
                    key={g}
                    onClick={() => setGender(g)}
                    className={cn(
                      "px-3 py-2 rounded-lg text-xs font-medium transition-all",
                      g === gender
                        ? "bg-accent text-bg"
                        : "bg-white/[0.04] text-text-secondary hover:text-text",
                    )}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>

            {/* Interests */}
            <div className="relative">
              <label className="label-field flex items-center gap-1.5 mb-2">
                <Tag className="w-3.5 h-3.5" /> Interests
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {interests.map((it) => (
                  <span key={it} className="badge badge-accent flex items-center gap-1.5">
                    {it}
                    <button onClick={() => toggle(interests, setInterests, it)}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
              <div className="relative">
                <input
                  value={interestInput}
                  onChange={(e) => {
                    setInterestInput(e.target.value);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  placeholder="Add interest..."
                  className="input-field"
                />
                <AnimatePresence>
                  {showSuggestions && filteredSuggestions.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="absolute top-full mt-1 left-0 right-0 z-30 glass-strong rounded-lg p-1 border border-white/10"
                    >
                      {filteredSuggestions.slice(0, 5).map((s) => (
                        <button
                          key={s}
                          onClick={() => {
                            setInterests([...interests, s]);
                            setInterestInput("");
                            setShowSuggestions(false);
                          }}
                          className="w-full text-left px-3 py-2 rounded-md text-sm text-text-secondary hover:bg-white/5 hover:text-text transition-colors"
                        >
                          {s}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Keywords */}
            <div>
              <label className="label-field mb-2 block">Intents / Keywords</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {keywords.map((k) => (
                  <span key={k} className="badge flex items-center gap-1.5 bg-info/10 text-info">
                    {k}
                    <button onClick={() => toggle(keywords, setKeywords, k)}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
              <input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && keywordInput.trim()) {
                    setKeywords([...keywords, keywordInput.trim()]);
                    setKeywordInput("");
                  }
                }}
                placeholder="Type keyword + Enter"
                className="input-field"
              />
            </div>

            {/* Languages */}
            <div>
              <label className="label-field flex items-center gap-1.5 mb-2">
                <Languages className="w-3.5 h-3.5" /> Languages
              </label>
              <div className="flex flex-wrap gap-2">
                {languages.map((l) => (
                  <span key={l} className="badge badge-accent flex items-center gap-1.5">
                    {l}
                    <button onClick={() => toggle(languages, setLanguages, l)}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {LANGUAGE_OPTIONS.filter((l) => !languages.includes(l)).map((l) => (
                  <button
                    key={l}
                    onClick={() => toggle(languages, setLanguages, l)}
                    className="badge hover:bg-white/10 transition-colors text-text-secondary"
                  >
                    + {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Lookalike seed */}
            <div>
              <label className="label-field mb-2 block">Lookalike Seed (optional)</label>
              <input
                value={lookalikeSeed}
                onChange={(e) => setLookalikeSeed(e.target.value)}
                placeholder="e.g. past_purchasers.csv"
                className="input-field"
              />
            </div>
          </div>
        </Card>

        {/* Center: Preview */}
        <div className="lg:col-span-5">
          <Card3D glow>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="font-display text-xl font-semibold text-text">Audience Preview</h2>
                <p className="text-xs text-text-secondary mt-0.5">Live estimate as you configure</p>
              </div>
              <span className="badge badge-success">High Intent</span>
            </div>

            {/* Reach ring */}
            <div className="flex items-center gap-6 mb-6">
              <PerformanceRing
                value={reachPct}
                size={140}
                label={`${(reach / 1000000).toFixed(2)}M`}
                sublabel="Reach"
                accent="#FFD400"
              />
              <div className="flex-1 space-y-3">
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="label-field">Est. CPM</span>
                    <span className="font-mono text-sm text-text">₹142</span>
                  </div>
                  <ProgressBar value={62} accent="info" />
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="label-field">Est. CPA</span>
                    <span className="font-mono text-sm text-text">₹218</span>
                  </div>
                  <ProgressBar value={45} accent="success" />
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="label-field">Purchase Intent</span>
                    <span className="font-mono text-sm text-text">High</span>
                  </div>
                  <ProgressBar value={84} accent="accent" />
                </div>
              </div>
            </div>

            {/* Demographics */}
            <div className="mb-6">
              <p className="label-field mb-3">Demographics Breakdown</p>
              <div className="space-y-2.5">
                {[
                  { label: "18-24", pct: 22 },
                  { label: "25-34", pct: 41 },
                  { label: "35-44", pct: 27 },
                  { label: "45+", pct: 10 },
                ].map((d) => (
                  <div key={d.label} className="flex items-center gap-3">
                    <span className="font-mono text-xs text-text-secondary w-12">{d.label}</span>
                    <div className="flex-1 h-2 bg-white/[0.06] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${d.pct}%` }}
                        transition={{ duration: 0.8 }}
                        className="h-full bg-gradient-to-r from-accent/60 to-accent rounded-full"
                      />
                    </div>
                    <span className="font-mono text-xs text-text w-8 text-right">{d.pct}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Interest cloud */}
            <div className="mb-6">
              <p className="label-field mb-3">Interest Cloud</p>
              <div className="flex flex-wrap gap-2 items-center">
                {interests.map((it, i) => (
                  <motion.span
                    key={it}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.05 }}
                    className={cn(
                      "font-display font-medium text-text",
                      i % 3 === 0 ? "text-xl" : i % 3 === 1 ? "text-base" : "text-sm",
                    )}
                    style={{ opacity: 0.6 + (i % 3) * 0.15 }}
                  >
                    {it}
                  </motion.span>
                ))}
              </div>
            </div>

            {/* AI insight */}
            <div className="glass rounded-lg p-4 border-l-2 border-l-accent/40">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="w-4 h-4 text-accent" />
                <span className="font-mono text-xs text-accent uppercase tracking-wider">
                  AI Insight
                </span>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed">
                This audience has <span className="text-accent">high purchase intent</span> for
                coffee products in Mumbai metro. 84% match your top-converting customer profile.
                Expect ~2.3x higher CTR than baseline.
              </p>
            </div>
          </Card3D>
        </div>

        {/* Right: AI Suggestions */}
        <div className="lg:col-span-3">
          <SectionHeader title="AI Suggestions" />
          <div className="space-y-3">
            {AI_SUGGESTIONS.map((s, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <AIRecommendation
                  title={s.title}
                  reasoning={s.reasoning}
                  action={s.action}
                  confidence={s.confidence}
                  onAccept={() => {}}
                  onDismiss={() => {}}
                />
              </motion.div>
            ))}
          </div>

          <div className="glass rounded-lg p-4 mt-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-success" />
              <span className="font-mono text-xs text-success uppercase tracking-wider">
                Tip
              </span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed">
              Audiences with 3-5 interests and 2 languages consistently outperform over-broad
              segments by 31%.
            </p>
          </div>
          </div>
      </div>

      {/* Bottom actions */}
      <div className="flex items-center justify-end gap-3 mt-8">
        <button className="btn-secondary flex items-center gap-2">
          <Save className="w-4 h-4" />
          Save Audience
        </button>
        <button className="btn-primary flex items-center gap-2">
          <Send className="w-4 h-4" />
          Push to Campaign
        </button>
      </div>
    </div>
  );
}
