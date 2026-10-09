"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { apiPost, ApiError } from "@/lib/api";
import {
  Image as ImageIcon, Download, Sparkles, AlertTriangle, ArrowUp,
  Square, RectangleVertical, RectangleHorizontal, ChevronDown, X,
} from "lucide-react";

type GeneratedImage = {
  id: string;
  prompt: string;
  style: string;
  ratio: string;
  imageUrl: string;
};

const RATIOS = [
  { id: "1:1", label: "1:1", icon: Square },
  { id: "16:9", label: "16:9", icon: RectangleHorizontal },
  { id: "9:16", label: "9:16", icon: RectangleVertical },
  { id: "4:5", label: "4:5", icon: RectangleVertical },
  { id: "3:2", label: "3:2", icon: RectangleHorizontal },
];

const STYLES = ["Photorealistic", "Illustration", "3D Render", "Minimalist", "Cinematic"];

/** Template suggestions — Gemini-style starter cards. Emoji-free thumbnails
 *  use gradient tiles; label fills the prompt on click. */
const TEMPLATES = [
  { label: "Product hero shot", prompt: "Premium product photo of a coffee product on a marble counter, soft morning light, minimal background", gradient: "from-amber-500/60 to-orange-600/60" },
  { label: "Festive promo", prompt: "Vibrant festive sale banner background, warm tones, celebratory lights, space for text overlay", gradient: "from-fuchsia-500/60 to-purple-600/60" },
  { label: "Lifestyle ad", prompt: "Lifestyle photo, young professional using a phone in a bright modern cafe, shallow depth of field", gradient: "from-sky-500/60 to-blue-600/60" },
  { label: "HD portrait", prompt: "Professional HD portrait with studio lighting, neutral backdrop, sharp focus", gradient: "from-emerald-500/60 to-teal-600/60" },
  { label: "Food flat-lay", prompt: "Overhead flat-lay of gourmet food on dark slate, editorial style, rich colors", gradient: "from-rose-500/60 to-red-600/60" },
];

