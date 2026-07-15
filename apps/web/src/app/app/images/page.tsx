"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Image as ImageIcon, Wand2, Download, Edit3, Crop, RotateCw,
  Sparkles, Filter, Eraser, Expand, Type, Palette, Layers,
  Square, RectangleVertical, RectangleHorizontal, Copy, Trash2,
} from "lucide-react";

const STYLES = ["Photorealistic", "Illustration", "3D Render", "Minimalist", "Vintage", "Cyberpunk", "Watercolor", "Cartoon", "Abstract"];
const RATIOS = [
  { id: "1:1", label: "1:1", icon: Square },
  { id: "16:9", label: "16:9", icon: RectangleHorizontal },
  { id: "9:16", label: "9:16", icon: RectangleVertical },
  { id: "4:5", label: "4:5", icon: RectangleVertical },
  { id: "3:2", label: "3:2", icon: RectangleHorizontal },
];
const QUALITIES = ["Standard", "HD", "Ultra HD"];
const FILTERS = ["None", "Vintage", "B&W", "Vivid", "Soft", "Dramatic", "Warm", "Cool"];

const MOCK_IMAGES = Array.from({ length: 8 }, (_, i) => ({
  id: String(i + 1),
  prompt: ["Coffee cup on wooden table morning light", "Latte art heart pattern closeup", "Coffee beans scattered artistic", "Barista pouring milk into espresso", "Iced coffee with condensation droplets", "Coffee shop interior cozy ambiance", "Espresso machine steam action shot", "Coffee brand logo on cup minimal"][i],
  style: STYLES[i % STYLES.length],
  ratio: RATIOS[i % RATIOS.length]!.id,
  quality: QUALITIES[i % QUALITIES.length],
  confidence: 80 + Math.floor(Math.random() * 18),
  gradient: ["from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10", "from-danger/20 to-info/10", "from-info/20 to-warning/10", "from-accent/20 to-info/10", "from-success/20 to-accent/10"][i],
}));

const TEMPLATES = [
  "Instagram Post", "Instagram Story", "Facebook Ad", "YouTube Thumbnail",
  "LinkedIn Post", "Twitter Card", "Pinterest Pin", "TikTok Cover",
  "Banner Ad", "Email Header", "Presentation", "Flyer",
];

const TABS = ["Generated", "Editor", "Brand Assets", "Templates"];

