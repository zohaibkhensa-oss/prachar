"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Image as ImageIcon, Wand2, Download, Edit3, Crop, Type,
  Palette, Layers, Sparkles, Plus, Search, Filter, Copy,
  Square, RectangleVertical, RectangleHorizontal, Expand,
  Eraser, Filter as FilterIcon, Star, Trash2, Check,
} from "lucide-react";

const CATEGORIES = ["Instagram Post", "Instagram Story", "Facebook Ad", "YouTube Thumbnail", "LinkedIn Post", "Twitter Card", "Pinterest Pin", "TikTok Cover", "Banner Ad", "Email Header", "Presentation", "Flyer", "Poster", "Business Card", "Logo", "Infographic"];

const TEMPLATES = CATEGORIES.map((cat, i) => ({
  id: i + 1,
  name: cat,
  dimensions: ["1080×1080", "1080×1920", "1200×628", "1280×720", "1200×627", "800×418", "1000×1500", "1080×1920", "728×90", "600×200", "1920×1080", "8.5×11", "24×36", "3.5×2", "500×500", "800×2000"][i],
  uses: Math.floor(Math.random() * 3000 + 100),
  gradient: ["from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10", "from-danger/20 to-info/10", "from-info/20 to-warning/10", "from-accent/20 to-info/10", "from-success/20 to-accent/10", "from-purple-500/20 to-info/10", "from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10", "from-danger/20 to-info/10", "from-info/20 to-warning/10", "from-accent/20 to-info/10"][i],
}));

const STYLES = ["Modern", "Minimal", "Bold", "Elegant", "Playful", "Corporate"];
const DESIGN_TYPES = ["Social Post", "Ad Creative", "Thumbnail", "Banner", "Story", "Presentation"];
const MAGIC_TOOLS = [
  { icon: Expand, name: "Magic Switch", desc: "Auto-resize for all platforms" },
  { icon: Type, name: "Magic Write", desc: "AI text generation" },
  { icon: Edit3, name: "Magic Edit", desc: "Select & describe changes" },
  { icon: Expand, name: "Magic Expand", desc: "Extend beyond borders" },
  { icon: Eraser, name: "Background Remover", desc: "One-click transparent BG" },
  { icon: Palette, name: "Brand Auto-Apply", desc: "Apply brand kit instantly" },
];

const MY_DESIGNS = Array.from({ length: 8 }, (_, i) => ({
  id: i + 1,
  name: ["Summer Sale Ad", "Product Launch Post", "Coffee Story", "Brand Banner", "Newsletter Header", "Event Flyer", "Logo Concept", "Infographic"][i],
  dimensions: ["1080×1080", "1080×1080", "1080×1920", "1920×1080", "1200×600", "8.5×11", "500×500", "800×2000"][i],
  edited: ["2h ago", "5h ago", "1d ago", "2d ago", "3d ago", "5d ago", "1w ago", "2w ago"][i],
  gradient: ["from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10", "from-danger/20 to-info/10", "from-info/20 to-warning/10", "from-accent/20 to-info/10", "from-success/20 to-accent/10"][i],
}));

const TABS = ["Templates", "AI Generator", "My Designs", "Brand Kit", "Magic Tools"];

