"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { SectionHeader, EmptyState } from "@/components/ui/empty-state";
import { LabsBanner } from "@/components/LabsBanner";
import { apiPost, ApiError } from "@/lib/api";
import {
  Image as ImageIcon, Wand2, Download, Edit3, Crop, RotateCw,
  Sparkles, Filter, Eraser, Expand, Type, Palette, Layers,
  Square, RectangleVertical, RectangleHorizontal, AlertTriangle,
} from "lucide-react";

type GeneratedImage = {
  id: string;
  prompt: string;
  style: string;
  ratio: string;
  quality: string;
  imageUrl: string;
};

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
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [aiPrompt, setAiPrompt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    setError(null);
    setAiPrompt(null);

    const fullPrompt = `${prompt}, ${style} style, high quality, detailed, professional photography${negativePrompt ? `. Exclude: ${negativePrompt}` : ""}`;

    // Fire LLM prompt enhancement in parallel (best-effort, non-blocking)
    const promptPromise = apiPost<{ reply: string }>("/chat", {
      messages: [{
        role: "user",
        content: `You are an AI image prompt engineer for PRACHAR. The user wants a ${style} image in ${ratio} format. Their prompt: "${prompt}". ${negativePrompt ? `Exclude: ${negativePrompt}.` : ""} Generate ${variations} enhanced, detailed image generation prompts (each on a new line, numbered 1-${variations}). Include lighting, composition, mood, and style details.`,
      }],
    }).then(data => setAiPrompt(data.reply)).catch(() => {});

    // Generate real AI images via the backend image generation API
    const count = Math.min(variations, 4);
    const imagePromises = Array.from({ length: count }, (_, i) =>
      apiPost<{ image_url?: string; url?: string }>("/video/generate-image", {
        prompt: fullPrompt,
        width: ratio === "9:16" ? 720 : 1024,
        height: ratio === "9:16" ? 1280 : 1024,
      }).then(data => ({
        id: `${Date.now()}-${i}`,
        prompt: `${prompt} — variation ${i + 1}`,
        style,
        ratio,
        quality,
        imageUrl: data.image_url ?? data.url ?? "",
      }))
    );

    const results = await Promise.allSettled(imagePromises);
    await promptPromise;

    const validImages = results
      .filter((r): r is PromiseFulfilledResult<GeneratedImage> => r.status === "fulfilled" && r.value.imageUrl !== "")
      .map(r => r.value);

    if (validImages.length === 0) {
      const firstError = results.find(r => r.status === "rejected");
      if (firstError && firstError.status === "rejected") {
        const reason = firstError.reason;
        setError(reason instanceof ApiError
          ? `Generation failed (HTTP ${reason.status}). Please try again.`
          : reason instanceof Error
            ? reason.message
            : "Image generation failed. Please try again.");
      } else {
        setError("Image generation returned no images. Please try again.");
      }
    } else {
      setImages(prev => [...validImages, ...prev]);
    }

    setGenerating(false);
  }

  return (
    <div className="space-y-6 relative">
      <LabsBanner title="AI Image Studio" description="Generate marketing creatives from text prompts. Powered by AI image generation." features={["Text-to-image", "Multiple styles", "Variations"]} />
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
              <button onClick={generate} disabled={!prompt.trim() || generating} className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"><Wand2 className="w-4 h-4" /> {generating ? "Generating..." : "Generate Images"}</button>
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
              {error && !generating && (
                <Card className="border-l-2 border-l-danger/40">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertTriangle className="w-4 h-4 text-danger" />
                    <span className="text-sm font-medium text-text">Generation Error</span>
                  </div>
                  <p className="text-xs text-text-secondary">{error}</p>
                </Card>
              )}
              {images.length === 0 && !generating ? (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center justify-center h-64 text-center"
                >
                  <motion.div
                    animate={{ y: [0, -6, 0] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-4 glow-ring"
                  >
                    <Wand2 className="w-8 h-8 text-accent" />
                  </motion.div>
                  <p className="text-sm text-text-secondary">Enter a prompt and click Generate to create images</p>
                  <p className="text-xs text-text-muted mt-1">AI will generate {variations} variation{variations > 1 ? "s" : ""} in {style} style</p>
                </motion.div>
              ) : (
                <div className="columns-2 md:columns-3 gap-4 space-y-4">
                  {images.map((img, i) => (
                <motion.div key={img.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }} className="break-inside-avoid">
                  <Card3D className="overflow-hidden p-0">
                    <div className="relative aspect-square rounded-t-xl flex items-center justify-center group cursor-pointer overflow-hidden">
                      <img src={img.imageUrl} alt={img.prompt} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                      <span className="absolute bottom-2 left-2 badge badge-neutral text-[9px]">{img.ratio}</span>
                    </div>
                    <div className="p-3">
                      <p className="text-xs text-text-secondary truncate mb-2">{img.prompt}</p>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-text-muted">{img.style} · {img.quality}</span>
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => {
                            if (!img.imageUrl) return;
                            const a = document.createElement("a");
                            a.href = img.imageUrl;
                            a.download = `prachar-image-${img.id}.png`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                          }}
                          disabled={!img.imageUrl}
                          className="btn-secondary text-xs px-2 py-1 flex-1 disabled:opacity-30"
                        >
                          <Download className="w-3 h-3" />
                        </button>
                        <button className="btn-secondary text-xs px-2 py-1 flex-1">Use in Ad</button>
                        <button className="btn-secondary text-xs px-2 py-1"><Edit3 className="w-3 h-3" /></button>
                      </div>
                    </div>
                  </Card3D>
                </motion.div>
                  ))}
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
            <EmptyState
              icon={<ImageIcon className="w-6 h-6 text-accent" />}
              title="No brand assets yet"
              description="Images you generate will be saved here. Start by creating an image from the Generate panel."
            />
          )}

          {tab === "Templates" && (
            <EmptyState
              icon={<Layers className="w-6 h-6 text-accent" />}
              title="Templates coming soon"
              description="Pre-built templates for Instagram, Facebook, YouTube, and more will be available here."
            />
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
