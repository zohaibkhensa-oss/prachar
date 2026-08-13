"use client";

/**
 * Creative Studio page (P2.14).
 *
 * Input: select a campaign plan + a creative direction.
 * Output: tabbed view of all 10 creative formats (preview + copy + regenerate).
 * "Generate All" button with progress indicator.
 *
 * Route: /app/creative-studio
 */
import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Wand2,
  Copy,
  Check,
  RefreshCw,
  AlertCircle,
  Loader2,
  Image as ImageIcon,
  Video,
  Layout,
  BookOpen,
  MessageCircle,
  Facebook,
  Linkedin,
  Mail,
  Globe,
  Smartphone,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useActiveBrand, useCampaignPlans, type CampaignPlan } from "@/lib/hooks";
import { apiGet, ApiError } from "@/lib/api";
import {
  creativeStudioApi,
  CREATIVE_FORMATS,
  CREATIVE_FORMAT_IDS,
  formatLabel,
  type CreativePackage,
  type CreativeFormatData,
  type CreativeStudioGenerateRequest,
  type RegenerateFieldRequest,
} from "@/lib/creative-studio";
import { FormatPreview } from "@/components/creative-studio/FormatPreview";

// ─── Icons per format ──────────────────────────────────────────────────────

const FORMAT_ICONS: Record<string, typeof Sparkles> = {
  poster: ImageIcon,
  video_script: Video,
  carousel: Layout,
  story: BookOpen,
  whatsapp: MessageCircle,
  facebook: Facebook,
  linkedin: Linkedin,
  email: Mail,
  landing_page: Globe,
  sms: Smartphone,
};

// ─── Creative direction option ─────────────────────────────────────────────

interface CreativeDirectionOption {
  id: string;
  label: string;
  description: string;
}

/**
 * Derive 3 creative-direction options from a campaign plan's embedded
 * creative_direction data.
 *
 * The campaign plan's `campaign` JSONB contains a `creative_direction` dict
 * (visual_style, mood, colour_palette, etc.). There is no backend endpoint to
 * list CreativeDirectionRecords, so we present 3 angle variants derived from
 * the embedded direction. The creative_direction_id sent to the backend is the
 * campaign plan id (pragmatic proxy until a list endpoint exists).
 */
function deriveDirectionOptions(plan: CampaignPlan): CreativeDirectionOption[] {
  const campaign = plan.campaign as Record<string, unknown>;
  const cd = (campaign.creative_direction ?? {}) as Record<string, unknown>;
  const mood = String(cd.mood || "").trim();
  const visualStyle = String(cd.visual_style || "").trim();

  const baseLabel = mood || visualStyle || "Default";
  const id = plan.id;

  return [
    {
      id,
      label: `${baseLabel} — Primary`,
      description: visualStyle
        ? `Visual style: ${visualStyle}`
        : "Uses the campaign's primary creative direction.",
    },
    {
      id,
      label: `${baseLabel} — Bold`,
      description: "A bolder, higher-contrast take on the same direction.",
    },
    {
      id,
      label: `${baseLabel} — Minimal`,
      description: "A cleaner, more restrained interpretation.",
    },
  ];
}

// ─── Page ──────────────────────────────────────────────────────────────────

type Phase = "idle" | "generating" | "done" | "error";

