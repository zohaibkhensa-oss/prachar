"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { apiPost, ApiError } from "@/lib/api";
import {
  Video as VideoIcon, Download, Sparkles, AlertTriangle, ArrowUp,
  ChevronDown, Play, X, Clapperboard, Music2, FileText,
} from "lucide-react";

const FORMATS = [
  { id: "reel", label: "Reel 9:16" },
  { id: "short", label: "Short 9:16" },
  { id: "square", label: "Square 1:1" },
  { id: "landscape", label: "Landscape 16:9" },
  { id: "story", label: "Story 9:10" },
];

const DURATIONS = ["5s", "8s", "10s", "15s"];

const QUALITY_TIERS = [
  { id: "preview", label: "Preview", desc: "Free · low quality" },
  { id: "lite", label: "Standard", desc: "~$0.08/s · 1080p + audio" },
  { id: "fast", label: "High", desc: "~$0.12/s · better motion" },
  { id: "standard", label: "Premium", desc: "~$0.40/s · best quality" },
] as const;

const STYLES = ["Cinematic", "Documentary", "Product Demo", "UGC", "Animated"];

const TEMPLATES = [
  { label: "Product reel", prompt: "Cinematic product reel — premium coffee pour over ice in slow motion, warm light, macro shots", gradient: "from-amber-500/60 to-orange-600/60" },
  { label: "Festive offer", prompt: "Vibrant festive sale video — lights, sparkles, celebratory mood, bold end card space", gradient: "from-fuchsia-500/60 to-purple-600/60" },
  { label: "UGC testimonial", prompt: "UGC-style testimonial — person talking to camera in a bright home setting, authentic feel", gradient: "from-sky-500/60 to-blue-600/60" },
  { label: "Brand film", prompt: "Cinematic brand film — city at golden hour, smooth drone shots, epic feel", gradient: "from-indigo-500/60 to-violet-600/60" },
  { label: "How-to demo", prompt: "Quick how-to product demo — clean hands-on shots, bright studio lighting, step by step", gradient: "from-emerald-500/60 to-teal-600/60" },
];

type VideoItem = {
  id: string;
  prompt: string;
  format: string;
  duration: string;
  script: string;
  scriptStatus: "generating" | "done" | "error";
  videoStatus: "generating" | "done" | "error";
  videoUrl: string;
  error?: string;
};

