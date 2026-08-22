"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Wand2,
  Check,
  X,
  Pencil,
  Copy,
  Image as ImageIcon,
  Type,
  History,
  Megaphone,
  TrendingUp,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
} from "lucide-react";
import { Card3D, Card, GlassCard } from "@/components/ui/card-3d";
import { MetricMini } from "@/components/ui/metric";
import { AIStatusBlock, AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { Sparkline, ProgressBar } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/* ────────────────────────────── Mock data ────────────────────────────── */

const BRANDS = [
  { id: "aurora", name: "Aurora Skincare", tone: "Luxury · Calm" },
  { id: "nitro", name: "Nitro Coffee Co.", tone: "Bold · Energetic" },
  { id: "lumen", name: "Lumen Finance", tone: "Trustworthy · Clear" },
];

const CHANNELS = ["Google", "Meta", "TikTok", "YouTube", "Instagram", "LinkedIn", "X", "Pinterest"];

const TONES = ["Bold", "Playful", "Luxury", "Trustworthy", "Urgent", "Inspiring", "Witty", "Minimal"];

type Creative = {
  id: string;
  variant: string;
  channel: string;
  headline: string;
  copy: string;
  confidence: number;
  ctr: number;
  status: "new" | "approved" | "rejected";
};

const MOCK_CREATIVES: Creative[] = [
  {
    id: "c1",
    variant: "A",
    channel: "Google",
    headline: "Glow that lasts 48 hours — not 48 minutes",
    copy: "Aurora's hyaluronic serum locks in moisture for 2 full days. Clinically tested. Dermatologist loved. Try it risk-free for 30 nights.",
    confidence: 94,
    ctr: 4.2,
    status: "new",
  },
  {
    id: "c2",
    variant: "B",
    channel: "Meta",
    headline: "Your skin called. It wants Aurora.",
    copy: "72% saw visible glow in 7 days. The serum everyone's whispering about — now shipped free across India. Limited launch batch.",
    confidence: 88,
    ctr: 3.8,
    status: "new",
  },
  {
    id: "c3",
    variant: "C",
    channel: "TikTok",
    headline: "POV: you wake up glowing ✨",
    copy: "3 drops. 7 days. One serum that broke the internet. Aurora is the only thing standing between you and your best skin era.",
    confidence: 91,
    ctr: 5.1,
    status: "new",
  },
  {
    id: "c4",
    variant: "A",
    channel: "YouTube",
    headline: "The science of glow, simplified",
    copy: "Hyaluronic acid + niacinamide, in a formula that actually works. Watch the 60-second breakdown from our lead chemist.",
    confidence: 82,
    ctr: 2.9,
    status: "new",
  },
  {
    id: "c5",
    variant: "B",
    channel: "Instagram",
    headline: "Glow without the filter",
    copy: "Real skin. Real results. 50,000+ five-star reviews can't be wrong. Aurora — because your skin deserves the truth.",
    confidence: 86,
    ctr: 3.4,
    status: "new",
  },
  {
    id: "c6",
    variant: "C",
    channel: "LinkedIn",
    headline: "Skincare, backed by data",
    copy: "Aurora's R&D team published 12 peer-reviewed studies this year. Our serum isn't hype — it's evidence. Trusted by 200+ clinics.",
    confidence: 79,
    ctr: 2.1,
    status: "new",
  },
];

const VARIANT_HISTORY = [
  { variant: "Variant A", ctr: [3.1, 3.4, 3.8, 4.0, 4.2, 4.1, 4.2], avg: 3.8 },
  { variant: "Variant B", ctr: [2.8, 3.0, 3.2, 3.5, 3.6, 3.7, 3.8], avg: 3.4 },
  { variant: "Variant C", ctr: [4.2, 4.5, 4.8, 4.9, 5.0, 5.1, 5.1], avg: 4.8 },
];

const DO_LIST = ["Lead with a benefit", "Use sensory language", "Include a proof point", "End with a soft CTA"];
const DONT_LIST = ["Avoid jargon", "No fear-mongering", "Don't over-claim results", "Avoid exclamation overload"];

const TONE_SLIDERS = [
  { label: "Formal", value: 30 },
  { label: "Playful", value: 70 },
  { label: "Urgent", value: 45 },
  { label: "Technical", value: 25 },
];

const TABS = [
  { id: "ads", label: "Generated Ads", icon: Megaphone },
  { id: "images", label: "Generated Images", icon: ImageIcon },
  { id: "headlines", label: "Headlines", icon: Type },
  { id: "history", label: "History", icon: History },
];

const CHANNEL_COLORS: Record<string, string> = {
  Google: "badge-info",
  Meta: "badge-accent",
  TikTok: "badge-success",
  YouTube: "badge-danger",
  Instagram: "badge-accent",
  LinkedIn: "badge-info",
  X: "badge-neutral",
  Pinterest: "badge-danger",
};

/* ────────────────────────────── Page ────────────────────────────── */

export default function CreativeAIPage() {
  const [prompt, setPrompt] = useState(
    "Launch campaign for Aurora's new hyaluronic serum. Target audience: women 25-40, urban India. Emphasize long-lasting glow and clinical proof.",
  );
  const [brand, setBrand] = useState("aurora");
  const [selectedChannels, setSelectedChannels] = useState<string[]>(["Google", "Meta", "TikTok"]);
  const [tone, setTone] = useState("Luxury");
  const [tab, setTab] = useState("ads");
  const [generating, setGenerating] = useState(false);
  const [creatives, setCreatives] = useState<Creative[]>(MOCK_CREATIVES);

  function toggleChannel(ch: string) {
    setSelectedChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch],
    );
  }

  function generate() {
    setGenerating(true);
    setTimeout(() => {
      setGenerating(false);
      // refresh creatives with slightly varied confidence for realism
      setCreatives(
        MOCK_CREATIVES.map((c) => ({
          ...c,
          confidence: Math.min(99, c.confidence + Math.floor(Math.random() * 4 - 1)),
          status: "new" as const,
        })),
      );
    }, 2200);
  }

  function act(id: string, action: "approved" | "rejected") {
    setCreatives((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status: action } : c)),
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-text flex items-center gap-3">
            <span className="text-gradient-accent">Creative AI</span>
            <Sparkles className="w-6 h-6 text-accent" />
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Generate, test, and ship high-performing ad creative in minutes.
          </p>
        </div>
        <AIStatusBlock status="idle" label="AI Engine Ready" detail="GPT-4o · Brand-tuned" confidence={96} />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-white/[0.04] pb-px overflow-x-auto scrollbar-none">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-all relative whitespace-nowrap",
              tab === t.id ? "text-accent" : "text-text-secondary hover:text-text",
            )}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
            {tab === t.id && (
              <motion.div
                layoutId="creative-tab"
                className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent rounded-full"
              />
            )}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_300px] gap-6">
        {/* ─── Left panel: controls ─── */}
        <div className="space-y-4">
          <Card3D className="space-y-4" glow>
            <div>
              <label className="label-field mb-2 block">Prompt</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={6}
                className="input-field resize-none w-full text-sm leading-relaxed"
                placeholder="Describe the ad you want the AI to generate..."
              />
              <div className="flex justify-between mt-1.5">
                <span className="font-mono text-[10px] text-text-muted">{prompt.length} chars</span>
                <span className="font-mono text-[10px] text-text-muted">~2.1k tokens</span>
              </div>
            </div>

            <div>
              <label className="label-field mb-2 block">Brand</label>
              <div className="space-y-1.5">
                {BRANDS.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => setBrand(b.id)}
                    className={cn(
                      "w-full flex items-center justify-between p-2.5 rounded-lg text-left transition-all",
                      brand === b.id
                        ? "bg-accent/10 border border-accent/30"
                        : "border border-white/[0.04] hover:bg-white/[0.03]",
                    )}
                  >
                    <div>
                      <div className="text-sm text-text font-medium">{b.name}</div>
                      <div className="text-[10px] text-text-muted font-mono">{b.tone}</div>
                    </div>
                    {brand === b.id && <Check className="w-4 h-4 text-accent" />}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="label-field mb-2 block">Channels</label>
              <div className="flex flex-wrap gap-1.5">
                {CHANNELS.map((ch) => (
                  <button
                    key={ch}
                    onClick={() => toggleChannel(ch)}
                    className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-medium transition-all",
                      selectedChannels.includes(ch)
                        ? "bg-accent text-white"
                        : "bg-white/[0.04] text-text-secondary hover:text-text",
                    )}
                  >
                    {ch}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="label-field mb-2 block">Tone</label>
              <div className="flex flex-wrap gap-1.5">
                {TONES.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTone(t)}
                    className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-medium transition-all",
                      tone === t
                        ? "bg-info text-white"
                        : "bg-white/[0.04] text-text-secondary hover:text-text",
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={generate}
              disabled={generating}
              className="btn-primary w-full group glow-ring flex items-center justify-center gap-2"
            >
              <Wand2 className="w-4 h-4" />
              {generating ? "Generating..." : "Generate Creatives"}
            </button>
          </Card3D>

          <Card>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-accent" />
              <span className="font-display text-sm font-medium text-text">This Session</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricMini label="Generated" value={142} accent="accent" />
              <MetricMini label="Approved" value={38} accent="success" />
              <MetricMini label="Avg CTR" value={4.2} format="percent" accent="info" />
              <MetricMini label="Avg Conf." value={88} format="percent" accent="default" />
            </div>
          </Card>
        </div>

        {/* ─── Center: results ─── */}
        <div className="relative min-h-[600px]">
          <AnimatePresence>
            {generating && (
              <AIThinkingOverlay message="AI is generating creatives..." />
            )}
          </AnimatePresence>

          <div className="flex items-center justify-between mb-4">
            <span className="font-mono text-xs text-text-muted">
              {creatives.length} variants · {selectedChannels.length} channels
            </span>
            <button
              onClick={generate}
              className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Regenerate
            </button>
          </div>

          <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AnimatePresence mode="popLayout">
              {creatives.map((c, i) => (
                <motion.div
                  key={c.id}
                  layout
                  initial={{ opacity: 0, y: 20, rotateX: -10 }}
                  animate={{ opacity: 1, y: 0, rotateX: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ delay: i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                >
                  <Card3D className="h-full flex flex-col" glow={c.status === "approved"}>
                    {/* Top row: variant + channel + confidence */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="badge badge-neutral font-mono">Variant {c.variant}</span>
                        <span className={cn("badge", CHANNEL_COLORS[c.channel])}>{c.channel}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="relative w-7 h-7">
                          <svg width="28" height="28" className="-rotate-90">
                            <circle cx="14" cy="14" r="11" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                            <circle
                              cx="14"
                              cy="14"
                              r="11"
                              fill="none"
                              stroke={c.confidence >= 90 ? "#22C55E" : c.confidence >= 80 ? "#FFD400" : "#EF4444"}
                              strokeWidth="3"
                              strokeLinecap="round"
                              strokeDasharray={2 * Math.PI * 11}
                              strokeDashoffset={2 * Math.PI * 11 * (1 - c.confidence / 100)}
                            />
                          </svg>
                        </div>
                        <span className="font-mono text-[10px] text-text-muted">{c.confidence}%</span>
                      </div>
                    </div>

                    {/* Headline */}
                    <h3 className="font-display text-lg font-semibold text-text leading-snug mb-2">
                      {c.headline}
                    </h3>

                    {/* Copy */}
                    <p className="text-sm text-text-secondary leading-relaxed flex-1 mb-4">
                      {c.copy}
                    </p>

                    {/* CTR mini */}
                    <div className="flex items-center justify-between mb-3 pb-3 border-b border-white/[0.04]">
                      <span className="label-field">Predicted CTR</span>
                      <span className="font-mono text-sm font-medium text-success">{c.ctr.toFixed(1)}%</span>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => act(c.id, "approved")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-all",
                          c.status === "approved"
                            ? "bg-success/20 text-success border border-success/40"
                            : "bg-white/[0.04] text-text-secondary hover:text-success hover:bg-success/10",
                        )}
                      >
                        <Check className="w-3.5 h-3.5" /> Approve
                      </button>
                      <button
                        onClick={() => act(c.id, "rejected")}
                        className={cn(
                          "flex items-center justify-center w-9 h-9 rounded-lg transition-all",
                          c.status === "rejected"
                            ? "bg-danger/20 text-danger border border-danger/40"
                            : "bg-white/[0.04] text-text-secondary hover:text-danger hover:bg-danger/10",
                        )}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      <button className="flex items-center justify-center w-9 h-9 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08] transition-all">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => navigator.clipboard?.writeText(`${c.headline}\n\n${c.copy}`)}
                        className="flex items-center justify-center w-9 h-9 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08] transition-all"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </Card3D>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>

          {/* Variant Performance */}
          <div className="mt-8">
            <SectionHeader
              title="Variant Performance"
              subtitle="Historical CTR of past variants across all channels"
              icon={<TrendingUp className="w-4 h-4" />}
            />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {VARIANT_HISTORY.map((v, i) => (
                <Card3D key={v.variant}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-display text-sm font-medium text-text">{v.variant}</span>
                    <span className="font-mono text-xs text-success">{v.avg.toFixed(1)}% avg</span>
                  </div>
                  <Sparkline data={v.ctr} width={240} height={40} color={i === 2 ? "#22C55E" : "#FFD400"} className="w-full" />
                  <div className="flex items-center justify-between mt-3">
                    <span className="label-field">7-day trend</span>
                    <div className="flex items-center gap-1 text-success">
                      <TrendingUp className="w-3 h-3" />
                      <span className="font-mono text-xs">+{(((v.ctr[6] ?? 0) - (v.ctr[0] ?? 1)) / (v.ctr[0] ?? 1) * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </Card3D>
              ))}
            </div>
          </div>
        </div>

        {/* ─── Right panel: Brand Voice ─── */}
        <div className="space-y-4">
          <Card3D glow>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent" />
              </div>
              <div>
                <div className="font-display text-sm font-medium text-text">Brand Voice</div>
                <div className="text-[10px] text-text-muted font-mono">Aurora Skincare</div>
              </div>
            </div>

            {/* Tone sliders */}
            <div className="space-y-3">
              {TONE_SLIDERS.map((s) => (
                <div key={s.label}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-text-secondary">{s.label}</span>
                    <span className="font-mono text-[10px] text-text-muted">{s.value}</span>
                  </div>
                  <ProgressBar value={s.value} accent="accent" />
                </div>
              ))}
            </div>
          </Card3D>

          <Card>
            <div className="flex items-center gap-2 mb-3">
              <ThumbsUp className="w-4 h-4 text-success" />
              <span className="font-display text-sm font-medium text-text">Do</span>
            </div>
            <ul className="space-y-2">
              {DO_LIST.map((d) => (
                <li key={d} className="flex items-start gap-2 text-xs text-text-secondary">
                  <Check className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                  {d}
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <div className="flex items-center gap-2 mb-3">
              <ThumbsDown className="w-4 h-4 text-danger" />
              <span className="font-display text-sm font-medium text-text">Don't</span>
            </div>
            <ul className="space-y-2">
              {DONT_LIST.map((d) => (
                <li key={d} className="flex items-start gap-2 text-xs text-text-secondary">
                  <X className="w-3.5 h-3.5 text-danger shrink-0 mt-0.5" />
                  {d}
                </li>
              ))}
            </ul>
          </Card>

          <GlassCard>
            <div className="flex items-center gap-2 mb-3">
              <History className="w-4 h-4 text-info" />
              <span className="font-display text-sm font-medium text-text">Historical Performance</span>
            </div>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">Best CTR</span>
                  <span className="font-mono text-xs text-success">5.1%</span>
                </div>
                <ProgressBar value={85} accent="success" />
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">Approval Rate</span>
                  <span className="font-mono text-xs text-accent">72%</span>
                </div>
                <ProgressBar value={72} accent="accent" />
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">Brand Match</span>
                  <span className="font-mono text-xs text-info">91%</span>
                </div>
                <ProgressBar value={91} accent="info" />
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
