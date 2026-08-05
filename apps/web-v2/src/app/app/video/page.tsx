"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { AIStatusBlock, AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { SectionHeader, EmptyState } from "@/components/ui/empty-state";
import {
  Video, Play, Download, Sparkles, Mic, Clock, Film,
  Wand2, RefreshCw, Eye, TrendingUp, Layers,
  AlertTriangle,
} from "lucide-react";
import { LabsBanner } from "@/components/LabsBanner";
import { apiPost, ApiError } from "@/lib/api";

const VIDEO_TYPES = [
  { id: "reel", label: "Reel 9:16", w: 9, h: 16 },
  { id: "short", label: "Short 9:16", w: 9, h: 16 },
  { id: "square", label: "Square 1:1", w: 1, h: 1 },
  { id: "landscape", label: "Landscape 16:9", w: 16, h: 9 },
  { id: "story", label: "Story 9:10", w: 9, h: 10 },
];

const PLATFORMS = ["Instagram Reels", "TikTok", "YouTube Shorts", "Facebook Reels", "LinkedIn"];
const STYLES = ["Cinematic", "Documentary", "Product Demo", "UGC", "Animated", "Slideshow"];
const VOICES = ["Male US", "Female US", "Male UK", "Female UK", "Male IN", "Female IN"];
const DURATIONS = ["5s", "8s", "10s", "15s"];

const QUALITY_TIERS = [
  { id: "preview" as const, label: "Preview", desc: "Free · low quality", cost: "$0", icon: "👁" },
  { id: "lite" as const, label: "Standard", desc: "~$0.08/s · 1080p + audio", cost: "$1.20/15s", icon: "✓" },
  { id: "fast" as const, label: "High", desc: "~$0.12/s · better motion", cost: "$1.80/15s", icon: "✦" },
  { id: "standard" as const, label: "Premium", desc: "~$0.40/s · best quality", cost: "$6.00/15s", icon: "★" },
];

const TABS = ["Generated Videos", "Video Templates", "Voice Library", "Performance"];

// Scene gradients for visual storyboard frames
const SCENE_GRADIENTS = [
  "from-blue-600/40 via-cyan-500/30 to-sky-400/20",
  "from-purple-600/40 via-pink-500/30 to-rose-400/20",
  "from-amber-600/40 via-orange-500/30 to-yellow-400/20",
  "from-emerald-600/40 via-green-500/30 to-teal-400/20",
  "from-indigo-600/40 via-violet-500/30 to-purple-400/20",
  "from-rose-600/40 via-red-500/30 to-orange-400/20",
  "from-cyan-600/40 via-blue-500/30 to-indigo-400/20",
  "from-slate-600/40 via-gray-500/30 to-zinc-400/20",
];

// Emoji map for common scene keywords
const EMOJI_MAP: Record<string, string> = {
  mountain: "🏔️", alps: "🏔️", snow: "❄️", winter: "❄️", cold: "❄️",
  coffee: "☕", cappuccino: "☕", nescafe: "☕", cup: "☕", drink: "🥤",
  boy: "🧑", girl: "👩", couple: "💑", love: "❤️", heart: "❤️",
  walk: "🚶", walking: "🚶", door: "🚪", cafe: "🏠", restaurant: "🏠",
  fire: "🔥", fireplace: "🔥", warm: "🔥",
  smile: "😊", happy: "😄", laugh: "😂",
  camera: "🎥", film: "🎬", video: "🎬", close: "🎥", pan: "🎥", zoom: "🎥",
  tree: "🌲", forest: "🌲", nature: "🌿",
  lake: "🏞️", water: "💧", river: "🏞️",
  sun: "☀️", sunrise: "🌅", sunset: "🌅", golden: "🌅",
  city: "🏙️", street: "🛣️", road: "🛣️",
  car: "🚗", drive: "🚗",
  phone: "📱", screen: "📱",
  food: "🍽️", meal: "🍽️", eat: "🍽️",
  logo: "🏷️", brand: "🏷️", product: "📦",
  sky: "☁️", cloud: "☁️", wind: "💨",
  night: "🌙", star: "⭐", moon: "🌙",
  flower: "🌸", garden: "🌷",
  music: "🎵", song: "🎵",
  gift: "🎁", present: "🎁",
  dog: "🐕", cat: "🐱", animal: "🐾",
};

