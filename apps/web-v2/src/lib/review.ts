/**
 * Review workflow API client.
 *
 * Wraps the `/review/*` backend endpoints (apps/api/prachar_api/routers/review.py).
 * Uses the shared `api` fetcher from `./api` so auth headers + error handling are
 * consistent with the rest of the app.
 */
import { apiGet, apiPost, ApiError } from "./api";

// ─── Types ────────────────────────────────────────────────────────────────

export type ReviewStatus = "draft" | "in_review" | "changes_requested" | "approved" | "active" | "rejected";

/**
 * A campaign row as returned by `GET /review/queue` (CampaignOut).
 *
 * The backend `CampaignOut` schema currently exposes the core campaign fields.
 * `name` and `created_at` are optional because the schema may or may not
 * include them depending on backend version — the UI degrades gracefully.
 */
export interface ReviewQueueItem {
  id: string;
  brand_id: string;
  network: string;
  objective: string;
  budget_daily: number;
  currency: string;
  status: ReviewStatus;
  dry_run: boolean;
  guardrails: Record<string, unknown> | null;
  // Optional fields — present when the backend extends CampaignOut.
  name?: string;
  created_at?: string;
  audience_spec?: Record<string, unknown>;
  bid_strategy?: Record<string, unknown> | null;
}

/** A single AI-generated improvement suggestion. */
export interface Suggestion {
  what_to_change: string;
  why: string;
  suggested_replacement: string;
}

/** Request body for `PATCH /review/{id}/field`. */
export interface FieldEditRequest {
  field: string;
  value: string;
}

// ─── Inline comment types ──────────────────────────────────────────────────

/** Author info embedded in a comment (user email for display). */
export interface CommentAuthor {
  id: string;
  email: string;
}

/** A single inline comment with optional threaded replies. */
export interface ReviewCommentItem {
  id: string;
  campaign_id: string;
  author_id: string;
  parent_id: string | null;
  anchor_text: string;
  body: string;
  resolved: boolean;
  created_at: string;
  updated_at: string;
  author: CommentAuthor | null;
  replies: ReviewCommentItem[];
}

/** Request body for `POST /review/{id}/comments`. */
export interface AddCommentRequest {
  anchor_text: string;
  body: string;
  parent_id?: string;
}

// ─── Version history types ──────────────────────────────────────────────────

/** Author info embedded in a version (user email for display). */
export interface VersionAuthor {
  id: string;
  email: string;
}

/** A single version snapshot of a campaign. */
export interface ReviewVersionItem {
  id: string;
  campaign_id: string;
  author_id: string;
  version_number: number;
  snapshot: Record<string, unknown>;
  change_summary: string | null;
  created_at: string;
  author: VersionAuthor | null;
}

// ─── API client ───────────────────────────────────────────────────────────

/**
 * We need a PATCH helper. The shared `api.ts` only exposes GET/POST, so we
 * implement a thin PATCH wrapper here that mirrors the same auth + error
 * handling pattern. If `api.ts` later adds `apiPatch`, this can be swapped out.
 */
async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("prachar_token");
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let errBody: unknown = null;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text();
    }
    throw new ApiError(`API ${res.status}`, res.status, errBody);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const reviewApi = {
  /** List campaigns awaiting review (draft / in_review / changes_requested). */
  async getReviewQueue(): Promise<ReviewQueueItem[]> {
    return apiGet<ReviewQueueItem[]>("/review/queue");
  },

  /** Send a campaign back to the creator with feedback. */
  async requestChanges(id: string, feedback: string): Promise<ReviewQueueItem> {
    return apiPost<ReviewQueueItem>(`/review/${id}/request-changes`, { feedback });
  },

  /** Approve a campaign (moves status → approved). */
  async approveReview(id: string): Promise<ReviewQueueItem> {
    return apiPost<ReviewQueueItem>(`/review/${id}/approve`);
  },

  /** Reject a campaign outright (moves status → rejected). */
  async rejectReview(id: string): Promise<ReviewQueueItem> {
    return apiPost<ReviewQueueItem>(`/review/${id}/reject`);
  },

  /** Publish an approved campaign (moves status → active). */
  async publishReview(id: string): Promise<ReviewQueueItem> {
    return apiPost<ReviewQueueItem>(`/review/${id}/publish`);
  },

  /** Generate AI improvement suggestions for a campaign. */
  async getSuggestions(id: string): Promise<Suggestion[]> {
    return apiPost<Suggestion[]>(`/review/${id}/suggestions`);
  },

  /** Inline-edit a single field on a campaign. */
  async editField(id: string, field: string, value: string): Promise<ReviewQueueItem> {
    return apiPatch<ReviewQueueItem>(`/review/${id}/field`, { field, value });
  },

  /** List all comments (with threaded replies) for a campaign. */
  async getComments(campaignId: string): Promise<ReviewCommentItem[]> {
    return apiGet<ReviewCommentItem[]>(`/review/${campaignId}/comments`);
  },

  /** Add a comment (or reply) to a campaign. */
  async addComment(campaignId: string, body: AddCommentRequest): Promise<ReviewCommentItem> {
    return apiPost<ReviewCommentItem>(`/review/${campaignId}/comments`, body);
  },

  /** Toggle the resolved status of a comment. */
  async resolveComment(campaignId: string, commentId: string): Promise<ReviewCommentItem> {
    return apiPost<ReviewCommentItem>(`/review/${campaignId}/comments/${commentId}/resolve`);
  },

  // ─── Version history ──────────────────────────────────────────────────────

  /** List all versions for a campaign (newest first). */
  async getVersions(campaignId: string): Promise<ReviewVersionItem[]> {
    return apiGet<ReviewVersionItem[]>(`/review/${campaignId}/versions`);
  },

  /** Get a specific version's snapshot. */
  async getVersion(campaignId: string, versionNumber: number): Promise<ReviewVersionItem> {
    return apiGet<ReviewVersionItem>(`/review/${campaignId}/versions/${versionNumber}`);
  },

  /** Restore a previous version (creates a new version with the old content). */
  async restoreVersion(campaignId: string, versionNumber: number): Promise<ReviewQueueItem> {
    return apiPost<ReviewQueueItem>(`/review/${campaignId}/versions/${versionNumber}/restore`);
  },
};
