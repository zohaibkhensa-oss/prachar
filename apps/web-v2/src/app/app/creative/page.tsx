"use client";

import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Wand2,
  Check,
  Copy,
  AlertCircle,
  Loader2,
  RefreshCw,
  Image as ImageIcon,
} from "lucide-react";
import { Card3D, Card, GlassCard } from "@/components/ui/card-3d";
import { AIStatusBlock, AIThinkingOverlay } from "@/components/ui/ai-blocks";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { LabsBanner } from "@/components/LabsBanner";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import {
  creativeStudioApi,
  formatLabel,
  type CreativePackage,
  type CreativeFormatData,
} from "@/lib/creative-studio";

/* ────────────────────────────── Helpers ────────────────────────────── */

type Phase = "idle" | "generating" | "done" | "error";

function formatApiError(err: ApiError): string {
  if (err.status === 404) {
    return "The campaign or creative direction was not found. Make sure you've selected a valid campaign.";
  }
  if (err.status === 401 || err.status === 403) {
    return "You're not authorised to do this. Please log in again.";
  }
  if (err.status === 429) {
    return "You've hit your AI usage limit. Try again later or upgrade your plan.";
  }
  const bodyMsg =
    typeof err.body === "object" && err.body !== null && "detail" in err.body
      ? String((err.body as Record<string, unknown>).detail)
      : "";
  return bodyMsg || `Request failed (${err.status}). Please try again.`;
}

/* ─── Recursive renderer for real format content ─────────────────────── */

function FormatContent({ data }: { data: CreativeFormatData }) {
  if ("error" in data && typeof (data as Record<string, unknown>).error === "string") {
    return (
      <p className="text-sm text-danger leading-relaxed">
        {(data as Record<string, unknown>).error as string}
      </p>
    );
  }
  return (
    <div className="space-y-2.5">
      {Object.entries(data).map(([key, value]) => (
        <Field key={key} name={key} value={value} />
      ))}
    </div>
  );
}

function Field({ name, value }: { name: string; value: unknown }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-text-muted mb-0.5 font-mono">
        {name}
      </div>
      <FieldValue value={value} />
    </div>
  );
}

function FieldValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <p className="text-sm text-text-muted">—</p>;
  }
  if (typeof value === "string") {
    return <p className="text-sm text-text-secondary leading-relaxed">{value}</p>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <p className="text-sm text-text-secondary font-mono">{String(value)}</p>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="space-y-1">
        {value.map((item, i) => (
          <li key={i} className="text-sm text-text-secondary leading-relaxed flex gap-1.5">
            <span className="text-text-muted shrink-0">•</span>
            <span>
              {typeof item === "string"
                ? item
                : typeof item === "object" && item !== null
                  ? JSON.stringify(item)
                  : String(item)}
            </span>
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <div className="pl-3 border-l border-white/[0.06] space-y-1.5">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <Field key={k} name={k} value={v} />
        ))}
      </div>
    );
  }
  return <p className="text-sm text-text-muted">{String(value)}</p>;
}

/* ────────────────────────────── Page ────────────────────────────── */