export default function CreativeStudioPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [selectedDirectionId, setSelectedDirectionId] = useState<string>("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [pkg, setPkg] = useState<CreativePackage | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeTab, setActiveTab] = useState<string>("poster");
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [regeneratingField, setRegeneratingField] = useState<string | null>(null);

  const selectedPlan = useMemo(
    () => plans?.find((p) => p.id === selectedPlanId) ?? null,
    [plans, selectedPlanId],
  );

  const directionOptions = useMemo(
    () => (selectedPlan ? deriveDirectionOptions(selectedPlan) : []),
    [selectedPlan],
  );

  const domain = brand?.customer_type === "creator" ? "creator" : "business";

  const requestBody: CreativeStudioGenerateRequest | null = useMemo(() => {
    if (!selectedPlanId || !selectedDirectionId) return null;
    return {
      campaign_id: selectedPlanId,
      creative_direction_id: selectedDirectionId,
      domain,
    };
  }, [selectedPlanId, selectedDirectionId, domain]);

  // ─── Generate all ──────────────────────────────────────────────────────

  const handleGenerateAll = useCallback(async () => {
    if (!requestBody) return;
    setPhase("generating");
    setErrorMsg("");
    setPkg(null);
    try {
      const result = await creativeStudioApi.generateAllFormats(requestBody);
      setPkg(result);
      setActiveTab(CREATIVE_FORMAT_IDS[0]);
      setPhase("done");
    } catch (err) {
      const msg = err instanceof ApiError ? formatApiError(err) : "Generation failed. Please try again.";
      setErrorMsg(msg);
      setPhase("error");
    }
  }, [requestBody]);

  // ─── Regenerate one ────────────────────────────────────────────────────

  const handleRegenerate = useCallback(
    async (formatId: string) => {
      if (!requestBody || !pkg) return;
      setRegenerating(formatId);
      try {
        const data = await creativeStudioApi.generateOneFormat(formatId, requestBody);
        setPkg((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            formats: { ...prev.formats, [formatId]: data },
          };
        });
      } catch (err) {
        const msg = err instanceof ApiError ? formatApiError(err) : `Regenerating ${formatLabel(formatId)} failed.`;
        setErrorMsg(msg);
      } finally {
        setRegenerating(null);
      }
    },
    [requestBody, pkg],
  );

  // ─── Regenerate a single field ────────────────────────────────────────

  const handleRegenerateField = useCallback(
    async (formatId: string, fieldName: string) => {
      if (!requestBody || !pkg) return;
      const currentData = pkg.formats[formatId];
      if (!currentData) return;
      const fieldKey = `${formatId}:${fieldName}`;
      setRegeneratingField(fieldKey);
      try {
        const body: RegenerateFieldRequest = {
          ...requestBody,
          format_id: formatId,
          field_name: fieldName,
          current_content: currentData,
        };
        const result = await creativeStudioApi.regenerateField(body);
        setPkg((prev) => {
          if (!prev) return prev;
          const fmtData = prev.formats[formatId];
          if (!fmtData) return prev;
          return {
            ...prev,
            formats: {
              ...prev.formats,
              [formatId]: { ...fmtData, [result.field_name]: result.new_value },
            },
          };
        });
      } catch (err) {
        const msg = err instanceof ApiError ? formatApiError(err) : `Regenerating ${fieldName} failed.`;
        setErrorMsg(msg);
      } finally {
        setRegeneratingField(null);
      }
    },
    [requestBody, pkg],
  );

  // ─── Edit a single field inline (in-memory only) ──────────────────────

  const handleEditField = useCallback(
    (formatId: string, path: string, value: unknown) => {
      setPkg((prev) => {
        if (!prev) return prev;
        const fmtData = prev.formats[formatId];
        if (!fmtData) return prev;
        const updated = applyPathEdit(fmtData, path, value);
        return {
          ...prev,
          formats: {
            ...prev.formats,
            [formatId]: updated,
          },
        };
      });
    },
    [],
  );

  // ─── Copy ──────────────────────────────────────────────────────────────

  const handleCopy = useCallback(async (formatId: string) => {
    const data = pkg?.formats[formatId];
    if (!data) return;
    const json = JSON.stringify(data, null, 2);
    try {
      await navigator.clipboard.writeText(json);
      setCopied(formatId);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard may be unavailable; ignore silently.
    }
  }, [pkg]);

  const canGenerate = !!requestBody && phase !== "generating";

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Wand2 className="w-4 h-4 text-accent" />
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider text-accent">Creative Studio</span>
        </div>
        <h1 className="font-display text-3xl font-semibold text-text">Creative Studio</h1>
        <p className="text-text-secondary mt-1.5 text-sm">
          Generate all 10 creative formats — posters, video scripts, carousels, and more — from a single campaign.
        </p>
      </div>

      {/* Input panel */}
      <div className="glass-strong rounded-2xl p-6 space-y-5">
        {/* Campaign selector */}
        <div>
          <label className="label-field block mb-2">Campaign</label>
          {plansLoading || brandLoading ? (
            <div className="h-10 rounded-lg bg-bg-surface/5 animate-pulse" />
          ) : plans && plans.length > 0 ? (
            <SelectDropdown
              value={selectedPlanId}
              onChange={(v) => {
                setSelectedPlanId(v);
                setSelectedDirectionId("");
                setPhase("idle");
                setPkg(null);
              }}
              placeholder="Select a campaign…"
              options={plans.map((p) => ({
                value: p.id,
                label: p.name,
                sub: p.goal,
              }))}
            />
          ) : (
            <p className="text-sm text-text-muted">
              No campaigns yet. Create a campaign first to use the Creative Studio.
            </p>
          )}
        </div>

        {/* Creative direction selector */}
        {selectedPlan && directionOptions.length > 0 && (
          <div>
            <label className="label-field block mb-2">Creative direction</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {directionOptions.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setSelectedDirectionId(opt.id);
                    setPhase("idle");
                    setPkg(null);
                  }}
                  className={cn(
                    "text-left rounded-xl p-3 border transition-all",
                    selectedDirectionId === opt.id && (i === 0 || selectedDirectionId !== "")
                      ? "border-accent bg-accent/5"
                      : "border-white/[0.06] hover:border-white/[0.12] bg-bg-surface/[0.02]",
                  )}
                >
                  <div className="text-sm font-medium text-text">{opt.label}</div>
                  <div className="text-xs text-text-secondary mt-0.5 leading-relaxed">{opt.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Generate button */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleGenerateAll}
            disabled={!canGenerate}
            className={cn(
              "btn-primary group inline-flex items-center gap-2",
              !canGenerate && "opacity-50 cursor-not-allowed",
            )}
          >
            {phase === "generating" ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating all 10 formats…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate All Formats
              </>
            )}
          </button>
          {pkg && phase === "done" && (
            <span className="text-xs text-text-muted font-mono">
              {Object.keys(pkg.formats).length} formats · {pkg.total_tokens.toLocaleString()} tokens
            </span>
          )}
        </div>
      </div>

      {/* Error */}
      <AnimatePresence>
        {phase === "error" && errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-xl p-4 border border-danger/30 bg-danger/5 flex items-start gap-3"
          >
            <AlertCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-danger leading-relaxed">{errorMsg}</p>
              <button onClick={() => setPhase("idle")} className="text-xs text-danger/70 underline mt-2">
                Dismiss
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generating progress */}
      {phase === "generating" && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center justify-center gap-4">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <div className="text-center">
            <p className="text-sm font-medium text-text">Generating all 10 creative formats…</p>
            <p className="text-xs text-text-secondary mt-1">This usually takes 15-30 seconds.</p>
          </div>
          <div className="w-full max-w-xs grid grid-cols-10 gap-1 mt-2">
            {CREATIVE_FORMAT_IDS.map((id) => (
              <div
                key={id}
                className="h-1.5 rounded-full bg-accent/20 overflow-hidden"
              >
                <motion.div
                  className="h-full bg-accent"
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 0.8, delay: CREATIVE_FORMAT_IDS.indexOf(id) * 0.15 }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Results — tabbed view */}
      {phase === "done" && pkg && (
        <FormatTabs
          pkg={pkg}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          onCopy={handleCopy}
          onRegenerate={handleRegenerate}
          onRegenerateField={handleRegenerateField}
          onEditField={(path, value) => handleEditField(activeTab, path, value)}
          copied={copied}
          regenerating={regenerating}
          regeneratingField={regeneratingField}
        />
      )}
    </div>
  );
}

