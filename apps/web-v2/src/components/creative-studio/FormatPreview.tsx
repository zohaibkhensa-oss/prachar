"use client";

/**
 * FormatPreview — renders a readable preview of one creative format's content.
 *
 * Each of the 10 formats has a different shape (defined by the backend
 * CreativeFormatSpec output_schema). This component uses a switch statement to
 * render known fields nicely per format, and falls back to a generic structured
 * card for any unknown shape.
 *
 * Each top-level field has a small "regenerate" icon button (RefreshCw) that
 * appears on hover. Clicking it calls `onRegenerateField(fieldName)` which
 * triggers a backend call to regenerate ONLY that field. While regenerating,
 * the individual field shows a loading spinner (not the whole card).
 *
 * Every field is also inline-editable: click the value to turn it into a
 * textarea, click away (or press Cmd/Ctrl+Enter) to save. Edits are committed
 * via `onEditField(path, value)` which updates the in-memory package state.
 */
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { RefreshCw, Loader2, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FormatPreviewProps {
  formatId: string;
  data: Record<string, unknown>;
  className?: string;
  /** Called when the user clicks the regenerate button on a field. */
  onRegenerateField?: (fieldName: string) => void;
  /** The field currently being regenerated (shows loading state on just that field). */
  regeneratingField?: string | null;
  /** Called when the user edits a field inline. `path` is a dot-path into the
   *  data object (e.g. "headline" or "scenes.0.visual"). */
  onEditField?: (path: string, value: unknown) => void;
}

// ─── Regenerate context ───────────────────────────────────────────────────

interface RegenerateCtx {
  onRegenerate?: (fieldName: string) => void;
  regeneratingField: string | null;
}

const RegenerateContext = createContext<RegenerateCtx | null>(null);

function useRegenerate(): RegenerateCtx {
  return useContext(RegenerateContext) ?? { onRegenerate: undefined, regeneratingField: null };
}

// ─── Edit context ──────────────────────────────────────────────────────────

interface EditCtx {
  onEdit?: (path: string, value: unknown) => void;
}

const EditContext = createContext<EditCtx | null>(null);

function useEdit(): EditCtx {
  return useContext(EditContext) ?? { onEdit: undefined };
}

// ─── Inline text editor ────────────────────────────────────────────────────

function InlineText({
  value,
  path,
  multiline = true,
  className,
}: {
  value: string;
  path: string;
  multiline?: boolean;
  className?: string;
}) {
  const { onEdit } = useEdit();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

  // Keep draft in sync when upstream value changes and not actively editing.
  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  // Focus + auto-size on entering edit mode.
  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      if (multiline) {
        const ta = ref.current as HTMLTextAreaElement;
        ta.style.height = "auto";
        ta.style.height = `${ta.scrollHeight}px`;
      }
    }
  }, [editing, multiline]);

  function commit() {
    setEditing(false);
    if (onEdit && draft !== value) onEdit(path, draft);
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  if (!onEdit) {
    // No edit handler wired — render as plain text.
    return <span className={className}>{value}</span>;
  }

  if (editing) {
    const common = {
      ref: ref as never,
      value: draft,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        setDraft(e.target.value);
        if (multiline) {
          const ta = e.target as HTMLTextAreaElement;
          ta.style.height = "auto";
          ta.style.height = `${ta.scrollHeight}px`;
        }
      },
      onBlur: commit,
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          cancel();
        } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !multiline)) {
          e.preventDefault();
          commit();
        }
      },
      className: cn(
        "w-full rounded-md border border-accent/40 bg-paper px-2 py-1 text-sm text-text",
        "outline-none focus:ring-2 focus:ring-accent/30 resize-none",
        className,
      ),
    };
    return multiline ? (
      <textarea {...(common as React.TextareaHTMLAttributes<HTMLTextAreaElement>)} rows={2} />
    ) : (
      <input {...(common as React.InputHTMLAttributes<HTMLInputElement>)} type="text" />
    );
  }

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setDraft(value);
          setEditing(true);
        }
      }}
      className={cn(
        "group/edit inline-block rounded-md px-1 -mx-1 cursor-text hover:bg-white/[0.04] transition-colors",
        className,
      )}
    >
      {value || <span className="text-text-muted italic">Click to edit…</span>}
      <Pencil className="w-3 h-3 text-text-muted opacity-0 group-hover/edit:opacity-100 transition-opacity inline-block ml-1 align-middle" />
    </span>
  );
}