export default function VideoPage() {
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState("reel");
  const [duration, setDuration] = useState("15s");
  const [qualityTier, setQualityTier] = useState<"preview" | "lite" | "fast" | "standard">("lite");
  const [style, setStyle] = useState("Cinematic");
  const [withAudio, setWithAudio] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [player, setPlayer] = useState<VideoItem | null>(null);
  const [scriptOpen, setScriptOpen] = useState<string | null>(null);

  async function generate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);

    const formatMap: Record<string, string> = { reel: "9:16", short: "9:16", square: "1:1", landscape: "16:9", story: "9:10" };
    const newId = String(Date.now());
    const newVideo: VideoItem = {
      id: newId,
      prompt,
      format: formatMap[format] || "9:16",
      duration,
      script: "",
      scriptStatus: "generating",
      videoStatus: "generating",
      videoUrl: "",
    };
    setVideos((prev) => [newVideo, ...prev]);
    const capturedPrompt = prompt;
    setPrompt("");

    // Script (LLM) — parallel, best-effort
    (async () => {
      try {
        const data = await apiPost<{ reply?: string }>("/chat", {
          messages: [{
            role: "user",
            content: `You are an AI video script writer for CURV AI. Write a ${duration} ${style} video script for social. Prompt: "${capturedPrompt}". Include scene-by-scene breakdown with timestamps, visual descriptions, and voiceover text.`,
          }],
        });
        setVideos((prev) => prev.map((v) => v.id === newId ? { ...v, script: data.reply || "", scriptStatus: "done" } : v));
      } catch {
        setVideos((prev) => prev.map((v) => v.id === newId ? { ...v, scriptStatus: "error" } : v));
      }
    })();

    // Video (fal.ai / Wan-3.0)
    try {
      const data = await apiPost<{ video_url?: string; detail?: string }>("/video/generate", {
        prompt: `${capturedPrompt}, ${style} style, high quality, detailed`,
        quality: qualityTier,
        duration: String(duration.replace("s", "")),
        resolution: "1080p",
        video_type: format,
        with_audio: withAudio,
      });
      if (data.video_url) {
        setVideos((prev) => prev.map((v) => v.id === newId ? { ...v, videoUrl: data.video_url!, videoStatus: "done" } : v));
      } else {
        setVideos((prev) => prev.map((v) => v.id === newId ? { ...v, videoStatus: "error", error: "Generation returned no video." } : v));
      }
    } catch (e) {
      let errMsg = "Video generation failed.";
      if (e instanceof ApiError) {
        const body = e.body as { detail?: string } | null;
        if (body?.detail?.includes("balance")) errMsg = "fal.ai credits exhausted — add credits at fal.ai/dashboard/billing";
        else if (body?.detail?.includes("FAL_KEY")) errMsg = "fal.ai API key not configured on server";
        else errMsg = body?.detail || e.message;
      } else if (e instanceof TypeError) {
        errMsg = "Network error — cannot reach video generation service";
      }
      setVideos((prev) => prev.map((v) => v.id === newId ? { ...v, videoStatus: "error", error: errMsg } : v));
    }
    setGenerating(false);
  }

  const dropdown = (
    id: string,
    label: React.ReactNode,
    options: { id: string; label: string; desc?: string }[],
    current: string,
    onPick: (v: string) => void,
  ) => (
    <div className="relative" key={id}>
      <button
        onClick={() => setOpenMenu(openMenu === id ? null : id)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-text-secondary hover:bg-bg-hover transition-colors"
      >
        {label}
        <ChevronDown className="w-3 h-3" />
      </button>
      <AnimatePresence>
        {openMenu === id && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute left-0 bottom-full mb-2 z-20 min-w-[160px] rounded-2xl border border-line/10 bg-bg-elevated p-1.5 shadow-xl"
          >
            {options.map((o) => (
              <button
                key={o.id}
                onClick={() => { onPick(o.id); setOpenMenu(null); }}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-xl text-xs transition-colors",
                  current === o.id ? "bg-accent/15 text-accent" : "text-text-secondary hover:bg-bg-hover hover:text-text",
                )}
              >
                <div>{o.label}</div>
                {o.desc && <div className="text-[10px] text-text-muted mt-0.5">{o.desc}</div>}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col items-center px-4">
      {/* ─── Hero ─── */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-3xl pt-14 lg:pt-20 text-center">
        <motion.div
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
          className="mx-auto mb-6 w-14 h-14 rounded-2xl bg-gradient-to-br from-accent to-accent-magenta flex items-center justify-center shadow-glow"
        >
          <Clapperboard className="w-7 h-7 text-white" />
        </motion.div>
        <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight text-text">Create videos</h1>
        <p className="mt-3 text-sm sm:text-base text-text-secondary max-w-md mx-auto">
          Try a template or describe an idea — CURV AI turns it into video.
        </p>
      </motion.div>

      {/* ─── Composer ─── */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} className="w-full max-w-2xl mt-8">
        <div className="group relative rounded-3xl border border-line/10 bg-bg-card/80 backdrop-blur-xl transition-all duration-300 focus-within:border-accent/30 focus-within:shadow-glow shadow-lg">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); generate(); }
            }}
            placeholder="Describe your video"
            rows={2}
            className="w-full bg-transparent text-text placeholder:text-text-muted text-sm sm:text-base px-5 pt-4 pb-2 resize-none outline-none"
          />
          <div className="flex items-center justify-between px-3 pb-3 pt-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-hover text-xs font-medium text-text-secondary">
                <VideoIcon className="w-3.5 h-3.5" /> Video
              </span>

              {dropdown("format", <>{FORMATS.find((f) => f.id === format)?.label}</>, FORMATS, format, setFormat)}
              {dropdown("duration", <>{duration}</>, DURATIONS.map((d) => ({ id: d, label: d })), duration, setDuration)}
              {dropdown("quality", <>{QUALITY_TIERS.find((q) => q.id === qualityTier)?.label}</>, QUALITY_TIERS.map((q) => ({ id: q.id, label: q.label, desc: q.desc })), qualityTier, (v) => setQualityTier(v as typeof qualityTier))}
              {dropdown("style", <>{style}</>, STYLES.map((s) => ({ id: s, label: s })), style, setStyle)}

              <button
                onClick={() => setWithAudio(!withAudio)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                  withAudio ? "bg-accent/15 text-accent" : "text-text-secondary hover:bg-bg-hover",
                )}
                title="Generate with audio"
              >
                <Music2 className="w-3.5 h-3.5" /> Audio
              </button>
            </div>

            <button
              onClick={generate}
              disabled={!prompt.trim() || generating}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center transition-all shrink-0 ml-2",
                prompt.trim() && !generating
                  ? "bg-gradient-to-br from-accent to-accent-dark text-white hover:scale-105 shadow-glow"
                  : "bg-white/[0.04] text-text-muted cursor-not-allowed",
              )}
              aria-label="Generate video"
            >
              {generating ? <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" /> : <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.5} />}
            </button>
          </div>
        </div>
      </motion.div>

      {/* ─── Templates / results ─── */}
      {videos.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} className="w-full max-w-3xl mt-10 pb-16">
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
                  <Play className="w-5 h-5 text-white/60 absolute bottom-3 left-3" />
                </div>
                <p className="mt-2 text-xs font-medium text-text-secondary group-hover:text-text transition-colors">{t.label}</p>
              </motion.button>
            ))}
          </div>
        </motion.div>
      ) : (
        <div className="w-full max-w-4xl mt-10 pb-16">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-text-secondary">Your videos</h2>
            {generating && <span className="text-xs text-text-muted animate-pulse">Generating…</span>}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {videos.map((v, i) => (
              <motion.div
                key={v.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
                className="rounded-2xl overflow-hidden bg-bg-card border border-line/10"
              >
                <div className="relative aspect-video bg-black flex items-center justify-center">
                  {v.videoStatus === "generating" ? (
                    <div className="flex flex-col items-center gap-2 text-text-muted">
                      <div className="w-8 h-8 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
                      <span className="text-[11px]">Generating video…</span>
                    </div>
                  ) : v.videoStatus === "error" ? (
                    <div className="flex flex-col items-center gap-1.5 text-danger px-4 text-center">
                      <AlertTriangle className="w-5 h-5" />
                      <span className="text-[11px]">{v.error || "Failed"}</span>
                    </div>
                  ) : (
                    <>
                      <video src={v.videoUrl} className="w-full h-full object-cover" />
                      <button
                        onClick={() => setPlayer(v)}
                        className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity"
                      >
                        <span className="w-11 h-11 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                          <Play className="w-5 h-5 text-white ml-0.5" />
                        </span>
                      </button>
                    </>
                  )}
                  <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/60 text-[10px] font-mono text-white z-10">{v.duration}</span>
                  <span className="absolute bottom-2 left-2 px-1.5 py-0.5 rounded bg-black/60 text-[10px] font-mono text-white z-10">{v.format}</span>
                </div>
                <div className="p-3">
                  <p className="text-xs text-text-secondary truncate">{v.prompt}</p>
                  <div className="flex items-center gap-2 mt-2">
                    {v.scriptStatus === "done" && v.script && (
                      <button
                        onClick={() => setScriptOpen(scriptOpen === v.id ? null : v.id)}
                        className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-full bg-bg-hover text-text-secondary hover:text-text transition-colors"
                      >
                        <FileText className="w-3 h-3" /> Script
                      </button>
                    )}
                    {v.scriptStatus === "generating" && (
                      <span className="text-[10px] text-text-muted animate-pulse">Writing script…</span>
                    )}
                    {v.videoUrl && (
                      <button
                        onClick={() => {
                          const a = document.createElement("a");
                          a.href = v.videoUrl;
                          a.download = `curv-video-${v.id}.mp4`;
                          a.target = "_blank";
                          a.click();
                        }}
                        className="ml-auto p-1.5 rounded-lg bg-bg-hover text-text-secondary hover:text-text transition-colors"
                        aria-label="Download"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  {scriptOpen === v.id && v.script && (
                    <pre className="mt-2 p-3 rounded-xl bg-bg/60 border border-line/10 text-[11px] text-text-secondary whitespace-pre-wrap max-h-48 overflow-y-auto">{v.script}</pre>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Player lightbox ─── */}
      <AnimatePresence>
        {player && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setPlayer(null)}
            className="fixed inset-0 z-[80] bg-black/85 backdrop-blur-sm flex items-center justify-center p-6"
          >
            <button onClick={() => setPlayer(null)} className="absolute top-5 right-5 p-2 rounded-full bg-white/10 text-white hover:bg-white/20" aria-label="Close">
              <X className="w-5 h-5" />
            </button>
            <motion.video
              initial={{ scale: 0.92 }}
              animate={{ scale: 1 }}
              src={player.videoUrl}
              controls
              autoPlay
              className="max-w-full max-h-[85vh] rounded-2xl shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