// ─── Tabbed format view ────────────────────────────────────────────────────

function FormatTabs({
  pkg,
  activeTab,
  onSelectTab,
  onCopy,
  onRegenerate,
  onRegenerateField,
  onEditField,
  copied,
  regenerating,
  regeneratingField,
}: {
  pkg: CreativePackage;
  activeTab: string;
  onSelectTab: (id: string) => void;
  onCopy: (id: string) => void;
  onRegenerate: (id: string) => void;
  onRegenerateField: (formatId: string, fieldName: string) => void;
  onEditField: (path: string, value: unknown) => void;
  copied: string | null;
  regenerating: string | null;
  regeneratingField: string | null;
}) {
  const activeData = pkg.formats[activeTab];
  const Icon = FORMAT_ICONS[activeTab] ?? Sparkles;

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex flex-wrap gap-1.5 glass rounded-xl p-1.5">
        {CREATIVE_FORMATS.map((fmt) => {
          const FmtIcon = FORMAT_ICONS[fmt.id] ?? Sparkles;
          const hasError = pkg.formats[fmt.id]?.error != null;
          return (
            <button
              key={fmt.id}
              onClick={() => onSelectTab(fmt.id)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all",
                activeTab === fmt.id
                  ? "bg-accent text-white"
                  : "text-text-secondary hover:bg-bg-surface/5 hover:text-text",
              )}
              title={fmt.description}
            >
              <FmtIcon className="w-3.5 h-3.5" />
              {fmt.label}
              {hasError && (
                <span className="w-1.5 h-1.5 rounded-full bg-danger" />
              )}
            </button>
          );
        })}
      </div>

      {/* Active tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="glass-strong rounded-2xl p-6 space-y-4"
        >
          {/* Tab header */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <Icon className="w-4 h-4 text-accent" />
              </div>
              <div>
                <h3 className="font-display text-lg font-semibold text-text">
                  {formatLabel(activeTab)}
                </h3>
                <p className="text-xs text-text-secondary">
                  {CREATIVE_FORMATS.find((f) => f.id === activeTab)?.description}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => onCopy(activeTab)}
                disabled={!activeData}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] hover:bg-bg-surface/5 transition-colors disabled:opacity-40"
              >
                {copied === activeTab ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-success" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy JSON
                  </>
                )}
              </button>
              <button
                onClick={() => onRegenerate(activeTab)}
                disabled={regenerating === activeTab}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] hover:bg-bg-surface/5 transition-colors disabled:opacity-40"
              >
                {regenerating === activeTab ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Regenerating…
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3.5 h-3.5" />
                    Regenerate
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Preview */}
          {activeData ? (
            <FormatPreview
              formatId={activeTab}
              data={activeData}
              onRegenerateField={(fieldName) => onRegenerateField(activeTab, fieldName)}
              onEditField={onEditField}
              regeneratingField={
                regeneratingField && regeneratingField.startsWith(`${activeTab}:`)
                  ? regeneratingField.split(":")[1]
                  : null
              }
            />
          ) : (
            <p className="text-sm text-text-muted">No data for this format.</p>
          )}

          {/* Raw JSON (collapsible) */}
          {activeData && (
            <details className="group">
              <summary className="cursor-pointer text-xs text-text-muted font-mono hover:text-text-secondary transition-colors select-none">
                ▸ Raw JSON
              </summary>
              <pre className="mt-2 text-xs text-text-secondary bg-bg-surface/5 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap border border-white/[0.04]">
                {JSON.stringify(activeData, null, 2)}
              </pre>
            </details>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ─── Select dropdown (styled) ──────────────────────────────────────────────

function SelectDropdown({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  options: { value: string; label: string; sub?: string }[];
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg border border-white/[0.08] bg-bg-surface/[0.02] hover:border-white/[0.15] transition-colors text-left"
      >
        <span className={cn("text-sm", selected ? "text-text" : "text-text-muted")}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown className={cn("w-4 h-4 text-text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute z-20 mt-1 w-full rounded-lg border border-white/[0.08] bg-bg-card shadow-lg max-h-64 overflow-y-auto">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "w-full text-left px-4 py-2.5 hover:bg-bg-surface/5 transition-colors border-b border-white/[0.03] last:border-0",
                  value === opt.value && "bg-accent/5",
                )}
              >
                <div className="text-sm text-text font-medium">{opt.label}</div>
                {opt.sub && <div className="text-xs text-text-secondary mt-0.5">{opt.sub}</div>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

/**
 * Immutably apply an inline edit to a nested path inside a format's data object.
 *
 * `path` is a dot-path like "headline" or "scenes.0.visual". Numeric segments
 * index into arrays. Returns a new object (shallow-cloned at each level) so
 * React state updates are detected. The edit is in-memory only — no backend
 * call is made.
 */
function applyPathEdit(
  data: CreativeFormatData,
  path: string,
  value: unknown,
): CreativeFormatData {
  const segments = path.split(".");
  if (segments.length === 0) return data;

  function setDeep<T>(obj: T, segs: string[], val: unknown): T {
    const head = segs[0];
    const rest = segs.slice(1);
    if (head == null) return obj;
    const key: string = head;
    if (rest.length === 0) {
      if (Array.isArray(obj)) {
        const idx = Number(key);
        if (Number.isNaN(idx)) return obj;
        const next = obj.slice();
        next[idx] = val as T[keyof T];
        return next as unknown as T;
      }
      if (obj !== null && typeof obj === "object") {
        return { ...(obj as object), [key]: val } as unknown as T;
      }
      return obj;
    }
    if (Array.isArray(obj)) {
      const idx = Number(key);
      if (Number.isNaN(idx)) return obj;
      const next = obj.slice();
      next[idx] = setDeep(obj[idx], rest, val);
      return next as unknown as T;
    }
    if (obj !== null && typeof obj === "object") {
      const record = obj as Record<string, unknown>;
      return { ...record, [key]: setDeep(record[key], rest, val) } as unknown as T;
    }
    return obj;
  }

  return setDeep(data, segments, value);
}

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
