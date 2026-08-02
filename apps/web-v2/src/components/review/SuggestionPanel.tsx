"use client";

/**
 * SuggestionPanel — renders AI-generated improvement suggestions with
 * "Apply" buttons. Each suggestion has {what_to_change, why, suggested_replacement}.
 *
 * "Apply" calls `onApply(suggestion)` — the parent decides what to do
 * (typically: write the replacement into the corresponding EditableField).
 */
import { Sparkles, Lightbulb, Check, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Suggestion } from "@/lib/review";

export interface SuggestionPanelProps {
  suggestions: Suggestion[];
  isLoading?: boolean;
  /** Whether a particular suggestion is currently being applied. */
  applyingIndex?: number | null;
  /** Applied suggestion indices (shows a check). */
  appliedIndices?: number[];
  /** Called when the user clicks "Apply" on a suggestion. */
  onApply: (suggestion: Suggestion, index: number) => void;
  /** Optional: re-generate suggestions. */
  onRefresh?: () => void;
  /** Optional error message. */
  error?: string | null;
}

export function SuggestionPanel({
  suggestions,
  isLoading,
  applyingIndex,
  appliedIndices = [],
  onApply,
  onRefresh,
  error,
}: SuggestionPanelProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-accent" />
          </div>
          <div>
            <div className="font-display text-sm font-semibold text-text">AI Suggestions</div>
            <div className="text-xs text-text-muted">
              {isLoading ? "Thinking…" : `${suggestions.length} idea${suggestions.length === 1 ? "" : "s"}`}
            </div>
          </div>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="btn-ghost !px-2 !py-1.5"
            title="Regenerate suggestions"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} />
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 p-3">
          <p className="text-xs text-danger">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && suggestions.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="glass rounded-xl p-4 space-y-2 animate-pulse">
              <div className="h-3 w-2/3 rounded bg-white/[0.06]" />
              <div className="h-2 w-full rounded bg-white/[0.04]" />
              <div className="h-2 w-4/5 rounded bg-white/[0.04]" />
            </div>
          ))}
        </div>
      )}

      {/* Empty (loaded but no suggestions) */}
      {!isLoading && suggestions.length === 0 && !error && (
        <div className="glass rounded-xl p-6 text-center">
          <Lightbulb className="w-8 h-8 text-text-muted mx-auto mb-2" />
          <p className="text-sm text-text-secondary">No suggestions right now.</p>
          <p className="text-xs text-text-muted mt-1">
            The campaign looks good, or suggestions are still being generated.
          </p>
        </div>
      )}

      {/* Suggestions list */}
      {suggestions.length > 0 && (
        <div className="space-y-3">
          {suggestions.map((s, i) => {
            const applied = appliedIndices.includes(i);
            const applying = applyingIndex === i;
            return (
              <div
                key={i}
                className={cn(
                  "glass rounded-xl p-4 space-y-3 transition-colors",
                  applied && "border-success/30",
                )}
              >
                {/* What to change */}
                <div>
                  <div className="label-field mb-1">What to change</div>
                  <p className="text-sm text-text font-medium leading-snug">{s.what_to_change}</p>
                </div>

                {/* Why */}
                {s.why && (
                  <div>
                    <div className="label-field mb-1">Why</div>
                    <p className="text-xs text-text-secondary leading-relaxed">{s.why}</p>
                  </div>
                )}

                {/* Suggested replacement */}
                {s.suggested_replacement && (
                  <div className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
                    <div className="label-field mb-1">Suggested</div>
                    <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
                      {s.suggested_replacement}
                    </p>
                  </div>
                )}

                {/* Apply button */}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => onApply(s, i)}
                    disabled={applied || applying}
                    className={cn(
                      "btn-primary !px-3 !py-1.5 !text-xs",
                      applied && "!bg-success/20 !text-success",
                    )}
                  >
                    {applied ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        Applied
                      </>
                    ) : applying ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Applying…
                      </>
                    ) : (
                      <>Apply</>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
