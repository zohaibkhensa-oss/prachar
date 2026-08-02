"use client";

/**
 * Review Queue page — `/app/review`
 *
 * Lists campaigns with status in (draft, in_review, changes_requested).
 * Each row shows campaign name, status, network/objective, and inline
 * Approve / Reject actions that hit the backend directly. Rows also link
 * to the full review detail page at `/app/review/{id}`.
 */
import { useMemo, useState, useTransition } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  ClipboardList,
  ArrowRight,
  Megaphone,
  Filter,
  Calendar,
  Check,
  X,
  Loader2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { reviewApi, type ReviewQueueItem, type ReviewStatus } from "@/lib/review";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type StatusFilter = "all" | ReviewStatus;

const STATUS_LABEL: Record<ReviewStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  changes_requested: "Changes Requested",
  approved: "Approved",
  active: "Active",
  rejected: "Rejected",
};

/** Maps a status to the badge class used across the app. */
function statusBadgeClass(status: ReviewStatus): string {
  switch (status) {
    case "draft":
      return "badge-neutral"; // gray
    case "in_review":
      return "badge-info"; // blue
    case "changes_requested":
      return "badge-warning"; // orange
    case "approved":
      return "badge-success";
    case "active":
      return "badge-accent";
    case "rejected":
      return "badge-danger";
    default:
      return "badge-neutral";
  }
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function ReviewQueuePage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const qc = useQueryClient();

  const { data: queue, isLoading, error } = useQuery<ReviewQueueItem[]>({
    queryKey: ["review-queue"],
    queryFn: () => reviewApi.getReviewQueue(),
    retry: 1,
  });

  // Filter + sort (newest first by created_at).
  const items = useMemo(() => {
    const filtered = (queue ?? []).filter(
      (item) => statusFilter === "all" || item.status === statusFilter,
    );
    return filtered.sort((a, b) => {
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
      return tb - ta;
    });
  }, [queue, statusFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Review Queue</h1>
          <p className="text-sm text-text-secondary mt-1">
            Campaigns waiting for your review and approval.
          </p>
        </div>
        {items.length > 0 && (
          <Link href="/app/campaigns" className="text-xs text-text-secondary hover:text-text transition-colors inline-flex items-center gap-1">
            <Megaphone className="w-3.5 h-3.5" />
            All campaigns
          </Link>
        )}
      </div>

      {/* Filter bar */}
      <div className="glass rounded-xl p-4 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-text-secondary">
          <Filter className="w-4 h-4" />
          <span className="label-field">Status</span>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="input-field !w-auto !py-1.5"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="in_review">In Review</option>
          <option value="changes_requested">Changes Requested</option>
        </select>
        <span className="text-xs text-text-muted ml-auto">
          {items.length} campaign{items.length === 1 ? "" : "s"}
        </span>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-6 text-center">
          <p className="text-sm text-danger">
            Could not load the review queue. {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && items.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-10 lg:p-14 text-center max-w-2xl mx-auto"
        >
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
            className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/20 to-orange-500/10 flex items-center justify-center mx-auto mb-5 glow-ring"
          >
            <ClipboardList className="w-7 h-7 text-accent" />
          </motion.div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            No campaigns awaiting review
          </h2>
          <p className="text-sm text-text-secondary leading-relaxed max-w-md mx-auto mb-6">
            When PRACHAR AI creates campaigns they&apos;ll appear here for your approval.
            You approve, you reject — nothing goes live without you.
          </p>
          <Link href="/app/campaigns" className="btn-primary inline-flex group">
            <Sparkles className="w-4 h-4" />
            Go to campaigns
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      )}

      {/* Queue list */}
      {!isLoading && !error && items.length > 0 && (
        <div className="glass-strong rounded-2xl divide-y divide-white/[0.04] overflow-hidden">
          <AnimatePresence mode="popLayout">
            {items.map((item) => (
              <QueueRow
                key={item.id}
                item={item}
                onApprove={async () => {
                  await reviewApi.approveReview(item.id);
                  qc.invalidateQueries({ queryKey: ["review-queue"] });
                }}
                onReject={async () => {
                  await reviewApi.rejectReview(item.id);
                  qc.invalidateQueries({ queryKey: ["review-queue"] });
                }}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function QueueRow({
  item,
  onApprove,
  onReject,
}: {
  item: ReviewQueueItem;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
}) {
  const [pending, startTransition] = useTransition();
  const [done, setDone] = useState<"approved" | "rejected" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const name = item.name || `${item.network} · ${item.objective}`;
  const actionable = item.status === "draft" || item.status === "in_review" || item.status === "changes_requested";

  function approve() {
    setActionError(null);
    startTransition(async () => {
      try {
        await onApprove();
        setDone("approved");
      } catch (err) {
        setActionError(`Approve failed: ${(err as Error).message}`);
      }
    });
  }

  function reject() {
    setActionError(null);
    startTransition(async () => {
      try {
        await onReject();
        setDone("rejected");
      } catch (err) {
        setActionError(`Reject failed: ${(err as Error).message}`);
      }
    });
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={cn(
        "flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 transition-colors",
        done === "approved" && "bg-success/[0.04]",
        done === "rejected" && "bg-danger/[0.04]",
      )}
    >
      <Link href={`/app/review/${item.id}`} className="flex items-center gap-3 min-w-0 flex-1 group">
        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Megaphone className="w-5 h-5 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-sm text-text font-medium truncate group-hover:text-accent transition-colors">
            {name}
          </div>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-text-muted">
            <span className="truncate">
              {item.network} · {item.objective}
            </span>
            <span className="text-text-muted/50">·</span>
            <span className="inline-flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDate(item.created_at)}
            </span>
            {item.dry_run && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-text-muted">
                dry-run
              </span>
            )}
          </div>
          {actionError && (
            <div className="text-[11px] text-danger mt-1">{actionError}</div>
          )}
        </div>
      </Link>

      <div className="flex items-center gap-3 shrink-0 pl-13 sm:pl-0">
        <span className={cn("badge", statusBadgeClass(item.status))}>
          {STATUS_LABEL[item.status] ?? item.status}
        </span>

        {done === "approved" ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-success font-medium">
            <CheckCircle2 className="w-4 h-4" />
            Approved
          </span>
        ) : done === "rejected" ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-danger font-medium">
            <X className="w-4 h-4" />
            Rejected
          </span>
        ) : actionable ? (
          <div className="flex items-center gap-2">
            <button
              onClick={approve}
              disabled={pending}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition",
                pending
                  ? "bg-white/[0.04] text-text-muted cursor-wait"
                  : "bg-success/15 text-success hover:bg-success/25",
              )}
            >
              {pending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              Approve
            </button>
            <button
              onClick={reject}
              disabled={pending}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition",
                pending
                  ? "bg-white/[0.04] text-text-muted cursor-wait"
                  : "bg-danger/15 text-danger hover:bg-danger/25",
              )}
            >
              {pending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
              Reject
            </button>
            <Link
              href={`/app/review/${item.id}`}
              className="hidden sm:inline-flex items-center gap-1 text-xs text-accent font-medium hover:text-accent/80 transition"
            >
              Details
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <Link
            href={`/app/review/${item.id}`}
            className="inline-flex items-center gap-1 text-xs text-accent font-medium hover:text-accent/80 transition"
          >
            View
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </motion.div>
  );
}