function pickEmoji(text: string): string {
  const lower = text.toLowerCase();
  for (const [keyword, emoji] of Object.entries(EMOJI_MAP)) {
    if (lower.includes(keyword)) return emoji;
  }
  return "🎬";
}

interface ParsedScene {
  time: string;
  visual: string;
  voiceover: string;
  emoji: string;
}

function parseScenes(script: string): ParsedScene[] {
  const scenes: ParsedScene[] = [];
  // Split by scene markers: "Scene 1", "(0s-3s)", "[0-3s]", "**Scene 1:**", etc.
  const parts = script.split(/(?=\*\*Scene\s*\d|(?=\(\d+s?-?\d*s?\))|(?=\[\d+s?-?\d*s?\])|(?=\*\*\[\d))/i);
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed || trimmed.length < 5) continue;
    // Extract timestamp
    const timeMatch = trimmed.match(/(\(?[\d]+s?\s*[-–]\s*[\d]+s?\)?|\[\d+s?\s*[-–]\s*[\d]+s?\])/i);
    const time = timeMatch ? timeMatch[0].replace(/[\[\]()]/g, "") : "";
    // Extract visual description
    const visualMatch = trimmed.match(/(?:visual|visuals|scene)\s*:?\s*(.+?)(?=\n|voiceover|vo\b|$)/is);
    const visual = visualMatch?.[1] ? visualMatch[1].trim().replace(/\*\*/g, "") : (trimmed.split("\n")[0] || "").replace(/\*\*/g, "").trim();
    // Extract voiceover
    const voMatch = trimmed.match(/(?:voiceover|vo)\s*:?\s*(.+?)(?=\n|$)/is);
    const voiceover = voMatch?.[1] ? voMatch[1].trim().replace(/[\(\)""]/g, "") : "";
    if (time || visual) {
      scenes.push({ time, visual, voiceover, emoji: pickEmoji(visual + " " + voiceover) });
    }
  }
  // Fallback: if no scenes parsed, split by double newlines
  if (scenes.length === 0) {
    const blocks = script.split(/\n\n+/).filter(b => b.trim().length > 10);
    for (const block of blocks) {
      const timeMatch = block.match(/(\d+s?\s*[-–]\s*[\d]+s?)/i);
      scenes.push({
        time: timeMatch ? timeMatch[0] : "",
        visual: block.replace(/\*\*/g, "").trim().slice(0, 120),
        voiceover: "",
        emoji: pickEmoji(block),
      });
    }
  }
  return scenes.slice(0, 10); // Max 10 scenes
}