export default function CreativeAIPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const [prompt, setPrompt] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [pkg, setPkg] = useState<CreativePackage | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<string | null>(null);

  const domain = brand?.customer_type === "creator" ? "creator" : "business";

  const selectedPlan = useMemo(
    () => plans?.find((p) => p.id === selectedPlanId) ?? null,
    [plans, selectedPlanId],
  );

  const canGenerate = !!prompt.trim() && !!selectedPlanId && phase !== "generating";

  const handleGenerate = useCallback(async () => {
    if (!selectedPlanId) return;
    setPhase("generating");
    setErrorMsg("");
    setPkg(null);
    try {
      const result = await creativeStudioApi.generateAllFormats({
        campaign_id: selectedPlanId,
        creative_direction_id: selectedPlanId,
        domain,
      });
      setPkg(result);
      setPhase("done");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? formatApiError(err)
          : "Generation failed. Please try again.";
      setErrorMsg(msg);
      setPhase("error");
    }
  }, [selectedPlanId, domain]);

  const handleRegenerate = useCallback(
    async (formatId: string) => {
      if (!selectedPlanId) return;
      setRegenerating(formatId);
      try {
        const data = await creativeStudioApi.generateOneFormat(formatId, {
          campaign_id: selectedPlanId,
          creative_direction_id: selectedPlanId,
          domain,
        });
        setPkg((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            formats: { ...prev.formats, [formatId]: data },
          };
        });
      } catch (err) {
        const msg =
          err instanceof ApiError
            ? formatApiError(err)
            : `Regenerating ${formatLabel(formatId)} failed.`;
        setErrorMsg(msg);
      } finally {
        setRegenerating(null);
      }
    },
    [selectedPlanId, domain],
  );

  const handleCopy = useCallback(async (formatId: string) => {
    const data = pkg?.formats[formatId];
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(formatId);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard may be unavailable; ignore silently.
    }
  }, [pkg]);

  const formatEntries = useMemo(() => {
    if (!pkg) return [];
    return Object.entries(pkg.formats);
  }, [pkg]);

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
      <LabsBanner title="Creative AI" description="Generate ad creatives, headlines, and visual variants with AI." features={["Ad generation", "Headline writing", "A/B variants"]} />
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-text flex items-center gap-3">
            <span className="text-gradient-accent">Creative AI</span>
            <Sparkles className="w-6 h-6 text-accent" />
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Generate, test, and ship high-performing ad creative in minutes.
          </p>
        </div>
        <AIStatusBlock status="idle" label="AI Engine Ready" detail="Brand-tuned" confidence={96} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_300px] gap-6">
        {/* ─── Left panel: controls ─── */}
        <div className="space-y-4">
          <Card3D className="space-y-4" glow>
            <div>
              <label className="label-field mb-2 block">Prompt</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={6}
                className="input-field resize-none w-full text-sm leading-relaxed"
                placeholder="Describe the ad you want the AI to generate..."
              />
              <div className="flex justify-between mt-1.5">
                <span className="font-mono text-[10px] text-text-muted">{prompt.length} chars</span>
              </div>
            </div>

            <div>
              <label className="label-field mb-2 block">Campaign</label>
              {plansLoading || brandLoading ? (
                <div className="h-10 rounded-lg bg-white/[0.04] animate-pulse" />
              ) : plans && plans.length > 0 ? (
                <div className="space-y-1.5">
                  {plans.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setSelectedPlanId(p.id);
                        setPhase("idle");
                        setPkg(null);
                      }}
                      className={cn(
                        "w-full flex items-center justify-between p-2.5 rounded-lg text-left transition-all",
                        selectedPlanId === p.id
                          ? "bg-accent/10 border border-accent/30"
                          : "border border-white/[0.04] hover:bg-white/[0.03]",
                      )}
                    >
                      <div className="min-w-0">
                        <div className="text-sm text-text font-medium truncate">{p.name}</div>
                        <div className="text-[10px] text-text-muted font-mono truncate">{p.goal}</div>
                      </div>
                      {selectedPlanId === p.id && <Check className="w-4 h-4 text-accent shrink-0" />}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted leading-relaxed">
                  No campaigns yet. Create a campaign first to generate creatives.
                </p>
              )}
            </div>

            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              className={cn(
                "btn-primary w-full group glow-ring flex items-center justify-center gap-2",
                !canGenerate && "opacity-50 cursor-not-allowed",
              )}
            >
              {phase === "generating" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  Generate Creatives
                </>
              )}
            </button>
          </Card3D>
        </div>

        {/* ─── Center: results ─── */}
        <div className="relative min-h-[600px]">
          <AnimatePresence>
            {phase === "generating" && (
              <AIThinkingOverlay message="AI is generating creatives..." />
            )}
          </AnimatePresence>

          {/* Error */}
          <AnimatePresence>
            {phase === "error" && errorMsg && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="rounded-xl p-4 border border-danger/30 bg-danger/5 flex items-start gap-3 mb-4"
              >
                <AlertCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-danger leading-relaxed">{errorMsg}</p>
                  <button
                    onClick={() => setPhase("idle")}
                    className="text-xs text-danger/70 underline mt-2"
                  >
                    Dismiss
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Generating progress */}
          {phase === "generating" && (
            <div className="glass rounded-2xl p-8 flex flex-col items-center justify-center gap-4 mb-4">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-text">Generating all creative formats…</p>
                <p className="text-xs text-text-secondary mt-1">This usually takes 15-30 seconds.</p>
              </div>
            </div>
          )}

          {/* Results header + regenerate */}
          {phase === "done" && pkg && (
            <div className="flex items-center justify-between mb-4">
              <span className="font-mono text-xs text-text-muted">
                {formatEntries.length} formats · {pkg.total_tokens.toLocaleString()} tokens
              </span>
              <button
                onClick={handleGenerate}
                className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Regenerate all
              </button>
            </div>
          )}

          {/* Results grid */}
          {phase === "done" && pkg && (
            <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <AnimatePresence mode="popLayout">
                {formatEntries.map(([formatId, data], i) => (
                  <motion.div
                    key={formatId}
                    layout
                    initial={{ opacity: 0, y: 20, rotateX: -10 }}
                    animate={{ opacity: 1, y: 0, rotateX: 0 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ delay: i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <Card3D className="h-full flex flex-col" glow>
                      {/* Top row: format label + actions */}
                      <div className="flex items-center justify-between mb-3">
                        <span className="badge badge-neutral font-mono">{formatLabel(formatId)}</span>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleRegenerate(formatId)}
                            disabled={regenerating === formatId}
                            className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08] transition-all disabled:opacity-50"
                            title="Regenerate this format"
                          >
                            {regenerating === formatId ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <RefreshCw className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => handleCopy(formatId)}
                            className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08] transition-all"
                            title="Copy as JSON"
                          >
                            {copied === formatId ? (
                              <Check className="w-3.5 h-3.5 text-success" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Content */}
                      <div className="flex-1 overflow-hidden">
                        <FormatContent data={data} />
                      </div>
                    </Card3D>
                  </motion.div>
                ))}
              </AnimatePresence>
            </motion.div>
          )}

          {/* Empty state */}
          {phase === "idle" && !pkg && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col items-center justify-center text-center py-24"
            >
              <motion.div
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-5 glow-ring"
              >
                <ImageIcon className="w-8 h-8 text-accent" />
              </motion.div>
              <SectionHeader
                title="No creatives generated yet"
                subtitle="Enter a prompt, pick a campaign, and click Generate to create ad creatives with AI."
              />
              <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                {["Poster", "Video Script", "Carousel", "Story", "Email", "SMS"].map((f) => (
                  <span key={f} className="badge badge-neutral">{f}</span>
                ))}
              </div>
            </motion.div>
          )}
        </div>

        {/* ─── Right panel: Brand Voice (real data) ─── */}
        <div className="space-y-4">
          <Card3D glow>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent" />
              </div>
              <div>
                <div className="font-display text-sm font-medium text-text">Brand Voice</div>
                <div className="text-[10px] text-text-muted font-mono">
                  {brandLoading ? "Loading…" : brand?.name ?? "No brand"}
                </div>
              </div>
            </div>

            {brand ? (
              <div className="space-y-3">
                {brand.tone?.voice && (
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs text-text-secondary">Voice</span>
                    </div>
                    <p className="text-sm text-text leading-relaxed">{brand.tone.voice}</p>
                  </div>
                )}
                {brand.tone?.description && (
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs text-text-secondary">Description</span>
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {brand.tone.description}
                    </p>
                  </div>
                )}
                {!brand.tone?.voice && !brand.tone?.description && (
                  <p className="text-xs text-text-muted leading-relaxed">
                    No brand voice configured. Add tone details to your brand profile for more tailored creatives.
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-text-muted leading-relaxed">
                {brandLoading
                  ? "Loading brand…"
                  : "No brand found. Create a brand to personalise your creatives."}
              </p>
            )}
          </Card3D>

          {selectedPlan && (
            <Card>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-info" />
                <span className="font-display text-sm font-medium text-text">Selected Campaign</span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-text-muted mb-0.5 font-mono">
                    Name
                  </div>
                  <p className="text-sm text-text">{selectedPlan.name}</p>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-text-muted mb-0.5 font-mono">
                    Goal
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">{selectedPlan.goal}</p>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-text-muted mb-0.5 font-mono">
                    Confidence
                  </div>
                  <p className="text-sm text-text font-mono">
                    {Math.round(selectedPlan.overall_confidence)}%
                  </p>
                </div>
              </div>
            </Card>
          )}

          <GlassCard>
            <div className="flex items-center gap-2 mb-3">
              <ImageIcon className="w-4 h-4 text-info" />
              <span className="font-display text-sm font-medium text-text">How it works</span>
            </div>
            <ol className="space-y-2">
              <li className="flex items-start gap-2 text-xs text-text-secondary">
                <span className="font-mono text-[10px] text-accent shrink-0 mt-0.5">1</span>
                <span>Enter a prompt describing the ad you want.</span>
              </li>
              <li className="flex items-start gap-2 text-xs text-text-secondary">
                <span className="font-mono text-[10px] text-accent shrink-0 mt-0.5">2</span>
                <span>Pick a campaign to ground the generation.</span>
              </li>
              <li className="flex items-start gap-2 text-xs text-text-secondary">
                <span className="font-mono text-[10px] text-accent shrink-0 mt-0.5">3</span>
                <span>Click Generate — AI creates 10 formats in seconds.</span>
              </li>
            </ol>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
