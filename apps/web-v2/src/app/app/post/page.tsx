"use client";

/**
 * Create Post — Facebook-style composer. Caption + optional image/video +
 * channel picker. Publishes synchronously via POST /brands/{id}/publish.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { apiGet, apiPost, apiUpload, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import {
  ImageIcon, VideoIcon, X, ArrowUp, Loader2, CheckCircle2,
  AlertCircle, PenSquare, Link2, Clock, Sparkles, Layers, ChevronLeft, ChevronRight, Wand2,
} from "lucide-react";

interface SlideItem {
  url: string;
  preview: string;
  headline?: string;
}

interface Connection {
  id: string;
  channel: string;
  status: string;
}

interface PublishResult {
  channel: string;
  ok: boolean;
  url?: string;
  error?: string;
}

// Channels that support a quick caption+media post through their adapters
const POSTABLE = ["facebook", "instagram", "youtube", "linkedin", "x", "telegram"];
const MEDIA_REQUIRED = new Set(["instagram"]);
const VIDEO_REQUIRED = new Set(["youtube"]);
const CHAT_ID_CHANNELS = new Set(["telegram"]);

const CHANNEL_LABEL: Record<string, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  linkedin: "LinkedIn",
  x: "X (Twitter)",
  telegram: "Telegram",
  youtube: "YouTube",
};

export default function PostPage() {
  const { brand } = useActiveBrand();
  const fileRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [slides, setSlides] = useState<SlideItem[]>([]);
  const [mediaType, setMediaType] = useState<"image" | "video">("image");
  const [uploading, setUploading] = useState(false);
  const [generatingCarousel, setGeneratingCarousel] = useState(false);
  const [finishingVideo, setFinishingVideo] = useState(false);
  const [carouselSlidesCount, setCarouselSlidesCount] = useState(5);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const vUrl = params.get("video_url");
    const cap = params.get("caption");
    if (vUrl) {
      setMediaType("video");
      setSlides([{ url: vUrl, preview: vUrl }]);
    }
    if (cap) {
      setText(cap);
    }
  }, []);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [telegramChatId, setTelegramChatId] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [scheduleAt, setScheduleAt] = useState("");
  const [results, setResults] = useState<PublishResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaUrl = slides[0]?.url ?? null;
  const mediaUrls = slides.map((s) => s.url);

  const queryClient = useQueryClient();
  const { data: connections } = useQuery<Connection[]>({
    queryKey: ["connections"],
    queryFn: () => apiGet("/connections"),
    retry: 1,
  });

  const activeChannels = new Set(
    (connections ?? []).filter((c) => c.status === "active").map((c) => c.channel),
  );
  // All supported channels render; unconnected ones are disabled with a
  // connect hint — you can't publish where nothing is connected.
  const postableChannels = POSTABLE;

  const toggle = (ch: string) => {
    const next = new Set(selected);
    next.has(ch) ? next.delete(ch) : next.add(ch);
    setSelected(next);
    setResults(null);
  };

  const pickFile = (type: "image" | "video") => {
    setMediaType(type);
    if (fileRef.current) {
      fileRef.current.accept = type === "image" ? "image/*" : "video/*";
      fileRef.current.multiple = type === "image";
      fileRef.current.click();
    }
  };

  const onFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0 || !brand?.id) return;
    setUploading(true);
    setError(null);
    try {
      const incoming = Array.from(fileList).slice(0, 10 - slides.length);
      const uploaded: SlideItem[] = [];
      for (const f of incoming) {
        const preview = URL.createObjectURL(f);
        const fd = new FormData();
        fd.append("file", f);
        const res = await apiUpload<{ media_url: string }>(`/brands/${brand.id}/media/upload`, fd);
        uploaded.push({ url: res.media_url, preview });
      }
      setSlides((prev) => (mediaType === "video" ? uploaded.slice(0, 1) : [...prev, ...uploaded].slice(0, 10)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeSlide = (idx: number) => {
    setSlides((prev) => prev.filter((_, i) => i !== idx));
  };

  const moveSlide = (idx: number, dir: -1 | 1) => {
    setSlides((prev) => {
      const target = idx + dir;
      if (target < 0 || target >= prev.length) return prev;
      const copy = [...prev];
      const [item] = copy.splice(idx, 1);
      if (item) copy.splice(target, 0, item);
      return copy;
    });
  };

  const generateAICarousel = async () => {
    if (!brand?.id || generatingCarousel) return;
    setGeneratingCarousel(true);
    setError(null);
    try {
      const res = await apiPost<{
        caption: string;
        slides: { slide_number: number; headline: string; body: string; media_url: string }[];
      }>(`/brands/${brand.id}/carousel/generate`, {
        topic: text.trim(),
        slides_count: carouselSlidesCount,
      });
      setMediaType("image");
      setSlides(
        res.slides.map((s) => ({
          url: s.media_url,
          preview: s.media_url,
          headline: s.headline,
        }))
      );
      if (!text.trim() && res.caption) {
        setText(res.caption);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to generate carousel");
    } finally {
      setGeneratingCarousel(false);
    }
  };

  const submit = async (scheduledAt: string | null) => {
    if (!brand?.id || selected.size === 0 || publishing) return;
    setPublishing(true);
    setError(null);
    try {
      const out: PublishResult[] = [];
      for (const ch of selected) {
        try {
          if (scheduledAt) {
            await apiPost<{ scheduled_at: string }>(`/brands/${brand.id}/schedule`, {
              channel: ch,
              text,
              media_url: mediaUrl,
              media_urls: mediaUrls,
              media_type: mediaType,
              chat_id: ch === "telegram" ? telegramChatId : null,
              scheduled_at: new Date(scheduledAt).toISOString(),
            });
            out.push({ channel: ch, ok: true, url: undefined });
          } else {
            const res = await apiPost<{ url: string | null }>(`/brands/${brand.id}/publish`, {
              channel: ch,
              text,
              media_url: mediaUrl,
              media_urls: mediaUrls,
              media_type: mediaType,
              chat_id: ch === "telegram" ? telegramChatId : null,
            });
            out.push({ channel: ch, ok: true, url: res.url ?? undefined });
          }
        } catch (e) {
          out.push({ channel: ch, ok: false, error: e instanceof ApiError ? e.message : "Publish failed" });
        }
      }
      setResults(out);
      queryClient.invalidateQueries({ queryKey: ["brand-content"] });
      if (!scheduledAt) {
        // Kick a provider-metrics pull so the dashboard reflects the new post.
        queryClient.invalidateQueries({ queryKey: ["metrics-summary"] });
        apiPost(`/brands/${brand.id}/metrics/sync`).catch(() => {});
      } else {
        queryClient.invalidateQueries({ queryKey: ["scheduled-posts"] });
      }
      // Reset the composer when everything succeeded
      if (out.every((r) => r.ok)) {
        setText("");
        setSlides([]);
        setSelected(new Set());
      }
    } finally {
      setPublishing(false);
    }
  };

  const publish = () => submit(scheduleAt || null);

  const canPublish = selected.size > 0 && (text.trim() || mediaUrl)
    && !publishing && !uploading
    && [...selected].every((ch) => !MEDIA_REQUIRED.has(ch) || mediaUrl)
    && [...selected].every((ch) => !VIDEO_REQUIRED.has(ch) || (mediaUrl && mediaType === "video"))
    && (!selected.has("telegram") || telegramChatId.trim());

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center">
          <PenSquare className="w-4 h-4 text-accent" />
        </div>
        <div>
          <h1 className="font-display text-xl font-semibold text-text">Create Post</h1>
          <p className="text-xs text-text-secondary">Write a caption, pick your channels, post.</p>
        </div>
      </div>

      <div className="rounded-2xl border border-line/10 bg-bg-card p-5 space-y-4">
        {/* Caption */}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={brand?.name ? `What's on your mind, ${brand.name}?` : "What's on your mind?"}
          rows={5}
          className="w-full resize-none bg-transparent text-[15px] text-text placeholder:text-text-muted focus:outline-none"
        />

        {/* Media / Carousel preview */}
        <AnimatePresence>
          {slides.length > 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-2"
            >
              {slides.length > 1 && (
                <div className="flex items-center justify-between text-xs text-text-secondary">
                  <span className="inline-flex items-center gap-1.5 font-medium text-accent">
                    <Layers className="w-3.5 h-3.5" /> Carousel · {slides.length} slides
                  </span>
                  <button
                    type="button"
                    onClick={() => setSlides([])}
                    className="text-text-muted hover:text-text transition"
                  >
                    Clear all
                  </button>
                </div>
              )}

              {mediaType === "video" && slides[0] ? (
                <div className="space-y-2">
                  <div className="relative rounded-xl overflow-hidden bg-bg-hover">
                    <video src={slides[0].preview} controls className="w-full max-h-72" />
                    <button
                      type="button"
                      onClick={() => setSlides([])}
                      className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-text-secondary truncate">
                      {slides[0].headline ? `✓ Hook: ${slides[0].headline}` : "Raw clip attached — burn hook, captions & watermark in 1 click"}
                    </span>
                    <button
                      type="button"
                      disabled={finishingVideo || !brand?.id}
                      onClick={async () => {
                        if (!brand?.id || !slides[0]) return;
                        setFinishingVideo(true);
                        setError(null);
                        try {
                          const res = await apiPost<{
                            video_url: string;
                            hook_title: string;
                            caption_text: string;
                          }>(`/brands/${brand.id}/video/finish`, {
                            video_url: slides[0].url,
                            prompt_context: text.trim(),
                          });
                          setSlides([
                            {
                              url: res.video_url,
                              preview: res.video_url,
                              headline: res.hook_title,
                            },
                          ]);
                          if (!text.trim() && res.caption_text) {
                            setText(res.caption_text);
                          }
                        } catch (e) {
                          setError(e instanceof ApiError ? e.message : "Failed to finish video");
                        } finally {
                          setFinishingVideo(false);
                        }
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/15 border border-accent/30 text-xs font-medium text-accent hover:bg-accent/25 transition disabled:opacity-50 shrink-0"
                    >
                      {finishingVideo ? (
                        <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Finishing…</>
                      ) : (
                        <><Wand2 className="w-3.5 h-3.5" /> Auto-Finish Video</>
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  {slides.map((sl, idx) => (
                    <div
                      key={`${sl.url}-${idx}`}
                      className="relative group rounded-xl overflow-hidden bg-bg-hover border border-line/10 aspect-square"
                    >
                      <img src={sl.preview} alt={sl.headline ?? `Slide ${idx + 1}`} className="w-full h-full object-cover" />
                      <span className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/70 text-[10px] font-semibold text-white">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeSlide(idx)}
                        className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black/90"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      {slides.length > 1 && (
                        <div className="absolute bottom-2 inset-x-2 flex justify-between opacity-0 group-hover:opacity-100 transition">
                          <button
                            type="button"
                            disabled={idx === 0}
                            onClick={() => moveSlide(idx, -1)}
                            className="w-6 h-6 rounded-md bg-black/70 text-white flex items-center justify-center disabled:opacity-30"
                          >
                            <ChevronLeft className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            disabled={idx === slides.length - 1}
                            onClick={() => moveSlide(idx, 1)}
                            className="w-6 h-6 rounded-md bg-black/70 text-white flex items-center justify-center disabled:opacity-30"
                          >
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Attachment + AI Carousel row */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-line/10">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-text-secondary mr-1">Add:</span>
            <button
              type="button"
              onClick={() => pickFile("image")}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-hover text-xs text-text-secondary hover:text-text"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5 text-emerald-400" />}
              {slides.length > 0 && mediaType === "image" ? "Add Slide" : "Photo / Carousel"}
            </button>
            <button
              type="button"
              onClick={() => pickFile("video")}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-hover text-xs text-text-secondary hover:text-text"
            >
              <VideoIcon className="w-3.5 h-3.5 text-sky-400" /> Video
            </button>
            <input ref={fileRef} type="file" className="hidden" onChange={(e) => onFiles(e.target.files)} />
          </div>

          <div className="flex items-center gap-1.5">
            <select
              value={carouselSlidesCount}
              onChange={(e) => setCarouselSlidesCount(Number(e.target.value))}
              className="bg-bg-hover text-text-secondary text-xs rounded-lg px-2 py-1.5 border border-line/10 outline-none"
            >
              {[3, 5, 7].map((n) => (
                <option key={n} value={n} className="bg-bg-card">
                  {n} slides
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={generateAICarousel}
              disabled={generatingCarousel || !brand?.id}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/15 border border-accent/30 text-xs font-medium text-accent hover:bg-accent/25 transition disabled:opacity-50"
            >
              {generatingCarousel ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Designing…</>
              ) : (
                <><Sparkles className="w-3.5 h-3.5" /> AI Carousel</>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Channel picker */}
      <div className="rounded-2xl border border-line/10 bg-bg-card p-5">
        <div className="text-xs text-text-secondary mb-3">Post to:</div>
        {postableChannels.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {postableChannels.map((ch) => {
              const connected = activeChannels.has(ch);
              return connected ? (
                <button
                  key={ch}
                  onClick={() => toggle(ch)}
                  className={cn(
                    "inline-flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-all",
                    selected.has(ch)
                      ? "border-accent/50 bg-accent/10 text-accent"
                      : "border-line/10 bg-bg-hover text-text-secondary hover:text-text",
                  )}
                >
                  {selected.has(ch) && <CheckCircle2 className="w-3.5 h-3.5" />}
                  {CHANNEL_LABEL[ch] ?? ch}
                </button>
              ) : (
                <Link
                  key={ch}
                  href="/app/connections"
                  title={`${CHANNEL_LABEL[ch] ?? ch} — connect first`}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-line/10 text-sm text-text-muted opacity-60 hover:opacity-100 transition-opacity"
                >
                  <Link2 className="w-3.5 h-3.5" />
                  {CHANNEL_LABEL[ch] ?? ch}
                  <span className="text-[10px] text-accent">connect</span>
                </Link>
              );
            })}
          </div>
        ) : null}

        {selected.has("telegram") && (
          <input
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            placeholder="Telegram chat ID (e.g. -1001234567890 or @channelname)"
            className="mt-3 w-full px-3 py-2 rounded-lg bg-bg-hover border border-line/10 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent/40"
          />
        )}
        {[...selected].some((ch) => MEDIA_REQUIRED.has(ch)) && !mediaUrl && (
          <p className="mt-3 text-xs text-amber-400 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" /> Instagram requires a photo or video — attach one above.
          </p>
        )}
        {[...selected].some((ch) => VIDEO_REQUIRED.has(ch)) && !(mediaUrl && mediaType === "video") && (
          <p className="mt-3 text-xs text-amber-400 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" /> YouTube uploads a video — attach one above (it becomes your video title/description).
          </p>
        )}
      </div>

      {/* Results */}
      <AnimatePresence>
        {results && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-line/10 bg-bg-card p-4 space-y-2"
          >
            {results.map((r) => (
              <div key={r.channel} className="flex items-center gap-3 text-sm">
                {r.ok
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  : <AlertCircle className="w-4 h-4 text-danger shrink-0" />}
                <span className="text-text">{CHANNEL_LABEL[r.channel] ?? r.channel}</span>
                {r.ok && r.url ? (
                  <a href={r.url} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline ml-auto">View post →</a>
                ) : r.ok ? (
                  <span className="text-xs text-emerald-400 ml-auto">Published</span>
                ) : (
                  <span className="text-xs text-danger ml-auto truncate max-w-[280px]">{r.error}</span>
                )}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Schedule (optional) — leave empty to post now */}
      <div className="flex items-center gap-3 rounded-xl border border-line/10 bg-bg-card px-4 py-2.5">
        <Clock className="w-4 h-4 text-text-muted shrink-0" />
        <label className="text-xs text-text-secondary shrink-0">Schedule for</label>
        <input
          type="datetime-local"
          value={scheduleAt}
          onChange={(e) => setScheduleAt(e.target.value)}
          min={new Date(Date.now() + 60_000).toISOString().slice(0, 16)}
          className="flex-1 bg-transparent text-sm text-text focus:outline-none [color-scheme:dark]"
        />
        {scheduleAt && (
          <button
            onClick={() => setScheduleAt("")}
            className="text-xs text-text-muted hover:text-text transition"
          >
            Clear
          </button>
        )}
      </div>

      {/* Publish */}
      <button
        onClick={publish}
        disabled={!canPublish}
        className={cn(
          "w-full py-3.5 rounded-2xl font-semibold text-sm flex items-center justify-center gap-2 transition-all",
          canPublish
            ? "bg-gradient-to-br from-accent to-accent-dark text-white shadow-glow hover:opacity-90"
            : "bg-bg-hover text-text-muted cursor-not-allowed",
        )}
      >
        {publishing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-4 h-4" />}
        {publishing
          ? (scheduleAt ? "Scheduling…" : "Posting…")
          : scheduleAt
            ? `Schedule${selected.size > 0 ? ` to ${selected.size} channel${selected.size > 1 ? "s" : ""}` : ""}`
            : `Post${selected.size > 0 ? ` to ${selected.size} channel${selected.size > 1 ? "s" : ""}` : ""}`}
      </button>
    </div>
  );
}
