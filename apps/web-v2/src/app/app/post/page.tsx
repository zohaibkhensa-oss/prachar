"use client";

/**
 * Create Post — Facebook-style composer. Caption + optional image/video +
 * channel picker. Publishes synchronously via POST /brands/{id}/publish.
 */

import { useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { apiGet, apiPost, apiUpload, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import {
  ImageIcon, VideoIcon, X, ArrowUp, Loader2, CheckCircle2,
  AlertCircle, PenSquare, Link2, Users,
} from "lucide-react";

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
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<"image" | "video">("image");
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [telegramChatId, setTelegramChatId] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [results, setResults] = useState<PublishResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      fileRef.current.click();
    }
  };

  const onFile = async (f: File | null) => {
    if (!f || !brand?.id) return;
    setUploading(true);
    setError(null);
    setMediaPreview(URL.createObjectURL(f));
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await apiUpload<{ media_url: string }>(`/brands/${brand.id}/media/upload`, fd);
      setMediaUrl(res.media_url);
    } catch (e) {
      setMediaPreview(null);
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const publish = async () => {
    if (!brand?.id || selected.size === 0 || publishing) return;
    setPublishing(true);
    setError(null);
    try {
      const out: PublishResult[] = [];
      for (const ch of selected) {
        try {
          const res = await apiPost<{ url: string | null }>(`/brands/${brand.id}/publish`, {
            channel: ch,
            text,
            media_url: mediaUrl,
            media_type: mediaType,
            chat_id: ch === "telegram" ? telegramChatId : null,
          });
          out.push({ channel: ch, ok: true, url: res.url ?? undefined });
        } catch (e) {
          out.push({ channel: ch, ok: false, error: e instanceof ApiError ? e.message : "Publish failed" });
        }
      }
      setResults(out);
      // Refresh the data surfaces and kick a provider-metrics pull so the
      // dashboard reflects the new post + any analytics already available.
      queryClient.invalidateQueries({ queryKey: ["brand-content"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-summary"] });
      apiPost(`/brands/${brand.id}/metrics/sync`).catch(() => {});
      // Reset the composer when everything succeeded
      if (out.every((r) => r.ok)) {
        setText("");
        setMediaUrl(null);
        setMediaPreview(null);
        setSelected(new Set());
      }
    } finally {
      setPublishing(false);
    }
  };

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

        {/* Media preview */}
        <AnimatePresence>
          {mediaPreview && (
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              className="relative rounded-xl overflow-hidden bg-bg-hover"
            >
              {mediaType === "image" ? (
                <img src={mediaPreview} alt="" className="w-full max-h-72 object-cover" />
              ) : (
                <video src={mediaPreview} controls className="w-full max-h-72" />
              )}
              <button
                onClick={() => { setMediaUrl(null); setMediaPreview(null); }}
                className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80"
              >
                <X className="w-4 h-4" />
              </button>
              {uploading && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-white animate-spin" />
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Attachment row */}
        <div className="flex items-center gap-2 pt-3 border-t border-line/10">
          <span className="text-xs text-text-secondary mr-1">Add:</span>
          <button onClick={() => pickFile("image")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-hover text-xs text-text-secondary hover:text-text">
            <ImageIcon className="w-3.5 h-3.5 text-emerald-400" /> Photo
          </button>
          <button onClick={() => pickFile("video")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-hover text-xs text-text-secondary hover:text-text">
            <VideoIcon className="w-3.5 h-3.5 text-sky-400" /> Video
          </button>
          <input ref={fileRef} type="file" className="hidden" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
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
        {publishing ? "Posting…" : `Post${selected.size > 0 ? ` to ${selected.size} channel${selected.size > 1 ? "s" : ""}` : ""}`}
      </button>
    </div>
  );
}
