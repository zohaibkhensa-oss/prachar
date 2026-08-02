"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiPost } from "@/lib/api";
import type { YouTubePlanResponse, YouTubePlan } from "@/lib/creator";
import {
  Video,
  Image as ImageIcon,
  Sparkles,
  ArrowRight,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  Type,
  Eye,
  Clock,
  FileText,
  Search,
  Tag,
  List,
  MessageSquare,
  Users,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function YouTubePlanPage() {
  const [concept, setConcept] = useState("");
  const [niche, setNiche] = useState("");
  const [audience, setAudience] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<YouTubePlanResponse | null>(null);
  const [error, setError] = useState("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  async function handleGenerate() {
    if (concept.trim().length < 5) return;
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const res = await apiPost<YouTubePlanResponse>("/creator/youtube-plan", {
        video_concept: concept,
        niche,
        audience,
      });
      setResponse(res);
    } catch (e) {
      setError("I couldn't build the video plan right now. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function copy(key: string, content: string) {
    navigator.clipboard.writeText(content);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* ─── Header ─── */}
      <div>
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-danger/10 border border-danger/20 mb-3">
          <Video className="w-3 h-3 text-danger" />
          <span className="font-mono text-[10px] text-danger uppercase tracking-wider">YouTube planning</span>
        </div>
        <h1 className="font-display text-2xl font-semibold text-text">Plan your next YouTube video</h1>
        <p className="text-sm text-text-secondary mt-1.5 max-w-lg">
          Give me your video concept. I'll create titles, thumbnails, hooks, retention techniques,
          description, SEO keywords, tags, chapters, pinned comment, community post, and end screen suggestions.
        </p>
      </div>

      {/* ─── Input ─── */}
      <div className="glass-strong rounded-2xl p-6 space-y-4">
        <div>
          <label className="label-field">Video concept</label>
          <textarea
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="e.g. I'm reviewing the new iPhone 16 Pro — focusing on camera, battery, and whether it's worth upgrading from the 15 Pro."
            rows={3}
            className="input-field mt-1.5 resize-y"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label-field">Your niche <span className="text-text-muted">(optional)</span></label>
            <input
              type="text"
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              placeholder="e.g. tech reviews"
              className="input-field mt-1.5"
            />
          </div>
          <div>
            <label className="label-field">Target audience <span className="text-text-muted">(optional)</span></label>
            <input
              type="text"
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              placeholder="e.g. Indian tech enthusiasts"
              className="input-field mt-1.5"
            />
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading || concept.trim().length < 5}
          className="btn-primary w-full sm:w-auto group"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {loading ? "Planning your video…" : "Generate video plan"}
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

      {/* ─── Loading ─── */}
      {loading && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-2xl p-8 text-center">
          <Loader2 className="w-6 h-6 text-accent animate-spin mx-auto mb-3" />
          <p className="text-sm text-text-secondary">
            Writing titles, thumbnails, hooks, SEO, chapters, and more…
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
            {response.reply && (
              <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-danger/50">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-danger/10 flex items-center justify-center shrink-0">
                    <Sparkles className="w-4 h-4 text-danger" />
                  </div>
                  <p className="text-sm text-text leading-relaxed">{response.reply}</p>
                </div>
              </div>
            )}

            <YouTubePlanView plan={response.plan} copiedKey={copiedKey} onCopy={copy} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function YouTubePlanView({
  plan,
  copiedKey,
  onCopy,
}: {
  plan: YouTubePlan;
  copiedKey: string | null;
  onCopy: (key: string, content: string) => void;
}) {
  return (
    <div className="space-y-4">
      {/* Title options */}
      {plan.title_options.length > 0 && (
        <PlanSection icon={<Type className="w-4 h-4 text-accent" />} title="Title options" copyKey="titles" copied={copiedKey === "titles"} onCopy={() => onCopy("titles", plan.title_options.join("\n"))}>
          <div className="space-y-2">
            {plan.title_options.map((title, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02]">
                <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center shrink-0 font-mono text-xs text-accent">
                  {i + 1}
                </div>
                <span className="text-sm text-text">{title}</span>
              </div>
            ))}
          </div>
        </PlanSection>
      )}

      {/* Thumbnail concepts */}
      {plan.thumbnail_concepts.length > 0 && (
        <PlanSection icon={<ImageIcon className="w-4 h-4 text-info" />} title="Thumbnail concepts" copyKey="thumbs" copied={copiedKey === "thumbs"} onCopy={() => onCopy("thumbs", plan.thumbnail_concepts.join("\n\n"))}>
          <div className="space-y-2">
            {plan.thumbnail_concepts.map((thumb, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02]">
                <div className="w-6 h-6 rounded-full bg-info/10 flex items-center justify-center shrink-0 font-mono text-xs text-info">
                  {i + 1}
                </div>
                <span className="text-sm text-text-secondary">{thumb}</span>
              </div>
            ))}
          </div>
        </PlanSection>
      )}

      {/* Opening hook */}
      {plan.opening_hook && (
        <PlanSection icon={<Sparkles className="w-4 h-4 text-warning" />} title="Opening hook (first 10 seconds)" copyKey="hook" copied={copiedKey === "hook"} onCopy={() => onCopy("hook", plan.opening_hook)}>
          <p className="text-sm text-text-secondary leading-relaxed italic">"{plan.opening_hook}"</p>
        </PlanSection>
      )}

      {/* Retention improvements */}
      {plan.retention_improvements.length > 0 && (
        <PlanSection icon={<Clock className="w-4 h-4 text-success" />} title="Keep viewers watching">
          <ul className="space-y-2">
            {plan.retention_improvements.map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-success mt-2 shrink-0" />
                <span className="text-sm text-text-secondary">{r}</span>
              </li>
            ))}
          </ul>
        </PlanSection>
      )}

      {/* Description */}
      {plan.description && (
        <PlanSection icon={<FileText className="w-4 h-4 text-accent" />} title="Video description" copyKey="desc" copied={copiedKey === "desc"} onCopy={() => onCopy("desc", plan.description)}>
          <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap font-mono text-[13px] bg-white/[0.02] rounded-lg p-3 max-h-[300px] overflow-y-auto">
            {plan.description}
          </div>
        </PlanSection>
      )}

      {/* SEO keywords + Tags */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {plan.seo_keywords.length > 0 && (
          <PlanSection icon={<Search className="w-4 h-4 text-info" />} title="SEO keywords">
            <div className="flex flex-wrap gap-1.5">
              {plan.seo_keywords.map((kw, i) => (
                <span key={i} className="badge badge-neutral text-[10px]">{kw}</span>
              ))}
            </div>
          </PlanSection>
        )}
        {plan.tags.length > 0 && (
          <PlanSection icon={<Tag className="w-4 h-4 text-text-muted" />} title="Tags">
            <div className="flex flex-wrap gap-1.5">
              {plan.tags.map((tag, i) => (
                <span key={i} className="badge badge-neutral text-[10px]">{tag}</span>
              ))}
            </div>
          </PlanSection>
        )}
      </div>

      {/* Chapters */}
      {plan.chapters.length > 0 && (
        <PlanSection icon={<List className="w-4 h-4 text-accent" />} title="Chapters" copyKey="chapters" copied={copiedKey === "chapters"} onCopy={() => onCopy("chapters", plan.chapters.join("\n"))}>
          <div className="space-y-1.5">
            {plan.chapters.map((ch, i) => (
              <div key={i} className="text-sm text-text-secondary font-mono text-[13px]">{ch}</div>
            ))}
          </div>
        </PlanSection>
      )}

      {/* Pinned comment + Community post */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {plan.pinned_comment && (
          <PlanSection icon={<MessageSquare className="w-4 h-4 text-warning" />} title="Pinned comment" copyKey="pinned" copied={copiedKey === "pinned"} onCopy={() => onCopy("pinned", plan.pinned_comment)}>
            <p className="text-sm text-text-secondary italic">"{plan.pinned_comment}"</p>
          </PlanSection>
        )}
        {plan.community_post && (
          <PlanSection icon={<Users className="w-4 h-4 text-info" />} title="Community post" copyKey="community" copied={copiedKey === "community"} onCopy={() => onCopy("community", plan.community_post)}>
            <p className="text-sm text-text-secondary italic">"{plan.community_post}"</p>
          </PlanSection>
        )}
      </div>

      {/* End screen suggestions */}
      {plan.end_screen_suggestions.length > 0 && (
        <PlanSection icon={<Target className="w-4 h-4 text-success" />} title="End screen suggestions">
          <ul className="space-y-2">
            {plan.end_screen_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-success mt-2 shrink-0" />
                <span className="text-sm text-text-secondary">{s}</span>
              </li>
            ))}
          </ul>
        </PlanSection>
      )}
    </div>
  );
}

function PlanSection({
  icon,
  title,
  children,
  copyKey,
  copied,
  onCopy,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  copyKey?: string;
  copied?: boolean;
  onCopy?: () => void;
}) {
  return (
    <div className="glass-strong rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-display text-sm font-semibold text-text">{title}</h3>
        </div>
        {copyKey && onCopy && (
          <button onClick={onCopy} className="btn-secondary text-xs">
            {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
