"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiPost } from "@/lib/api";
import type { RepurposeResponse, RepurposedAsset } from "@/lib/creator";
import {
  RefreshCw,
  Sparkles,
  ArrowRight,
  Copy,
  Check,
  Loader2,
  Video,
  FileText,
  Mail,
  Send,
  MessageSquare,
  Podcast,
  Handshake,
  Newspaper,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ASSET_META: Record<string, { icon: typeof Video; color: string }> = {
  "YouTube Shorts": { icon: Video, color: "text-danger" },
  "Instagram Reels": { icon: Video, color: "text-info" },
  "Facebook Reel": { icon: Video, color: "text-info" },
  "LinkedIn Post": { icon: FileText, color: "text-info" },
  "X Thread": { icon: Send, color: "text-text" },
  "Blog Article": { icon: Newspaper, color: "text-accent" },
  "Newsletter": { icon: Mail, color: "text-accent" },
  "Email": { icon: Mail, color: "text-success" },
  "Community Post": { icon: MessageSquare, color: "text-warning" },
  "Podcast Summary": { icon: Podcast, color: "text-danger" },
  "Sponsor Pitch": { icon: Handshake, color: "text-success" },
};

export default function RepurposePage() {
  const [videoTitle, setVideoTitle] = useState("");
  const [videoDescription, setVideoDescription] = useState("");
  const [niche, setNiche] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<RepurposeResponse | null>(null);
  const [error, setError] = useState("");
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  async function handleRepurpose() {
    if (videoDescription.trim().length < 10) return;
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const res = await apiPost<RepurposeResponse>("/creator/repurpose", {
        video_title: videoTitle,
        video_description: videoDescription,
        niche,
      });
      setResponse(res);
    } catch (e) {
      setError("I couldn't repurpose this video right now. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function copyAsset(idx: number, content: string) {
    navigator.clipboard.writeText(content);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* ─── Header ─── */}
      <div>
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 mb-3">
          <RefreshCw className="w-3 h-3 text-accent" />
          <span className="font-mono text-[10px] text-accent uppercase tracking-wider">Content repurposing</span>
        </div>
        <h1 className="font-display text-2xl font-semibold text-text">Turn one video into 11 assets</h1>
        <p className="text-sm text-text-secondary mt-1.5 max-w-lg">
          Paste your YouTube video title and description (or a transcript summary).
          I'll create Shorts, Reels, posts, blog, newsletter, and more — each ready to edit.
        </p>
      </div>

      {/* ─── Input form ─── */}
      <div className="glass-strong rounded-2xl p-6 space-y-4">
        <div>
          <label className="label-field">Video title <span className="text-text-muted">(optional)</span></label>
          <input
            type="text"
            value={videoTitle}
            onChange={(e) => setVideoTitle(e.target.value)}
            placeholder="e.g. I tested the ₹500 phone for 30 days"
            className="input-field mt-1.5"
          />
        </div>
        <div>
          <label className="label-field">Video description or transcript summary</label>
          <textarea
            value={videoDescription}
            onChange={(e) => setVideoDescription(e.target.value)}
            placeholder="Paste your video description, a transcript summary, or the key points you cover..."
            rows={6}
            className="input-field mt-1.5 resize-y"
          />
          <p className="text-[11px] text-text-muted mt-1.5">
            The more detail you give, the better the repurposed assets will be.
          </p>
        </div>
        <div>
          <label className="label-field">Your niche <span className="text-text-muted">(optional)</span></label>
          <input
            type="text"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            placeholder="e.g. tech reviews, gaming, education"
            className="input-field mt-1.5"
          />
        </div>
        <button
          onClick={handleRepurpose}
          disabled={loading || videoDescription.trim().length < 10}
          className="btn-primary w-full sm:w-auto group"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {loading ? "Repurposing…" : "Repurpose into 11 assets"}
          {!loading && <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />}
        </button>
      </div>

      {/* ─── Error ─── */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-danger/5 border border-danger/10">
          <AlertCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
          <div className="text-sm text-danger">{error}</div>
        </div>
      )}

      {/* ─── Loading state ─── */}
      {loading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass rounded-2xl p-8 text-center"
        >
          <Loader2 className="w-6 h-6 text-accent animate-spin mx-auto mb-3" />
          <p className="text-sm text-text-secondary">
            Creating Shorts, Reels, posts, blog, newsletter, and more…
          </p>
        </motion.div>
      )}

      {/* ─── Results ─── */}
      <AnimatePresence>
        {response && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* PRACHAR AI's reply */}
            {response.reply && (
              <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                    <Sparkles className="w-4 h-4 text-accent" />
                  </div>
                  <p className="text-sm text-text leading-relaxed">{response.reply}</p>
                </div>
              </div>
            )}

            {/* Assets grid */}
            <div className="grid grid-cols-1 gap-3">
              {response.assets.map((asset, idx) => (
                <AssetCard
                  key={idx}
                  asset={asset}
                  idx={idx}
                  copied={copiedIdx === idx}
                  onCopy={() => copyAsset(idx, asset.content)}
                />
              ))}
            </div>

            <p className="text-[11px] text-text-muted text-center pt-2">
              Each asset is a starting point — edit before posting.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AssetCard({
  asset,
  idx,
  copied,
  onCopy,
}: {
  asset: RepurposedAsset;
  idx: number;
  copied: boolean;
  onCopy: () => void;
}) {
  const meta = ASSET_META[asset.asset_type] ?? { icon: FileText, color: "text-text-muted" };
  const Icon = meta.icon;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.06 }}
      className="glass-strong rounded-xl p-5"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div className={cn("w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center shrink-0", meta.color)}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-display text-sm font-semibold text-text">{asset.asset_type}</h3>
            {asset.notes && <p className="text-[11px] text-text-muted mt-0.5">{asset.notes}</p>}
          </div>
        </div>
        <button
          onClick={onCopy}
          className="btn-secondary text-xs shrink-0"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap font-mono text-[13px] bg-white/[0.02] rounded-lg p-3 max-h-[300px] overflow-y-auto">
        {asset.content}
      </div>
    </motion.div>
  );
}