// ─── Regenerate button ────────────────────────────────────────────────────

function RegenerateButton({ fieldName }: { fieldName: string }) {
  const { onRegenerate, regeneratingField } = useRegenerate();
  if (!onRegenerate) return null;
  const isRegenerating = regeneratingField === fieldName;

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        if (!isRegenerating) onRegenerate(fieldName);
      }}
      disabled={isRegenerating}
      title={isRegenerating ? "Regenerating…" : `Regenerate ${fieldName.replace(/_/g, " ")}`}
      className={cn(
        "inline-flex items-center justify-center w-5 h-5 rounded-md transition-all",
        "opacity-0 group-hover:opacity-100 focus:opacity-100",
        "text-text-muted hover:text-accent hover:bg-accent/10",
        isRegenerating && "opacity-100 text-accent",
      )}
    >
      {isRegenerating ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : (
        <RefreshCw className="w-3 h-3" />
      )}
    </button>
  );
}

// ─── Small shared primitives ───────────────────────────────────────────────

function FieldLabel({ label, fieldName }: { label: string; fieldName?: string }) {
  return (
    <div className="flex items-center gap-1.5 mb-0.5">
      <span className="label-field">{label}</span>
      {fieldName && <RegenerateButton fieldName={fieldName} />}
    </div>
  );
}