export default function DesignPage() {
  const [tab, setTab] = useState("Templates");
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [designType, setDesignType] = useState("Social Post");
  const [style, setStyle] = useState("Modern");
  const [search, setSearch] = useState("");
  const [filterCat, setFilterCat] = useState("all");
  const [showEditor, setShowEditor] = useState(false);
  const [generatedDesigns, setGeneratedDesigns] = useState<Array<{ id: number; desc: string; gradient: string; confidence: number }>>([]);
  const [aiText, setAiText] = useState<string | null>(null);

  async function generate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setGeneratedDesigns([]);
    setAiText(null);

    // Call the real LLM to generate design concepts
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const { authedFetch } = await import("@/lib/auth");
      const res = await authedFetch(`${apiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: [{
            role: "user",
            content: `You are an AI design assistant for CURV AI, an AI advertising platform. The user wants to create a "${designType}" in a "${style}" style. Their prompt: "${prompt}". Generate 4 distinct design concepts. For each, provide a vivid visual description (colors, layout, typography, imagery) in 1-2 sentences. Format as a numbered list 1-4. Be specific and creative.`,
          }],
        }),
        signal: AbortSignal.timeout(20000),
      });
      if (res.ok) {
        const data = await res.json() as { reply: string };
        setAiText(data.reply);
      }
    } catch {
      setAiText(null);
    }

    // Simulate design generation with visual results
    const gradients = ["from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10", "from-danger/20 to-info/10", "from-purple-500/20 to-info/10"];
    const concepts = [
      `Design 1: ${style} ${designType} — ${prompt.slice(0, 40)}...`,
      `Design 2: ${style} ${designType} — alt layout`,
      `Design 3: ${style} ${designType} — bold variant`,
      `Design 4: ${style} ${designType} — minimal variant`,
    ];
    const newDesigns = concepts.map((desc, i) => ({
      id: Date.now() + i,
      desc,
      gradient: gradients[i % gradients.length]!,
      confidence: 82 + Math.floor(Math.random() * 15),
    }));

    setTimeout(() => {
      setGeneratedDesigns(newDesigns);
      setGenerating(false);
    }, 1500);
  }

  const filteredTemplates = TEMPLATES.filter(t => {
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterCat !== "all" && t.name !== filterCat) return false;
    return true;
  });

  return (
    <div className="space-y-6 relative">
      {generating && <AIThinkingOverlay message="AI is generating your designs..." />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Design Studio</h1>
          <p className="text-sm text-text-secondary mt-1">AI-powered design — better than Canva</p>
        </div>
        <span className="badge badge-accent"><Sparkles className="w-3 h-3" /> AI Powered</span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Designs Created" value={142} delta={28} icon={<ImageIcon className="w-4 h-4" />} accent="info" />
        <Metric label="Templates Used" value={67} delta={12} icon={<Layers className="w-4 h-4" />} accent="accent" />
        <Metric label="Brand Kits" value={3} delta={1} icon={<Palette className="w-4 h-4" />} accent="success" />
        <Metric label="Avg Design Time" value={2.5} suffix="min" delta={-1.2} icon={<Wand2 className="w-4 h-4" />} accent="accent" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg bg-bg-surface w-fit overflow-x-auto">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-md text-sm font-medium transition-all whitespace-nowrap", tab === t ? "bg-accent/10 text-accent" : "text-text-secondary hover:text-text")}>{t}</button>
        ))}
      </div>

      {/* Templates Tab */}
      {tab === "Templates" && (
        <>
          <div className="flex gap-2">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search templates..." className="input-field flex-1 max-w-xs" />
            <select value={filterCat} onChange={(e) => setFilterCat(e.target.value)} className="input-field w-48">
              <option value="all">All Categories</option>
              {CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filteredTemplates.map((t, i) => (
              <motion.div key={t.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.03 }}>
                <Card3D className="text-center">
                  <div className={cn("aspect-video rounded-lg bg-gradient-to-br flex items-center justify-center mb-3", t.gradient)}>
                    <ImageIcon className="w-8 h-8 text-white/20" />
                  </div>
                  <h3 className="font-display text-xs font-medium text-text mb-1">{t.name}</h3>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] text-text-muted">{t.dimensions}</span>
                    <span className="text-[10px] text-text-muted">{t.uses} uses</span>
                  </div>
                  <button className="btn-secondary text-xs w-full">Use Template</button>
                </Card3D>
              </motion.div>
            ))}
          </div>
        </>
      )}

      {/* AI Generator Tab */}
      {tab === "AI Generator" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card3D glow className="lg:col-span-1">
            <SectionHeader title="AI Design Generator" subtitle="Describe and create" />
            <div className="space-y-4">
              <div>
                <label className="label-field block mb-2">Prompt</label>
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe what you want to design... e.g., 'A modern Instagram ad for cold brew coffee with bold typography'" className="input-field h-24 resize-none" />
              </div>
              <div>
                <label className="label-field block mb-2">Design Type</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {DESIGN_TYPES.map(d => (
                    <button key={d} onClick={() => setDesignType(d)} className={cn("px-2 py-1.5 rounded-md text-xs border transition-all", designType === d ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary")}>{d}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Style</label>
                <div className="flex flex-wrap gap-1.5">
                  {STYLES.map(s => (
                    <button key={s} onClick={() => setStyle(s)} className={cn("px-2.5 py-1 rounded-full text-xs border transition-all", style === s ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary")}>{s}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Brand Kit</label>
                <select className="input-field"><option>Prachar Coffee</option><option>BeanThere</option><option>Custom</option></select>
              </div>
              <button onClick={generate} className="btn-primary w-full"><Wand2 className="w-4 h-4" />Generate Designs</button>
            </div>
          </Card3D>

          <div className="lg:col-span-2 space-y-4">
            {generatedDesigns.length === 0 && !generating && (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <Wand2 className="w-12 h-12 text-text-muted mb-3" />
                <p className="text-sm text-text-secondary">Enter a prompt and click Generate to create designs</p>
                <p className="text-xs text-text-muted mt-1">AI will generate 4 design concepts based on your description</p>
              </div>
            )}
            {aiText && (
              <Card className="border-l-2 border-l-accent/40">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-accent" />
                  <span className="text-sm font-medium text-text">AI Design Concepts</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">{aiText}</p>
              </Card>
            )}
            {generatedDesigns.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {generatedDesigns.map((d, i) => (
                  <motion.div key={d.id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.1 }}>
                    <Card3D className="overflow-hidden p-0">
                      <div className={cn("aspect-square bg-gradient-to-br flex items-center justify-center", d.gradient)}>
                        <ImageIcon className="w-8 h-8 text-white/20" />
                        <span className="absolute top-2 right-2 badge badge-accent text-[8px]">{d.confidence}%</span>
                      </div>
                      <div className="p-2.5">
                        <p className="text-[10px] text-text-secondary truncate mb-2">{d.desc}</p>
                        <div className="flex gap-1">
                          <button onClick={() => setShowEditor(true)} className="btn-secondary text-[10px] px-2 py-1 flex-1"><Edit3 className="w-2.5 h-2.5 inline mr-1" />Edit</button>
                          <button className="btn-secondary text-[10px] px-2 py-1 flex-1"><Download className="w-2.5 h-2.5 inline mr-1" />Save</button>
                        </div>
                      </div>
                    </Card3D>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* My Designs Tab */}
      {tab === "My Designs" && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {MY_DESIGNS.map((d, i) => (
            <motion.div key={d.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <Card3D className="overflow-hidden p-0">
                <div className={cn("aspect-video bg-gradient-to-br flex items-center justify-center", d.gradient)}>
                  <ImageIcon className="w-8 h-8 text-white/20" />
                </div>
                <div className="p-3">
                  <h4 className="text-xs font-medium text-text truncate mb-1">{d.name}</h4>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] text-text-muted">{d.dimensions}</span>
                    <span className="text-[10px] text-text-muted">{d.edited}</span>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => setShowEditor(true)} className="btn-secondary text-[10px] px-2 py-1 flex-1"><Edit3 className="w-2.5 h-2.5 inline mr-1" />Edit</button>
                    <button className="btn-secondary text-[10px] px-2 py-1"><Copy className="w-2.5 h-2.5" /></button>
                    <button className="btn-secondary text-[10px] px-2 py-1 text-danger"><Trash2 className="w-2.5 h-2.5" /></button>
                  </div>
                </div>
              </Card3D>
            </motion.div>
          ))}
        </div>
      )}

      {/* Brand Kit Tab */}
      {tab === "Brand Kit" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <SectionHeader title="Brand Colors" icon={<Palette className="w-4 h-4" />} />
            <div className="grid grid-cols-5 gap-2">
              {["#FFD400", "#0B0F14", "#22C55E", "#3B82F6", "#EF4444", "#A855F7", "#F97316", "#06B6D4", "#EC4899", "#84CC16"].map(c => (
                <div key={c} className="aspect-square rounded-lg border border-white/[0.1] flex flex-col items-center justify-center group cursor-pointer" style={{ background: c }}>
                  <span className="text-[8px] font-mono text-white/80 opacity-0 group-hover:opacity-100 transition-opacity">{c}</span>
                </div>
              ))}
            </div>
            <button className="btn-secondary text-xs mt-3 w-full"><Plus className="w-3 h-3 inline mr-1" />Add Color</button>
          </Card>
          <Card>
            <SectionHeader title="Fonts & Logo" icon={<Type className="w-4 h-4" />} />
            <div className="space-y-3">
              <div><label className="label-field block mb-1.5">Heading Font</label><div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-sm" style={{ fontFamily: "Space Grotesk" }}>Space Grotesk</div></div>
              <div><label className="label-field block mb-1.5">Body Font</label><div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-sm" style={{ fontFamily: "Inter" }}>Inter</div></div>
              <div><label className="label-field block mb-1.5">Logo</label><div className="w-full h-16 rounded-lg bg-white/[0.02] border border-dashed border-white/[0.08] flex items-center justify-center text-xs text-text-muted">Upload logo</div></div>
              <button className="btn-primary text-xs w-full"><Check className="w-3 h-3 inline mr-1" />Save Brand Kit</button>
            </div>
          </Card>
        </div>
      )}

      {/* Magic Tools Tab */}
      {tab === "Magic Tools" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {MAGIC_TOOLS.map((tool, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card3D className="group">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center group-hover:glow-ring transition-all">
                    <tool.icon className="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <h3 className="font-display text-sm font-medium text-text">{tool.name}</h3>
                    <p className="text-[10px] text-text-muted">{tool.desc}</p>
                  </div>
                </div>
                <button className="btn-secondary text-xs w-full">Try Now</button>
              </Card3D>
            </motion.div>
          ))}
        </div>
      )}

      {/* Editor Modal */}
      <AnimatePresence>
        {showEditor && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowEditor(false)} className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} onClick={(e) => e.stopPropagation()} className="w-full max-w-3xl">
              <Card3D glow>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-display text-lg font-semibold text-text">Design Editor</h3>
                  <button onClick={() => setShowEditor(false)} className="text-text-muted hover:text-text text-xl">✕</button>
                </div>
                {/* Canvas */}
                <div className="aspect-video rounded-xl bg-gradient-to-br from-bg-surface to-bg-card border border-white/[0.06] flex items-center justify-center mb-4">
                  <ImageIcon className="w-16 h-16 text-white/10" />
                </div>
                {/* Toolbar */}
                <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mb-4">
                  {[
                    { icon: Type, label: "Text" }, { icon: Crop, label: "Crop" }, { icon: ImageIcon, label: "Image" },
                    { icon: Layers, label: "Layers" }, { icon: Palette, label: "Color" }, { icon: FilterIcon, label: "Filter" },
                    { icon: Wand2, label: "AI" }, { icon: Download, label: "Export" },
                  ].map(tool => (
                    <button key={tool.label} className="flex flex-col items-center gap-1 p-2 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.04] transition-all">
                      <tool.icon className="w-4 h-4 text-text-secondary" />
                      <span className="text-[9px] text-text-muted">{tool.label}</span>
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button className="btn-secondary text-xs flex-1">Export PNG</button>
                  <button className="btn-secondary text-xs flex-1">Export JPG</button>
                  <button className="btn-secondary text-xs flex-1">Export PDF</button>
                  <button className="btn-primary text-xs flex-1"><Check className="w-3 h-3 inline mr-1" />Save</button>
                </div>
              </Card3D>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