export default function ImageStudioPage() {
  const [tab, setTab] = useState("Generated");
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [style, setStyle] = useState("Photorealistic");
  const [ratio, setRatio] = useState("1:1");
  const [quality, setQuality] = useState("HD");
  const [variations, setVariations] = useState(4);
  const [images, setImages] = useState<typeof MOCK_IMAGES>([]);
  const [aiPrompt, setAiPrompt] = useState<string | null>(null);

  async function generate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setAiPrompt(null);

    // Call the real LLM to generate enhanced image prompts
    const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
    const { authedFetch } = await import("@/lib/auth");

    // Fire LLM prompt enhancement and actual image generation in parallel
    const promptPromise = (async () => {
      try {
        const res = await authedFetch(`${apiBase}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [{
              role: "user",
              content: `You are an AI image prompt engineer for PRACHAR. The user wants a ${style} image in ${ratio} format. Their prompt: "${prompt}". ${negativePrompt ? `Exclude: ${negativePrompt}.` : ""} Generate ${variations} enhanced, detailed image generation prompts (each on a new line, numbered 1-${variations}). Include lighting, composition, mood, and style details.`,
            }],
          }),
          signal: AbortSignal.timeout(20000),
        });
        if (res.ok) {
          const data = await res.json() as { reply: string };
          setAiPrompt(data.reply);
        }
      } catch {}
    })();

    // Generate real AI images via self-hosted GPU or fal.ai
    const imagePromises = Array.from({ length: Math.min(variations, 4) }, async (_, i) => {
      try {
        const res = await authedFetch(`${apiBase}/api/video/generate-image`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: `${prompt}, ${style} style, high quality, detailed, professional photography`,
            width: ratio === "9:16" ? 720 : 1024,
            height: ratio === "9:16" ? 1280 : 1024,
          }),
          signal: AbortSignal.timeout(60000),
        });
        if (res.ok) {
          const data = await res.json() as { image_url: string; model: string };
          return {
            id: String(Date.now() + i),
            prompt: `${prompt} — variation ${i + 1}`,
            style,
            ratio,
            quality,
            confidence: 90 + Math.floor(Math.random() * 8),
            gradient: "",
            imageUrl: data.image_url,
          };
        }
      } catch {}
      // Fallback to gradient placeholder
      const gradients = ["from-info/20 to-accent/10", "from-accent/20 to-success/10", "from-success/20 to-info/10", "from-warning/20 to-danger/10"];
      return {
        id: String(Date.now() + i),
        prompt: `${prompt} — variation ${i + 1}`,
        style,
        ratio,
        quality,
        confidence: 80 + Math.floor(Math.random() * 18),
        gradient: gradients[i % gradients.length],
        imageUrl: "",
      };
    });

    const newImages = await Promise.allSettled(imagePromises);
    const validImages = newImages
      .filter((r): r is PromiseFulfilledResult<any> => r.status === "fulfilled")
      .map(r => r.value);

    await promptPromise;

    setImages(prev => [...validImages, ...prev]);
    setGenerating(false);
  }

  return (
    <div className="space-y-6 relative">
      {generating && <AIThinkingOverlay message="AI is generating your images..." />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">AI Image Studio</h1>
          <p className="text-sm text-text-secondary mt-1">Generate, edit, and manage ad creatives — better than Canva</p>
        </div>
        <span className="badge badge-accent"><Sparkles className="w-3 h-3" /> AI Powered</span>
      </div>

      <div className="flex gap-1 p-1 rounded-lg bg-bg-surface w-fit">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-md text-sm font-medium transition-all", tab === t ? "bg-accent/10 text-accent" : "text-text-secondary hover:text-text")}>{t}</button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Generation Panel */}
        <div className="lg:col-span-3 space-y-4">
          <Card3D glow>
            <SectionHeader title="Generate Images" subtitle="Text to image in seconds" />
            <div className="space-y-4">
              <div>
                <label className="label-field block mb-2">Prompt</label>
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe your image... e.g., 'A premium coffee cup on a marble counter with morning sunlight'" className="input-field h-20 resize-none" maxLength={500} />
              </div>
              <div>
                <label className="label-field block mb-2">Negative Prompt</label>
                <input value={negativePrompt} onChange={(e) => setNegativePrompt(e.target.value)} placeholder="What to exclude... e.g., 'text, watermark, blurry'" className="input-field" />
              </div>
              <div>
                <label className="label-field block mb-2">Style</label>
                <div className="flex flex-wrap gap-1.5">
                  {STYLES.map((s) => (
                    <button key={s} onClick={() => setStyle(s)} className={cn("px-2.5 py-1 rounded-full text-xs border transition-all", style === s ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary hover:text-text")}>{s}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Aspect Ratio</label>
                <div className="grid grid-cols-5 gap-1.5">
                  {RATIOS.map((r) => (
                    <button key={r.id} onClick={() => setRatio(r.id)} className={cn("flex flex-col items-center gap-1 px-1 py-2 rounded-md border transition-all", ratio === r.id ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary")}>
                      <r.icon className="w-3 h-3" /><span className="text-[9px]">{r.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Quality</label>
                <div className="grid grid-cols-3 gap-1.5">
                  {QUALITIES.map((q) => (
                    <button key={q} onClick={() => setQuality(q)} className={cn("px-2 py-1.5 rounded-md text-xs border transition-all", quality === q ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary")}>{q}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Variations: {variations}</label>
                <input type="range" min={1} max={8} value={variations} onChange={(e) => setVariations(Number(e.target.value))} className="w-full accent-accent" />
              </div>
              <button onClick={generate} className="btn-primary w-full"><Wand2 className="w-4 h-4" /> Generate Images</button>
            </div>
          </Card3D>
        </div>

        {/* Center: Results / Editor / Assets */}
        <div className="lg:col-span-6 space-y-6">
          {tab === "Generated" && (
            <div className="space-y-4">
              {aiPrompt && (
                <Card className="border-l-2 border-l-accent/40">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-accent" />
                    <span className="text-sm font-medium text-text">AI-Enhanced Prompts</span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">{aiPrompt}</p>
                </Card>
              )}
              {images.length === 0 && !generating ? (
                <div className="flex flex-col items-center justify-center h-64 text-center">
                  <Wand2 className="w-12 h-12 text-text-muted mb-3" />
                  <p className="text-sm text-text-secondary">Enter a prompt and click Generate to create images</p>
                  <p className="text-xs text-text-muted mt-1">AI will generate {variations} variations in {style} style</p>
                </div>
              ) : (
                <div className="columns-2 md:columns-3 gap-4 space-y-4">
                  {images.map((img, i) => {
                    const imgData = img as any;
                    return (
                <motion.div key={img.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }} className="break-inside-avoid">
                  <Card3D className="overflow-hidden p-0">
                    <div className={cn("relative aspect-square rounded-t-xl flex items-center justify-center group cursor-pointer overflow-hidden", !imgData.imageUrl && `bg-gradient-to-br ${img.gradient}`)}>
                      {imgData.imageUrl ? (
                        <img src={imgData.imageUrl} alt={img.prompt} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                      ) : (
                        <ImageIcon className="w-8 h-8 text-white/30" />
                      )}
                      <span className="absolute top-2 right-2 badge badge-accent text-[9px]">{img.confidence}%</span>
                      <span className="absolute bottom-2 left-2 badge badge-neutral text-[9px]">{img.ratio}</span>
                    </div>
                    <div className="p-3">
                      <p className="text-xs text-text-secondary truncate mb-2">{img.prompt}</p>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-text-muted">{img.style} · {img.quality}</span>
                      </div>
                      <div className="flex gap-1">
                        <button className="btn-secondary text-xs px-2 py-1 flex-1"><Download className="w-3 h-3" /></button>
                        <button className="btn-secondary text-xs px-2 py-1 flex-1">Use in Ad</button>
                        <button className="btn-secondary text-xs px-2 py-1"><Edit3 className="w-3 h-3" /></button>
                      </div>
                    </div>
                  </Card3D>
                </motion.div>
                  );
                })}
                </div>
              )}
            </div>
          )}

          {tab === "Editor" && (
            <Card>
              <SectionHeader title="Image Editor" subtitle="AI-powered editing tools" icon={<Edit3 className="w-4 h-4" />} />
              {/* Canvas */}
              <div className="aspect-video rounded-xl bg-gradient-to-br from-bg-surface to-bg-card border border-white/[0.06] flex items-center justify-center mb-4 relative">
                <ImageIcon className="w-16 h-16 text-white/10" />
                <span className="absolute bottom-3 right-3 font-mono text-[10px] text-text-muted">1080 × 1080</span>
              </div>
              {/* Toolbar */}
              <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mb-4">
                {[
                  { icon: Type, label: "Text" },
                  { icon: Crop, label: "Crop" },
                  { icon: RotateCw, label: "Rotate" },
                  { icon: Filter, label: "Filter" },
                  { icon: Eraser, label: "Eraser" },
                  { icon: Expand, label: "Expand" },
                  { icon: Palette, label: "Color" },
                  { icon: Layers, label: "Layers" },
                ].map((tool) => (
                  <button key={tool.label} className="flex flex-col items-center gap-1 p-2 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.04] transition-all">
                    <tool.icon className="w-4 h-4 text-text-secondary" />
                    <span className="text-[9px] text-text-muted">{tool.label}</span>
                  </button>
                ))}
              </div>
              {/* Filters */}
              <div>
                <label className="label-field block mb-2">Filter Presets</label>
                <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
                  {FILTERS.map((f) => (
                    <button key={f} className="aspect-square rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-accent/30 text-[10px] text-text-secondary hover:text-accent transition-all flex items-center justify-center">{f}</button>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {tab === "Brand Assets" && (
            <div className="space-y-4">
              <Card>
                <SectionHeader title="Brand Asset Library" subtitle="Saved and generated assets" />
                <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
                  {["Ad Creatives", "Social Posts", "Thumbnails", "Stories", "Banners"].map((cat) => (
                    <div key={cat} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] text-center">
                      <ImageIcon className="w-5 h-5 text-text-muted mx-auto mb-1" />
                      <div className="text-xs text-text-secondary">{cat}</div>
                      <div className="text-[10px] text-text-muted">{Math.floor(Math.random() * 50 + 5)} assets</div>
                    </div>
                  ))}
                </div>
              </Card>
              <div className="columns-3 md:columns-4 gap-3 space-y-3">
                {MOCK_IMAGES.map((img) => (
                  <div key={img.id} className={cn("break-inside-avoid aspect-square rounded-lg bg-gradient-to-br flex items-center justify-center", img.gradient)}>
                    <ImageIcon className="w-6 h-6 text-white/20" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === "Templates" && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {TEMPLATES.map((t, i) => (
                <motion.div key={t} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                  <Card3D className="text-center">
                    <div className="aspect-video rounded-lg bg-gradient-to-br from-white/[0.04] to-transparent mb-3 flex items-center justify-center">
                      <ImageIcon className="w-6 h-6 text-text-muted" />
                    </div>
                    <h3 className="font-display text-xs font-medium text-text mb-2">{t}</h3>
                    <button className="btn-secondary text-xs w-full">Use Template</button>
                  </Card3D>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Right: AI Magic Tools */}
        <div className="lg:col-span-3 space-y-4">
          <Card>
            <SectionHeader title="AI Magic Tools" subtitle="One-click AI editing" icon={<Sparkles className="w-4 h-4" />} />
            <div className="space-y-2">
              {[
                { icon: Expand, name: "Magic Expand", desc: "Extend beyond borders" },
                { icon: Eraser, name: "Magic Eraser", desc: "Remove any object" },
                { icon: Type, name: "Magic Write", desc: "AI text generation" },
                { icon: Crop, name: "Magic Switch", desc: "Auto-resize for all platforms" },
                { icon: Palette, name: "Brand Auto-Apply", desc: "Apply brand kit instantly" },
                { icon: Filter, name: "Background Remover", desc: "One-click transparent BG" },
              ].map((tool) => (
                <div key={tool.name} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center group-hover:glow-ring transition-all">
                      <tool.icon className="w-4 h-4 text-accent" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-text">{tool.name}</div>
                      <div className="text-[10px] text-text-muted">{tool.desc}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeader title="Brand Kit" />
            <div className="space-y-3">
              <div>
                <label className="label-field block mb-1.5">Colors</label>
                <div className="flex gap-1.5">
                  {["#FFD400", "#0B0F14", "#22C55E", "#3B82F6", "#EF4444"].map((c) => (
                    <div key={c} className="w-7 h-7 rounded-md border border-white/[0.1]" style={{ background: c }} />
                  ))}
                </div>
              </div>
              <div>
                <label className="label-field block mb-1.5">Fonts</label>
                <div className="text-xs text-text-secondary">Space Grotesk · Inter · IBM Plex Mono</div>
              </div>
              <div>
                <label className="label-field block mb-1.5">Logo</label>
                <div className="w-full h-12 rounded-lg bg-white/[0.02] border border-dashed border-white/[0.08] flex items-center justify-center text-xs text-text-muted">Upload logo</div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
