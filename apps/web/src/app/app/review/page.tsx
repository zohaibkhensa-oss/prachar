"use client";

/**
 * Review Queue page — `/app/review`
 *
 * Lists campaigns with status in (draft, in_review, changes_requested).
 * Filter by status, sort by date (newest first). Each row links to the
 * review detail page at `/app/review/{id}`.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ClipboardList,
  ArrowRight,
  Megaphone,
  Filter,
  Calendar,
} from "lucide-react";
import { reviewApi, type ReviewQueueItem, type ReviewStatus } from "@/lib/review";
import { Skeleton } from "@/components/ui/skeleton";

type StatusFilter = "all" | ReviewStatus;

const STATUS_LABEL: Record<ReviewStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  changes_requested: "Changes Requested",
  approved: "Approved",
  active: "Active",
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
      </div>

      {/* Filter bar */}
      <div className="glass rounded-xl p-4 flex items-center gap-3">
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
            <Skeleton key={i} className="h-20 rounded-xl" />
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
        <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
          <ClipboardList className="w-10 h-10 text-text-muted mx-auto mb-3" />
          <h2 className="font-display text-lg font-semibold text-text mb-1">
            No campaigns awaiting review
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            When campaigns are created they&apos;ll appear here for your approval.
          </p>
          <Link href="/app/campaigns" className="btn-primary inline-flex group">
            Go to campaigns
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      )}

      {/* Queue list */}
      {!isLoading && !error && items.length > 0 && (
        <div className="glass-strong rounded-2xl divide-y divide-white/[0.04]">
          {items.map((item) => (
            <QueueRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const name = item.name || `${item.network} · ${item.objective}`;
  return (
    <Link
      href={`/app/review/${item.id}`}
      className="flex items-center justify-between p-4 hover:bg-white/[0.03] transition-colors group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Megaphone className="w-5 h-5 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-sm text-text font-medium truncate">{name}</div>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-text-muted">
            <span className="truncate">
              {item.network} · {item.objective}
            </span>
            <span className="text-text-muted/50">·</span>
            <span className="inline-flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDate(item.created_at)}
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span className={`badge ${statusBadgeClass(item.status)}`}>
          {STATUS_LABEL[item.status] ?? item.status}
        </span>
        <span className="text-xs text-accent font-medium hidden sm:inline">Review</span>
        <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-text transition-colors" />
      </div>
    </Link>
  );
}