export default function VideoStudioPage() {
  const [tab, setTab] = useState("Generated Videos");
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [selectedType, setSelectedType] = useState("reel");
  const [selectedPlatform, setSelectedPlatform] = useState("Instagram Reels");
  const [selectedStyle, setSelectedStyle] = useState("Cinematic");
  const [selectedVoice, setSelectedVoice] = useState("Female US");
  const [duration, setDuration] = useState("15s");
  const [qualityTier, setQualityTier] = useState<"preview" | "lite" | "fast" | "standard">("lite");
  const [music, setMusic] = useState(true);
  const [logoOverlay, setLogoOverlay] = useState(true);
  const [videos, setVideos] = useState<Array<{
    id: string;
    title: string;
    platform: string;
    duration: string;
    format: string;
    confidence: number;
    scenes: number;
    views: string;
    ctr: string;
    isNew?: boolean;
    gradient?: string;
    scriptStatus: "generating" | "done" | "error";
    videoStatus: "generating" | "done" | "error";
    script: string;
    videoUrl: string;
  }>>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [currentSceneIdx, setCurrentSceneIdx] = useState(0);
  const playTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-advance scenes during playback
  useEffect(() => {
    if (playingId && playTimerRef.current === null) {
      const v = videos.find(v => v.id === playingId) as any;
      const scenes = v?.script ? parseScenes(v.script) : [];
      if (scenes.length > 0) {
        playTimerRef.current = setTimeout(() => {
          setCurrentSceneIdx(prev => {
            if (prev + 1 >= scenes.length) {
              // Loop back to start
              return 0;
            }
            return prev + 1;
          });
        }, 3000); // 3 seconds per scene
      }
    }
    return () => {
      if (playTimerRef.current) {
        clearTimeout(playTimerRef.current);
        playTimerRef.current = null;
      }
    };
  }, [playingId, currentSceneIdx, videos]);

  function togglePlay(videoId: string, sceneCount: number) {
    if (playingId === videoId) {
      setPlayingId(null);
      setCurrentSceneIdx(0);
    } else {
      setPlayingId(videoId);
      setCurrentSceneIdx(0);
    }
  }

  async function generate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);

    const formatMap: Record<string, string> = { reel: "9:16", short: "9:16", square: "1:1", landscape: "16:9", story: "9:10" };
    const gradients = [
      "from-info/30 via-accent/20 to-success/10",
      "from-accent/30 via-success/20 to-info/10",
      "from-purple-500/30 via-info/20 to-accent/10",
      "from-warning/30 via-danger/20 to-info/10",
    ];
    const newId = String(Date.now());

    // Add video immediately with "generating" state
    const newVideo = {
      id: newId,
      title: prompt.slice(0, 40) + (prompt.length > 40 ? "..." : ""),
      platform: selectedPlatform,
      duration,
      format: formatMap[selectedType] || "9:16",
      confidence: 0,
      scenes: 0,
      views: "0",
      ctr: "—",
      isNew: true,
      gradient: gradients[Math.floor(Math.random() * gradients.length)],
      scriptStatus: "generating" as "generating" | "done" | "error",
      videoStatus: "generating" as "generating" | "done" | "error",
      script: "",
      videoUrl: "",
    };

    setVideos(prev => [newVideo, ...prev]);

    if (typeof window !== "undefined") {
      setTimeout(() => window.scrollTo({ top: 0, behavior: "smooth" }), 100);
    }

    // Fire both requests in parallel: LLM script & video generation
    const scriptPromise = (async () => {
      try {
        const data = await apiPost<{ reply?: string; detail?: string }>("/chat", {
          messages: [{
            role: "user",
            content: `You are an AI video script writer for PRACHAR. Write a ${duration} ${selectedStyle} video script for ${selectedPlatform}. Prompt: "${prompt}". Include scene-by-scene breakdown with timestamps, visual descriptions, and voiceover text.`,
          }],
        });
        const script = data.reply || "";
        const sceneCount = script ? (script.match(/scene\s*\d/gi) || []).length : 0;
        setVideos(prev => prev.map(v => v.id === newId ? { ...v, script, scriptStatus: "done", scenes: sceneCount } : v));
      } catch (e) {
        const errMsg = e instanceof ApiError
          ? `Script generation failed (${e.status}). The AI service may be rate-limited. Try again in a moment.`
          : "AI service is rate-limited. Please try again in a moment.";
        setVideos(prev => prev.map(v => v.id === newId ? { ...v, script: errMsg, scriptStatus: "error" } : v));
      }
    })();

    const videoPromise = (async () => {
      try {
        const data = await apiPost<{ video_url?: string; status?: string; detail?: string }>("/video/generate", {
          prompt: `${prompt}, ${selectedStyle} style, high quality, detailed`,
          quality: qualityTier,
          duration: String(duration.replace("s", "")),
          resolution: "1080p",
          video_type: selectedType,
          with_audio: music,
        });
        if (data.video_url) {
          setVideos(prev => prev.map(v => v.id === newId ? {
            ...v,
            videoUrl: data.video_url as string,
            videoStatus: "done",
          } : v));
        } else {
          setVideos(prev => prev.map(v => v.id === newId ? {
            ...v,
            videoStatus: "error",
            script: v.script || "Video generation returned no URL.",
          } : v));
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
        } else {
          errMsg = "Video generation failed: " + String(e);
        }
        setVideos(prev => prev.map(v => v.id === newId ? {
          ...v,
          videoStatus: "error",
          script: v.script || errMsg,
        } : v));
      }
    })();

    await Promise.allSettled([scriptPromise, videoPromise]);
    setGenerating(false);
  }

  return (
    <div className="space-y-6 relative">
      <LabsBanner title="AI Video" description="Generate marketing videos from text prompts. Powered by AI video generation." features={["Text-to-video", "Voice synthesis", "Brand templates"]} />
      {generating && <AIThinkingOverlay message="AI is generating your video..." />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">AI Video Studio</h1>
          <p className="text-sm text-text-secondary mt-1">Generate professional videos from text prompts — Reels, Shorts, TikToks, Ads</p>
        </div>
        <span className="badge badge-accent"><Sparkles className="w-3 h-3" /> Powered by AI</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg bg-bg-surface w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 rounded-md text-sm font-medium transition-all",
              tab === t ? "bg-accent/10 text-accent" : "text-text-secondary hover:text-text",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Generation Panel */}
        <div className="lg:col-span-3 space-y-4">
          <Card3D glow>
            <SectionHeader title="Generate Video" subtitle="Text to video in seconds" />
            <div className="space-y-4">
              <div>
                <label className="label-field block mb-2">Prompt</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe your video... e.g., 'A morning coffee routine showing our cold brew being poured over ice'"
                  className="input-field h-24 resize-none"
                  maxLength={500}
                />
                <div className="text-right text-[10px] text-text-muted mt-1">{prompt.length}/500</div>
              </div>

              <div>
                <label className="label-field block mb-2">Video Type</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {VIDEO_TYPES.map((v) => (
                    <button
                      key={v.id}
                      onClick={() => setSelectedType(v.id)}
                      className={cn(
                        "px-2 py-1.5 rounded-md text-xs border transition-all",
                        selectedType === v.id ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary hover:text-text",
                      )}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label-field block mb-2">Platform</label>
                <select value={selectedPlatform} onChange={(e) => setSelectedPlatform(e.target.value)} className="input-field">
                  {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div>
                <label className="label-field block mb-2">Style</label>
                <div className="flex flex-wrap gap-1.5">
                  {STYLES.map((s) => (
                    <button
                      key={s}
                      onClick={() => setSelectedStyle(s)}
                      className={cn(
                        "px-2.5 py-1 rounded-full text-xs border transition-all",
                        selectedStyle === s ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary hover:text-text",
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label-field block mb-2">AI Voiceover</label>
                <select value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)} className="input-field">
                  {VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>

              <div>
                <label className="label-field block mb-2">Duration</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {DURATIONS.map((d) => (
                    <button
                      key={d}
                      onClick={() => setDuration(d)}
                      className={cn(
                        "px-2 py-1.5 rounded-md text-xs border transition-all",
                        duration === d ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary",
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label-field block mb-2">Quality</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {QUALITY_TIERS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setQualityTier(t.id)}
                      className={cn(
                        "px-2 py-2 rounded-md text-left border transition-all",
                        qualityTier === t.id ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary hover:text-text",
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs">{t.icon}</span>
                        <span className="text-xs font-medium">{t.label}</span>
                      </div>
                      <div className="text-[10px] text-text-muted mt-0.5">{t.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={music} onChange={(e) => setMusic(e.target.checked)} className="accent-accent" />
                  <span className="text-xs text-text-secondary">Background music</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={logoOverlay} onChange={(e) => setLogoOverlay(e.target.checked)} className="accent-accent" />
                  <span className="text-xs text-text-secondary">Logo watermark overlay</span>
                </label>
              </div>

              <button onClick={generate} disabled={!prompt.trim() || generating} className="btn-primary w-full group disabled:opacity-40 disabled:cursor-not-allowed">
                <Wand2 className="w-4 h-4" />
                {generating ? "Generating..." : "Generate Video"}
              </button>
            </div>
          </Card3D>
        </div>

        {/* Center: Results */}
        <div className="lg:col-span-6 space-y-6">
          {tab === "Generated Videos" && (
            <>
              {videos.length === 0 ? (
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
                    <Video className="w-8 h-8 text-accent" />
                  </motion.div>
                  <p className="text-sm text-text-secondary">No videos generated yet</p>
                  <p className="text-xs text-text-muted mt-1">Enter a prompt on the left and click Generate to create your first AI video</p>
                </motion.div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {videos.map((v, i) => {
                  const vd = v;
                  const isExpanded = expandedId === v.id;
                  const isGeneratingScript = vd.scriptStatus === "generating";
                  const isGeneratingVideo = vd.videoStatus === "generating";
                  const hasScript = vd.scriptStatus === "done" && vd.script;
                  const hasError = vd.scriptStatus === "error" || vd.videoStatus === "error";
                  const hasVideo = vd.videoStatus === "done" && vd.videoUrl;
                  const isPlaying = playingId === v.id;
                  const scenes = hasScript ? parseScenes(vd.script) : [];
                  const currentScene = isPlaying ? scenes[currentSceneIdx] || scenes[0] : null;
                  const isGenerating = isGeneratingScript || isGeneratingVideo;
                  return (
                    <motion.div key={v.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                      <Card3D className={`overflow-hidden relative ${vd.isNew ? "ring-1 ring-success/30" : ""}`}>
                        {vd.isNew && (
                          <span className="absolute top-2 right-2 z-10 badge badge-success text-[9px]">NEW</span>
                        )}
                        {/* Video Player — real AI video or storyboard fallback */}
                        <div className="relative aspect-video rounded-lg overflow-hidden mb-3 group bg-black">
                          {hasVideo ? (
                            // REAL AI-GENERATED VIDEO
                            <video
                              src={vd.videoUrl}
                              controls
                              autoPlay
                              loop
                              muted
                              playsInline
                              className="absolute inset-0 w-full h-full object-cover"
                            />
                          ) : isGenerating ? (
                            // GENERATING — show spinner with status
                            <div className={`absolute inset-0 bg-gradient-to-br ${vd.gradient || "from-info/20 via-accent/10 to-success/10"} flex flex-col items-center justify-center gap-3`}>
                              <div className="w-12 h-12 rounded-full border-2 border-accent/20 border-t-accent animate-spin" />
                              <span className="text-xs text-white/80 font-medium">
                                {isGeneratingVideo ? "Generating AI video..." : "Generating script..."}
                              </span>
                              <span className="text-[10px] text-white/50">This takes 30-60 seconds</span>
                            </div>
                          ) : hasScript && scenes.length > 0 ? (
                            <>
                              {/* Animated scene frame */}
                              <AnimatePresence mode="wait">
                                <motion.div
                                  key={isPlaying ? currentSceneIdx : "static"}
                                  initial={{ opacity: 0, scale: 1.05 }}
                                  animate={{ opacity: 1, scale: 1 }}
                                  exit={{ opacity: 0, scale: 0.95 }}
                                  transition={{ duration: 0.4 }}
                                  className={`absolute inset-0 bg-gradient-to-br ${SCENE_GRADIENTS[currentSceneIdx % SCENE_GRADIENTS.length]}`}
                                >
                                  {/* Scene visual elements */}
                                  <div className="absolute inset-0 flex flex-col items-center justify-center p-4">
                                    {/* Animated visual representation */}
                                    <motion.div
                                      animate={isPlaying ? { y: [0, -8, 0], rotate: [0, 2, 0] } : {}}
                                      transition={{ duration: 2, repeat: Infinity }}
                                      className="text-5xl mb-3"
                                    >
                                      {currentScene?.emoji || "🎬"}
                                    </motion.div>
                                    <div className="text-center max-w-[90%]">
                                      <span className="font-mono text-[10px] text-white/60 mb-1 block">{currentScene?.time || ""}</span>
                                      <p className="text-xs text-white/90 font-medium leading-snug line-clamp-2">{currentScene?.visual || v.title}</p>
                                    </div>
                                  </div>
                                  {/* Film grain overlay */}
                                  <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.9'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23n)' opacity='0.4'/%3E%3C/svg%3E\")" }} />
                                </motion.div>
                              </AnimatePresence>

                              {/* Play/Pause overlay */}
                              {!isPlaying && (
                                <motion.div whileHover={{ scale: 1.1 }} className="absolute inset-0 flex items-center justify-center bg-black/30">
                                  <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                                    <Play className="w-6 h-6 text-white fill-white ml-0.5" />
                                  </div>
                                </motion.div>
                              )}

                              {/* Progress bar at bottom */}
                              <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/50">
                                <motion.div
                                  className="h-full bg-accent"
                                  animate={{ width: isPlaying ? `${((currentSceneIdx + 1) / scenes.length) * 100}%` : "0%" }}
                                  transition={{ duration: 0.3 }}
                                />
                              </div>

                              {/* Scene counter */}
                              <div className="absolute top-2 left-2 flex items-center gap-1.5">
                                <span className="badge badge-neutral text-[9px]">{v.format}</span>
                                {isPlaying && <span className="badge badge-accent text-[9px]">{currentSceneIdx + 1}/{scenes.length}</span>}
                              </div>

                              {/* Voiceover subtitle bar */}
                              {isPlaying && currentScene?.voiceover && (
                                <motion.div
                                  initial={{ opacity: 0, y: 10 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  className="absolute bottom-3 left-2 right-2 bg-black/70 backdrop-blur-sm rounded px-2 py-1"
                                >
                                  <p className="text-[9px] text-white/80 text-center line-clamp-2">{currentScene.voiceover}</p>
                                </motion.div>
                              )}
                            </>
                          ) : (
                            <div className={`absolute inset-0 bg-gradient-to-br ${vd.gradient || "from-info/20 via-accent/10 to-success/10"} flex items-center justify-center`}>
                              <motion.div whileHover={{ scale: 1.1 }} className="w-12 h-12 rounded-full bg-white/10 backdrop-blur flex items-center justify-center">
                                <Play className="w-5 h-5 text-white fill-white" />
                              </motion.div>
                            </div>
                          )}
                          <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/60 text-[10px] font-mono text-white z-10">{v.duration}</span>
                        </div>

                        {/* Scene timeline strip */}
                        {hasScript && scenes.length > 0 && (
                          <div className="flex gap-1 mb-3 overflow-x-auto pb-1">
                            {scenes.map((s, si) => (
                              <button
                                key={si}
                                onClick={(e) => { e.stopPropagation(); setPlayingId(v.id); setCurrentSceneIdx(si); }}
                                className={`shrink-0 w-12 h-8 rounded border transition-all ${isPlaying && currentSceneIdx === si ? "border-accent bg-accent/10" : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]"}`}
                                title={s.time}
                              >
                                <div className="text-[8px] text-text-muted text-center pt-1">{s.time?.split("-")[0] || `${si}s`}</div>
                              </button>
                            ))}
                          </div>
                        )}

                        <h3 className="font-display text-sm font-medium text-text mb-1">{v.title}</h3>
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-xs text-text-secondary">{v.platform}</span>
                          {v.confidence > 0 ? (
                            <span className="badge badge-accent">{v.confidence}% AI</span>
                          ) : isGenerating ? (
                            <span className="badge badge-warning text-[9px]">Generating...</span>
                          ) : hasError ? (
                            <span className="badge badge-danger text-[9px]">Error</span>
                          ) : null}
                        </div>
                        <div className="grid grid-cols-3 gap-2 mb-3 text-center">
                          <div><div className="font-mono text-xs text-text">{v.views}</div><div className="text-[9px] text-text-muted">views</div></div>
                          <div><div className="font-mono text-xs text-text">{v.ctr}</div><div className="text-[9px] text-text-muted">CTR</div></div>
                          <div><div className="font-mono text-xs text-text">{isGenerating ? "..." : scenes.length || v.scenes}</div><div className="text-[9px] text-text-muted">scenes</div></div>
                        </div>

                        {/* Inline AI Script — collapsible */}
                        {hasScript && (
                          <div className="mb-3">
                            <button
                              onClick={() => setExpandedId(isExpanded ? null : v.id)}
                              className="w-full flex items-center justify-between p-2 rounded-lg bg-accent/5 border border-accent/15 hover:bg-accent/10 transition-all"
                            >
                              <span className="text-[10px] font-medium flex items-center gap-1 text-accent">
                                <Sparkles className="w-3 h-3" /> Full Script ({scenes.length} scenes)
                              </span>
                              <span className="text-[9px] text-text-muted">{isExpanded ? "▲ Collapse" : "▼ Expand"}</span>
                            </button>
                            {isExpanded && (
                              <div className="mt-2 max-h-48 overflow-y-auto p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                                <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">{vd.script}</p>
                              </div>
                            )}
                          </div>
                        )}

                        {hasError && (
                          <div className="mb-3 rounded-lg border p-3 bg-danger/5 border-danger/20">
                            <span className="text-[10px] font-medium flex items-center gap-1 text-danger mb-1">
                              <AlertTriangle className="w-3 h-3" /> Error
                            </span>
                            <p className="text-xs text-danger/80 leading-relaxed">{vd.script}</p>
                          </div>
                        )}

                        <div className="flex gap-1.5">
                          <button className="btn-secondary text-xs px-2 py-1 flex-1"><Download className="w-3 h-3" /></button>
                          <button className="btn-secondary text-xs px-2 py-1 flex-1" disabled={isGenerating}>Publish</button>
                          <button className="btn-secondary text-xs px-2 py-1"><RefreshCw className="w-3 h-3" /></button>
                        </div>
                      </Card3D>
                    </motion.div>
                  );
                })}
                </div>
              )}
            </>
          )}

          {tab === "Video Templates" && (
            <EmptyState
              icon={<Layers className="w-6 h-6 text-accent" />}
              title="Templates coming soon"
              description="Pre-built video templates will be available here in a future update. For now, generate videos from your own prompts."
            />
          )}
          {tab === "Voice Library" && (
            <EmptyState
              icon={<Mic className="w-6 h-6 text-accent" />}
              title="Voice options coming soon"
              description="A library of AI voices in multiple languages and accents will be available here in a future update."
            />
          )}

          {tab === "Performance" && (
            <EmptyState
              icon={<TrendingUp className="w-6 h-6 text-accent" />}
              title="No videos generated yet"
              description="Performance analytics will appear here once you have generated and published videos."
            />
          )}
        </div>

        {/* Right: Performance + AI */}
        <div className="lg:col-span-3 space-y-4">
          <Card>
            <SectionHeader title="Video Performance" subtitle="Published videos" />
            {videos.length === 0 ? (
              <p className="text-xs text-text-muted text-center py-6">No videos generated yet.</p>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">Videos generated</span>
                  <span className="font-mono text-xs text-text">{videos.length}</span>
                </div>
              </div>
            )}
          </Card>

          <AIStatusBlock
            status={videos.length > 0 ? "done" : "idle"}
            label={videos.length > 0 ? "Videos generated" : "No videos yet"}
            detail={videos.length > 0 ? `${videos.length} video${videos.length > 1 ? "s" : ""} created` : "Generate your first video"}
          />

          <Card>
            <SectionHeader title="AI Recommendations" />
            <div className="space-y-2">
              <div className="p-2.5 rounded-lg bg-accent/5 border border-accent/10">
                <p className="text-xs text-text-secondary">Reels under 30s get more completions. Keep videos concise.</p>
              </div>
              <div className="p-2.5 rounded-lg bg-info/5 border border-info/10">
                <p className="text-xs text-text-secondary">Add captions — most users watch with sound off.</p>
              </div>
              <div className="p-2.5 rounded-lg bg-success/5 border border-success/10">
                <p className="text-xs text-text-secondary">Use specific prompts for better AI video results.</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
