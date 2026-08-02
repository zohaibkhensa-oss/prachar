"use client";

/**
 * VersionHistory — Google Docs-style version history panel.
 *
 * Renders a list of all versions for a campaign (newest first). Each version
 * shows its number, timestamp, author, and change summary. Clicking a version
 * expands its snapshot so the user can preview the campaign state at that
 * point. A "Restore" button lets the user restore a previous version (with a
 * confirmation dialog).
 */
import { useState } from "react";
import {
  History,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Loader2,
  AlertCircle,
  Eye,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReviewVersionItem } from "@/lib/review";

export interface VersionHistoryProps {
  versions: ReviewVersionItem[];
  isLoading?: boolean;
  /** Called when the user confirms a restore. */
  onRestore: (versionNumber: number) => void | Promise<void>;
  /** Whether a restore mutation is currently in-flight. */
  restoring?: boolean;
  /** The version number currently being restored (for button state). */
  restoringVersion?: number | null;
}

export function VersionHistory({
  versions,
  isLoading,
  onRestore,
  restoring,
  restoringVersion,
}: VersionHistoryProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [confirmRestore, setConfirmRestore] = useState<number | null>(null);

  function toggleExpand(versionNumber: number) {
    setExpanded((prev) => (prev === versionNumber ? null : versionNumber));
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <History className="w-4 h-4 text-accent" />
          </div>
          <div>
            <div className="font-display text-sm font-semibold text-text">Version History</div>
            <div className="text-xs text-text-muted">
              {isLoading ? "Loading…" : `${versions.length} version${versions.length === 1 ? "" : "s"}`}
            </div>
          </div>
        </div>
      </div>

      {/* Loading skeleton */}
      {isLoading && versions.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="glass rounded-xl p-4 space-y-2 animate-pulse">
              <div className="h-3 w-1/4 rounded bg-white/[0.06]" />
              <div className="h-2 w-2/3 rounded bg-white/[0.04]" />
              <div className="h-2 w-1/2 rounded bg-white/[0.04]" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && versions.length === 0 && (
        <div className="glass rounded-xl p-6 text-center">
          <History className="w-8 h-8 text-text-muted mx-auto mb-2" />
          <p className="text-sm text-text-secondary">No versions yet.</p>
          <p className="text-xs text-text-muted mt-1">
            Edit a field to create the first version snapshot.
          </p>
        </div>
      )}

      {/* Version list */}
      {versions.length > 0 && (
        <div className="space-y-2">
          {versions.map((version, idx) => (
            <VersionRow
              key={version.id}
              version={version}
              isLatest={idx === 0}
              isExpanded={expanded === version.version_number}
              onToggle={() => toggleExpand(version.version_number)}
              isConfirming={confirmRestore === version.version_number}
              onStartConfirm={() => setConfirmRestore(version.version_number)}
              onCancelConfirm={() => setConfirmRestore(null)}
              onConfirmRestore={() => {
                onRestore(version.version_number);
                setConfirmRestore(null);
              }}
              isRestoring={
                (restoring ?? false) && restoringVersion === version.version_number
              }
              disableRestore={(restoring ?? false) || idx === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Single version row ─────────────────────────────────────────────────────

interface VersionRowProps {
  version: ReviewVersionItem;
  isLatest: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  isConfirming: boolean;
  onStartConfirm: () => void;
  onCancelConfirm: () => void;
  onConfirmRestore: () => void;
  isRestoring: boolean;
  disableRestore: boolean;
}

function VersionRow({
  version,
  isLatest,
  isExpanded,
  onToggle,
  isConfirming,
  onStartConfirm,
  onCancelConfirm,
  onConfirmRestore,
  isRestoring,
  disableRestore,
}: VersionRowProps) {
  const date = new Date(version.created_at);
  const timeStr = date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={cn(
        "glass rounded-xl overflow-hidden transition-all",
        isLatest && "ring-1 ring-accent/20",
      )}
    >
      {/* Header row */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="shrink-0 mt-0.5">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-text-muted" />
          ) : (
            <ChevronRight className="w-4 h-4 text-text-muted" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-text">
              v{version.version_number}
            </span>
            {isLatest && (
              <span className="badge badge-accent !text-[10px] !px-1.5 !py-0.5">
                Current
              </span>
            )}
            <span className="text-xs text-text-muted">{timeStr}</span>
          </div>
          {version.change_summary && (
            <p className="text-xs text-text-secondary mt-0.5 truncate">
              {version.change_summary}
            </p>
          )}
          {version.author && (
            <div className="flex items-center gap-1 mt-0.5">
              <User className="w-3 h-3 text-text-muted" />
              <span className="text-xs text-text-muted truncate">
                {version.author.email}
              </span>
            </div>
          )}
        </div>
      </button>

      {/* Expanded snapshot preview */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3">
          <div className="rounded-lg bg-black/20 border border-white/[0.04] p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-xs text-text-muted">
              <Eye className="w-3.5 h-3.5" />
              <span>Snapshot at this version</span>
            </div>
            <SnapshotFields snapshot={version.snapshot} />
          </div>

          {/* Restore action */}
          {!isConfirming ? (
            <button
              type="button"
              onClick={onStartConfirm}
              disabled={disableRestore}
              className={cn(
                "btn-ghost !text-xs !px-3 !py-1.5 w-full justify-center",
                disableRestore && "opacity-40 cursor-not-allowed",
              )}
              title={
                isLatest
                  ? "This is the current version"
                  : "Restore this version"
              }
            >
              <RotateCcw className="w-3.5 h-3.5" />
              {isLatest ? "Current version" : "Restore this version"}
            </button>
          ) : (
            <div className="rounded-lg bg-warning/10 border border-warning/20 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                <p className="text-xs text-text-secondary">
                  Restore <strong>v{version.version_number}</strong>? This creates a new
                  version with the old content — your current state is preserved in history.
                </p>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onCancelConfirm}
                  disabled={isRestoring}
                  className="btn-ghost !text-xs !px-2.5 !py-1"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={onConfirmRestore}
                  disabled={isRestoring}
                  className="btn-primary !text-xs !px-2.5 !py-1 !bg-warning/20 !text-warning !border-warning/30 hover:!bg-warning/30"
                >
                  {isRestoring ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Restoring…
                    </>
                  ) : (
                    <>
                      <RotateCcw className="w-3 h-3" />
                      Confirm restore
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Snapshot field preview ─────────────────────────────────────────────────

function SnapshotFields({ snapshot }: { snapshot: Record<string, unknown> }) {
  // Display the key editable fields from the snapshot in a compact grid.
  const fields: { key: string; label: string }[] = [
    { key: "network", label: "Network" },
    { key: "objective", label: "Objective" },
    { key: "budget_daily", label: "Daily Budget" },
    { key: "currency", label: "Currency" },
    { key: "dry_run", label: "Dry Run" },
  ];
  const jsonFields: { key: string; label: string }[] = [
    { key: "audience_spec", label: "Audience" },
    { key: "bid_strategy", label: "Bid Strategy" },
    { key: "guardrails", label: "Guardrails" },
  ];

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {fields.map(({ key, label }) => {
          const val = snapshot[key];
          if (val === undefined) return null;
          return (
            <div key={key} className="min-w-0">
              <div className="text-[10px] text-text-muted uppercase tracking-wide">
                {label}
              </div>
              <div className="text-xs text-text truncate">
                {formatValue(val)}
              </div>
            </div>
          );
        })}
      </div>
      {jsonFields.map(({ key, label }) => {
        const val = snapshot[key];
        if (val === undefined || val === null) return null;
        return (
          <div key={key} className="min-w-0">
            <div className="text-[10px] text-text-muted uppercase tracking-wide">
              {label}
            </div>
            <div className="text-xs text-text-secondary font-mono break-words line-clamp-3">
              {formatValue(val)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatValue(val: unknown): string {
  if (val === null) return "—";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}
