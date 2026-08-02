"use client";

/**
 * EditableField — a field that toggles between display and edit mode.
 *
 * Click the displayed value to turn it into a textarea. Save commits via the
 * `onSave` callback (which should call `reviewApi.editField`); Cancel reverts.
 */
import { useEffect, useRef, useState } from "react";
import { Check, X, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EditableFieldProps {
  /** Backend field name passed to PATCH /review/{id}/field. */
  field: string;
  /** Human-readable label shown above the value. */
  label: string;
  /** Current value (string). */
  value: string;
  /** Called with the new value when the user saves. Return a promise to
   *  indicate in-flight state; throw to keep the editor open on error. */
  onSave: (value: string) => void | Promise<void>;
  /** Optional placeholder for the textarea. */
  placeholder?: string;
  /** Extra classes for the display value. */
  className?: string;
}

export function EditableField({
  field,
  label,
  value,
  onSave,
  placeholder,
  className,
}: EditableFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep draft in sync when the upstream value changes.
  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  // Focus + auto-size on enter.
  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editing]);

  function startEdit() {
    setDraft(value);
    setEditing(true);
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  async function save() {
    if (draft === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } catch {
      // Keep editor open on error so the user can retry.
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="space-y-2">
        <div className="label-field">{label}</div>
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (textareaRef.current) {
              textareaRef.current.style.height = "auto";
              textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
            }
          }}
          placeholder={placeholder ?? `Enter ${label.toLowerCase()}`}
          disabled={saving}
          className="input-field resize-none min-h-[80px] font-body"
          data-field={field}
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="btn-primary !px-3 !py-1.5 !text-xs"
          >
            <Check className="w-3.5 h-3.5" />
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={cancel}
            disabled={saving}
            className="btn-ghost !px-3 !py-1.5 !text-xs"
          >
            <X className="w-3.5 h-3.5" />
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={startEdit}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          startEdit();
        }
      }}
      className={cn(
        "group space-y-1 cursor-text rounded-lg p-2 -mx-2 hover:bg-white/[0.03] transition-colors",
        className,
      )}
    >
      <div className="flex items-center gap-1.5">
        <span className="label-field">{label}</span>
        <Pencil className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      <div className="text-sm text-text whitespace-pre-wrap leading-relaxed">
        {value || <span className="text-text-muted italic">Click to edit…</span>}
      </div>
    </div>
  );
}