export default function ImageStudioPage() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("Photorealistic");
  const [ratio, setRatio] = useState("1:1");
  const [generating, setGenerating] = useState(false);
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ratioOpen, setRatioOpen] = useState(false);
  const [styleOpen, setStyleOpen] = useState(false);
  const [lightbox, setLightbox] = useState<GeneratedImage | null>(null);

  const [w, h] = ratio === "9:16" ? [720, 1280]
    : ratio === "16:9" ? [1280, 720]
    : ratio === "4:5" ? [896, 1120]
    : ratio === "3:2" ? [1152, 768]
    : [1024, 1024];

  async function generate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    setError(null);

    const fullPrompt = `${prompt}, ${style} style, high quality, detailed, professional`;

    const results = await Promise.allSettled(
      Array.from({ length: 4 }, (_, i) =>
        apiPost<{ image_url?: string; url?: string }>("/video/generate-image", {
          prompt: fullPrompt,
          width: w,
          height: h,
        }).then((data) => ({
          id: `${Date.now()}-${i}`,
          prompt,
          style,
          ratio,
          imageUrl: data.image_url ?? data.url ?? "",
        })),
      ),
    );

    const validImages = results
      .filter((r): r is PromiseFulfilledResult<GeneratedImage> => r.status === "fulfilled" && r.value.imageUrl !== "")
      .map((r) => r.value);

    if (validImages.length === 0) {
      const firstError = results.find((r) => r.status === "rejected");
      setError(
        firstError && firstError.status === "rejected" && firstError.reason instanceof ApiError
          ? `Generation failed (HTTP ${firstError.reason.status}). Please try again.`
          : firstError && firstError.status === "rejected" && firstError.reason instanceof Error
            ? firstError.reason.message
            : "Image generation failed. Please try again.",
      );
    } else {
      setImages((prev) => [...validImages, ...prev]);
    }
    setGenerating(false);
  }

  const ActiveRatioIcon = RATIOS.find((r) => r.id === ratio)?.icon ?? Square;

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col items-center px-4">
      {/* ─── Hero ─── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-3xl pt-14 lg:pt-20 text-center"
      >
        <motion.div
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
          className="mx-auto mb-6 w-14 h-14 rounded-2xl bg-gradient-to-br from-accent to-accent-magenta flex items-center justify-center shadow-glow"
        >
          <ImageIcon className="w-7 h-7 text-white" />
        </motion.div>
        <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight text-text">
          Create images
        </h1>
        <p className="mt-3 text-sm sm:text-base text-text-secondary max-w-md mx-auto">
          Try a template or describe an idea — CURV AI creates it.
        </p>
      </motion.div>

      {/* ─── Composer ─── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="w-full max-w-2xl mt-8"
      >
        <div className="group relative rounded-3xl border border-line/10 bg-bg-card/80 backdrop-blur-xl transition-all duration-300 focus-within:border-accent/30 focus-within:shadow-glow shadow-lg">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                generate();
              }
            }}
            placeholder="Describe your image"
            rows={2}
            className="w-full bg-transparent text-text placeholder:text-text-muted text-sm sm:text-base px-5 pt-4 pb-2 resize-none outline-none"
          />
          <div className="flex items-center justify-between px-3 pb-3 pt-1">
            <div className="flex items-center gap-1.5">
              {/* Mode chip */}
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-hover text-xs font-medium text-text-secondary">
                <ImageIcon className="w-3.5 h-3.5" /> Images
              </span>

              {/* Aspect ratio dropdown */}
              <div className="relative">
                <button
                  onClick={() => { setRatioOpen(!ratioOpen); setStyleOpen(false); }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-text-secondary hover:bg-bg-hover transition-colors"
                >
                  <ActiveRatioIcon className="w-3.5 h-3.5" />
                  Aspect ratio
                  <ChevronDown className="w-3 h-3" />
                </button>
                <AnimatePresence>
                  {ratioOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 4 }}
                      className="absolute left-0 bottom-full mb-2 z-20 min-w-[140px] rounded-2xl border border-line/10 bg-bg-elevated p-1.5 shadow-xl"
                    >
                      {RATIOS.map((r) => (
                        <button
                          key={r.id}
                          onClick={() => { setRatio(r.id); setRatioOpen(false); }}
                          className={cn(
                            "w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors",
                            ratio === r.id ? "bg-accent/15 text-accent" : "text-text-secondary hover:bg-bg-hover hover:text-text",
                          )}
                        >
                          <r.icon className="w-3.5 h-3.5" />
                          {r.label}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Style dropdown */}
              <div className="relative">
                <button
                  onClick={() => { setStyleOpen(!styleOpen); setRatioOpen(false); }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-text-secondary hover:bg-bg-hover transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {style}
                  <ChevronDown className="w-3 h-3" />
                </button>
                <AnimatePresence>
                  {styleOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 4 }}
                      className="absolute left-0 bottom-full mb-2 z-20 min-w-[160px] rounded-2xl border border-line/10 bg-bg-elevated p-1.5 shadow-xl"
                    >
                      {STYLES.map((s) => (
                        <button
                          key={s}
                          onClick={() => { setStyle(s); setStyleOpen(false); }}
                          className={cn(
                            "w-full text-left px-3 py-2 rounded-xl text-xs transition-colors",
                            style === s ? "bg-accent/15 text-accent" : "text-text-secondary hover:bg-bg-hover hover:text-text",
                          )}
                        >
                          {s}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Send */}
            <button
              onClick={generate}
              disabled={!prompt.trim() || generating}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center transition-all",
                prompt.trim() && !generating
                  ? "bg-gradient-to-br from-accent to-accent-dark text-white hover:scale-105 shadow-glow"
                  : "bg-white/[0.04] text-text-muted cursor-not-allowed",
              )}
              aria-label="Generate images"
            >
              {generating ? (
                <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              ) : (
                <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.5} />
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 text-xs text-danger px-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}
      </motion.div>

      {/* ─── Templates / results ─── */}
      {images.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="w-full max-w-3xl mt-10 pb-16"
        >
          <div className="flex gap-3 overflow-x-auto scrollbar-none pb-2 -mx-4 px-4">
            {TEMPLATES.map((t, i) => (
              <motion.button
                key={t.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + i * 0.05 }}
                onClick={() => setPrompt(t.prompt)}
                className="group shrink-0 w-40 text-left"
              >
                <div className={cn("aspect-[3/4] rounded-2xl bg-gradient-to-br overflow-hidden relative", t.gradient)}>
                  <Sparkles className="w-5 h-5 text-white/60 absolute bottom-3 left-3" />
                </div>
                <p className="mt-2 text-xs font-medium text-text-secondary group-hover:text-text transition-colors">
                  {t.label}
                </p>
              </motion.button>
            ))}
          </div>
        </motion.div>
      ) : (
        <div className="w-full max-w-4xl mt-10 pb-16">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-text-secondary">Your images</h2>
            {generating && (
              <span className="text-xs text-text-muted animate-pulse">Generating 4 more…</span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {images.map((img, i) => (
              <motion.div
                key={img.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
                className="group relative rounded-2xl overflow-hidden bg-bg-card border border-line/10 cursor-pointer"
                onClick={() => setLightbox(img)}
              >
                <div
                  className={cn(
                    "w-full",
                    ratio === "9:16" ? "aspect-[9/16]"
                    : ratio === "16:9" ? "aspect-video"
                    : ratio === "4:5" ? "aspect-[4/5]"
                    : ratio === "3:2" ? "aspect-[3/2]"
                    : "aspect-square",
                  )}
                >
                  <img src={img.imageUrl} alt={img.prompt} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-between p-3">
                  <span className="text-[10px] text-white/80 truncate flex-1 mr-2">{img.prompt}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const a = document.createElement("a");
                      a.href = img.imageUrl;
                      a.download = `curv-image-${img.id}.png`;
                      a.click();
                    }}
                    className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors shrink-0"
                    aria-label="Download"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Lightbox ─── */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setLightbox(null)}
            className="fixed inset-0 z-[80] bg-black/80 backdrop-blur-sm flex items-center justify-center p-6"
          >
            <button onClick={() => setLightbox(null)} className="absolute top-5 right-5 p-2 rounded-full bg-white/10 text-white hover:bg-white/20" aria-label="Close">
              <X className="w-5 h-5" />
            </button>
            <motion.img
              initial={{ scale: 0.92 }}
              animate={{ scale: 1 }}
              src={lightbox.imageUrl}
              alt={lightbox.prompt}
              className="max-w-full max-h-[85vh] rounded-2xl object-contain shadow-2xl"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