function Field({
  label,
  value,
  fieldName,
  path,
}: {
  label: string;
  value: string;
  fieldName?: string;
  /** Dot-path for inline editing (e.g. "headline" or "scenes.0.visual").
   *  Defaults to `fieldName` when omitted. */
  path?: string;
}) {
  const { regeneratingField } = useRegenerate();
  if (!value && !fieldName) return null;
  const isRegenerating = fieldName != null && regeneratingField === fieldName;
  const editPath = path ?? fieldName;

  return (
    <div className="group">
      <FieldLabel label={label} fieldName={fieldName} />
      {isRegenerating ? (
        <div className="h-4 rounded bg-ink/5 animate-pulse" />
      ) : (
        <motion.div
          key={value}
          initial={{ opacity: 0.4 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="text-sm text-text leading-relaxed"
        >
          {editPath ? (
            <InlineText value={value} path={editPath} />
          ) : (
            <span>{value}</span>
          )}
        </motion.div>
      )}
    </div>
  );
}

function ListField({
  label,
  items,
  fieldName,
  path,
}: {
  label: string;
  items: string[];
  fieldName?: string;
  path?: string;
}) {
  const { regeneratingField } = useRegenerate();
  if (!items || items.length === 0) return null;
  const isRegenerating = fieldName != null && regeneratingField === fieldName;
  const basePath = path ?? fieldName;

  return (
    <div className="group">
      <FieldLabel label={label} fieldName={fieldName} />
      {isRegenerating ? (
        <div className="space-y-1.5">
          {items.map((_, i) => (
            <div key={i} className="h-3 rounded bg-ink/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <motion.ul
          key={items.join("|")}
          initial={{ opacity: 0.4 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="space-y-1"
        >
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text">
              <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0" />
              <span className="leading-relaxed flex-1">
                {basePath ? (
                  <InlineText value={item} path={`${basePath}.${i}`} multiline={false} />
                ) : (
                  item
                )}
              </span>
            </li>
          ))}
        </motion.ul>
      )}
    </div>
  );
}

function Chips({
  label,
  items,
  fieldName,
  path,
}: {
  label: string;
  items: string[];
  fieldName?: string;
  path?: string;
}) {
  const { regeneratingField } = useRegenerate();
  if (!items || items.length === 0) return null;
  const isRegenerating = fieldName != null && regeneratingField === fieldName;
  const basePath = path ?? fieldName;

  return (
    <div className="group">
      <FieldLabel label={label} fieldName={fieldName} />
      {isRegenerating ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((_, i) => (
            <div key={i} className="h-5 w-16 rounded-md bg-ink/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <motion.div
          key={items.join("|")}
          initial={{ opacity: 0.4 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="flex flex-wrap gap-1.5"
        >
          {items.map((item, i) => (
            <span
              key={i}
              className="px-2 py-0.5 rounded-md bg-accent/10 border border-accent/20 font-mono text-[11px] text-accent"
            >
              {basePath ? (
                <InlineText
                  value={item}
                  path={`${basePath}.${i}`}
                  multiline={false}
                  className="!px-0 !py-0 hover:bg-transparent"
                />
              ) : (
                item
              )}
            </span>
          ))}
        </motion.div>
      )}
    </div>
  );
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function strList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map(str).filter(Boolean);
}

// ─── Per-format renderers ──────────────────────────────────────────────────

function PosterPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <Field label="Headline" value={str(data.headline)} fieldName="headline" />
      <Field label="Subheadline" value={str(data.subheadline)} fieldName="subheadline" />
      <Field label="Body" value={str(data.body)} fieldName="body" />
      <Field label="CTA" value={str(data.cta)} fieldName="cta" />
      <Field label="Visual brief" value={str(data.visual_brief)} fieldName="visual_brief" />
      <Chips label="Colour palette" items={strList(data.color_palette)} fieldName="color_palette" />
      <Field label="Layout hint" value={str(data.layout_hint)} fieldName="layout_hint" />
    </div>
  );
}

function VideoScriptPreview({ data }: { data: Record<string, unknown> }) {
  const scenes = Array.isArray(data.scenes) ? (data.scenes as Record<string, unknown>[]) : [];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs text-text-secondary">
        <span className="font-mono">{str(data.total_duration)}s total</span>
        <span className="text-text-muted">·</span>
        <span className="font-mono">{scenes.length} scenes</span>
        <span className="text-text-muted">·</span>
        <span>Mood: {str(data.music_mood) || "—"}</span>
      </div>
      <div className="space-y-2">
        {scenes.map((scene, i) => (
          <div key={i} className="glass rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-[11px] text-accent">Scene {str(scene.scene_no || i + 1)}</span>
              <span className="font-mono text-[11px] text-text-muted">{str(scene.duration)}s</span>
            </div>
            <Field label="Visual" value={str(scene.visual)} path={`scenes.${i}.visual`} />
            <div className="mt-2">
              <Field label="Voiceover" value={str(scene.voiceover)} path={`scenes.${i}.voiceover`} />
            </div>
            <div className="mt-2">
              <Field label="On-screen text" value={str(scene.on_screen_text)} path={`scenes.${i}.on_screen_text`} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CarouselPreview({ data }: { data: Record<string, unknown> }) {
  const slides = Array.isArray(data.slides) ? (data.slides as Record<string, unknown>[]) : [];
  return (
    <div className="space-y-3">
      <div className="text-xs text-text-secondary font-mono">{slides.length} slides</div>
      <div className="space-y-2">
        {slides.map((slide, i) => (
          <div key={i} className="glass rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-[11px] text-accent">Slide {str(slide.slide_no || i + 1)}</span>
              {slide.cta_slide ? (
                <span className="font-mono text-[11px] text-success">CTA slide</span>
              ) : null}
            </div>
            <Field label="Headline" value={str(slide.headline)} path={`slides.${i}.headline`} />
            <div className="mt-2">
              <Field label="Body" value={str(slide.body)} path={`slides.${i}.body`} />
            </div>
            <div className="mt-2">
              <Field label="Visual brief" value={str(slide.visual_brief)} path={`slides.${i}.visual_brief`} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StoryPreview({ data }: { data: Record<string, unknown> }) {
  const frames = Array.isArray(data.frames) ? (data.frames as Record<string, unknown>[]) : [];
  return (
    <div className="space-y-3">
      <div className="text-xs text-text-secondary font-mono">{frames.length} frames</div>
      <div className="space-y-2">
        {frames.map((frame, i) => (
          <div key={i} className="glass rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-[11px] text-accent">Frame {str(frame.frame_no || i + 1)}</span>
              <span className="font-mono text-[11px] text-text-muted">{str(frame.type)}</span>
            </div>
            <Field label="Copy" value={str(frame.copy)} path={`frames.${i}.copy`} />
            <div className="mt-2">
              <Field label="Visual brief" value={str(frame.visual_brief)} path={`frames.${i}.visual_brief`} />
            </div>
            {frame.sticker ? (
              <div className="mt-2">
                <Field label="Sticker" value={str(frame.sticker)} path={`frames.${i}.sticker`} />
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function WhatsappPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <Field label="Status text" value={str(data.status_text)} fieldName="status_text" />
      <Field label="Status image brief" value={str(data.status_image_brief)} fieldName="status_image_brief" />
      <Field label="Broadcast message" value={str(data.broadcast_message)} fieldName="broadcast_message" />
    </div>
  );
}

function FacebookPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <Field label="Copy" value={str(data.copy)} fieldName="copy" />
      <Field label="Image brief" value={str(data.image_brief)} fieldName="image_brief" />
      <Field label="Link description" value={str(data.link_description)} fieldName="link_description" />
    </div>
  );
}

function LinkedinPreview({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <Field label="Hook" value={str(data.hook)} fieldName="hook" />
      <Field label="Body" value={str(data.body)} fieldName="body" />
      <Field label="CTA" value={str(data.cta)} fieldName="cta" />
      <Chips label="Hashtags" items={strList(data.hashtags)} fieldName="hashtags" />
    </div>
  );
}

function EmailPreview({ data }: { data: Record<string, unknown> }) {
  const subjects = strList(data.subject_lines);
  const { regeneratingField } = useRegenerate();
  const subjectsRegenerating = regeneratingField === "subject_lines";

  return (
    <div className="space-y-3">
      <div className="group">
        <FieldLabel label="Subject lines (A/B/n)" fieldName="subject_lines" />
        {subjectsRegenerating ? (
          <div className="space-y-1.5">
            {subjects.map((_, i) => (
              <div key={i} className="h-8 rounded-lg bg-ink/5 animate-pulse" />
            ))}
          </div>
        ) : (
          <motion.div
            key={subjects.join("|")}
            initial={{ opacity: 0.4 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="space-y-1.5"
          >
            {subjects.map((s, i) => (
              <div key={i} className="glass rounded-lg px-3 py-2 flex items-center gap-2">
                <span className="font-mono text-[11px] text-accent shrink-0">V{i + 1}</span>
                <span className="text-sm text-text flex-1">
                  <InlineText value={s} path={`subject_lines.${i}`} multiline={false} />
                </span>
              </div>
            ))}
          </motion.div>
        )}
      </div>
      <Field label="Preview text" value={str(data.preview_text)} fieldName="preview_text" />
      <Field label="Body brief" value={str(data.body_html_brief)} fieldName="body_html_brief" />
      <Field label="CTA" value={str(data.cta)} fieldName="cta" />
      <Field label="PS line" value={str(data.ps_line)} fieldName="ps_line" />
    </div>
  );
}

function LandingPagePreview({ data }: { data: Record<string, unknown> }) {
  const faq = Array.isArray(data.faq) ? (data.faq as Record<string, unknown>[]) : [];
  return (
    <div className="space-y-3">
      <Field label="Hero headline" value={str(data.hero_headline)} fieldName="hero_headline" />
      <Field label="Hero subhead" value={str(data.hero_subhead)} fieldName="hero_subhead" />
      <ListField label="Benefits" items={strList(data.benefits)} fieldName="benefits" />
      <Field label="Social proof" value={str(data.social_proof_section)} fieldName="social_proof_section" />
      <div>
        <div className="label-field mb-1">FAQ</div>
        <div className="space-y-2">
          {faq.map((item, i) => (
            <div key={i} className="glass rounded-lg p-3">
              <p className="text-sm font-medium text-text">
                <InlineText value={str(item.question)} path={`faq.${i}.question`} multiline={false} />
              </p>
              <p className="text-sm text-text-secondary mt-1 leading-relaxed">
                <InlineText value={str(item.answer)} path={`faq.${i}.answer`} />
              </p>
            </div>
          ))}
        </div>
      </div>
      <Field label="CTA" value={str(data.cta)} fieldName="cta" />
      <ListField label="Form fields" items={strList(data.form_fields)} fieldName="form_fields" />
    </div>
  );
}

function SmsPreview({ data }: { data: Record<string, unknown> }) {
  const variants = Array.isArray(data.variants) ? (data.variants as Record<string, unknown>[]) : [];
  if (variants.length > 0) {
    return (
      <div className="space-y-3">
        <div className="space-y-2">
          {variants.map((v, i) => (
            <div key={i} className="glass rounded-lg p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-[11px] text-accent">Variant {i + 1}</span>
                <span className="font-mono text-[11px] text-text-muted">{str(v.char_count)} chars</span>
              </div>
              <p className="text-sm text-text leading-relaxed">
                <InlineText value={str(v.message)} path={`variants.${i}.message`} />
              </p>
            </div>
          ))}
        </div>
        <Field label="Opt-out language" value={str(data.opt_out_language)} fieldName="opt_out_language" />
      </div>
    );
  }
  // Fallback shape: flat fields
  return (
    <div className="space-y-3">
      <Field label="Message" value={str(data.message)} fieldName="message" />
      <Field label="Opt-out language" value={str(data.opt_out_language)} fieldName="opt_out_language" />
    </div>
  );
}

// ─── Generic fallback renderer ─────────────────────────────────────────────

function GenericPreview({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([k]) => k !== "error");
  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => {
        if (Array.isArray(value)) {
          const items = value.map((v) => (typeof v === "string" ? v : JSON.stringify(v, null, 2)));
          return <ListField key={key} label={key.replace(/_/g, " ")} items={items} fieldName={key} path={key} />;
        }
        if (value !== null && typeof value === "object") {
          return (
            <div key={key}>
              <div className="label-field mb-1">{key.replace(/_/g, " ")}</div>
              <pre className="text-xs text-text-secondary bg-ink/5 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(value, null, 2)}
              </pre>
            </div>
          );
        }
        return <Field key={key} label={key.replace(/_/g, " ")} value={str(value)} fieldName={key} path={key} />;
      })}
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

export function FormatPreview({
  formatId,
  data,
  className,
  onRegenerateField,
  regeneratingField,
  onEditField,
}: FormatPreviewProps) {
  // Error case — the backend marks failed formats as { error: "..." }
  if (typeof data.error === "string") {
    return (
      <div className={cn("rounded-xl p-4 border border-danger/30 bg-danger/5", className)}>
        <p className="text-sm text-danger leading-relaxed">
          This format failed to generate: {data.error}
        </p>
        <p className="text-xs text-text-muted mt-2">Try the Regenerate button to retry.</p>
      </div>
    );
  }

  let body: React.ReactNode;
  switch (formatId) {
    case "poster":
      body = <PosterPreview data={data} />;
      break;
    case "video_script":
      body = <VideoScriptPreview data={data} />;
      break;
    case "carousel":
      body = <CarouselPreview data={data} />;
      break;
    case "story":
      body = <StoryPreview data={data} />;
      break;
    case "whatsapp":
      body = <WhatsappPreview data={data} />;
      break;
    case "facebook":
      body = <FacebookPreview data={data} />;
      break;
    case "linkedin":
      body = <LinkedinPreview data={data} />;
      break;
    case "email":
      body = <EmailPreview data={data} />;
      break;
    case "landing_page":
      body = <LandingPagePreview data={data} />;
      break;
    case "sms":
      body = <SmsPreview data={data} />;
      break;
    default:
      body = <GenericPreview data={data} />;
  }

  return (
    <EditContext.Provider value={{ onEdit: onEditField }}>
      <RegenerateContext.Provider
        value={{ onRegenerate: onRegenerateField, regeneratingField: regeneratingField ?? null }}
      >
        <div className={cn("space-y-3", className)}>{body}</div>
      </RegenerateContext.Provider>
    </EditContext.Provider>
  );
}
