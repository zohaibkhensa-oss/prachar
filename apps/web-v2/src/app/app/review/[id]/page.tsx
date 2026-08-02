"use client";

/**
 * Review Detail page — `/app/review/{id}`
 *
 * Shows the campaign preview (rendered from CampaignOut fields), an AI
 * suggestions sidebar, inline-editable fields, and a bottom action bar with
 * Request Changes / Approve / Publish.
 */
import { useState, useTransition, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Megaphone,
  CheckCircle2,
  Send,
  MessageSquare,
  Loader2,
  Sparkles,
  AlertCircle,
  Rocket,
  PanelRightOpen,
  PanelRightClose,
  Highlighter,
  History,
} from "lucide-react";
import {
  reviewApi,
  type ReviewQueueItem,
  type Suggestion,
  type ReviewCommentItem,
  type ReviewVersionItem,
} from "@/lib/review";
import { Skeleton } from "@/components/ui/skeleton";
import { EditableField } from "@/components/review/EditableField";
import { SuggestionPanel } from "@/components/review/SuggestionPanel";
import { InlineComments } from "@/components/review/InlineComments";
import { VersionHistory } from "@/components/review/VersionHistory";
import { cn } from "@/lib/utils";

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const qc = useQueryClient();

  // ─── Data ──────────────────────────────────────────────────────────────
  const {
    data: campaign,
    isLoading,
    error,
  } = useQuery<ReviewQueueItem>({
    queryKey: ["review-campaign", id],
    queryFn: () => reviewApi.getReviewQueue().then((rows) => {
      const found = rows.find((r) => r.id === id);
      if (!found) throw new Error("Campaign not found in review queue");
      return found;
    }),
    enabled: !!id,
    retry: 1,
  });

  const {
    data: suggestions,
    isLoading: suggestionsLoading,
    error: suggestionsError,
    refetch: refetchSuggestions,
  } = useQuery<Suggestion[]>({
    queryKey: ["review-suggestions", id],
    queryFn: () => reviewApi.getSuggestions(id),
    enabled: !!id,
    retry: 1,
  });

  // ─── Inline comments ──────────────────────────────────────────────────
  // `rightPanel` controls which panel is shown on the right side:
  // "comments" | "history" | null (null → AI suggestions).
  const [rightPanel, setRightPanel] = useState<"comments" | "history" | null>(null);
  const showComments = rightPanel === "comments";
  const showHistory = rightPanel === "history";
  const [pendingAnchor, setPendingAnchor] = useState<string | null>(null);
  const [commentFloating, setCommentFloating] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const previewRef = useRef<HTMLDivElement>(null);

  const {
    data: comments,
    isLoading: commentsLoading,
  } = useQuery<ReviewCommentItem[]>({
    queryKey: ["review-comments", id],
    queryFn: () => reviewApi.getComments(id),
    enabled: !!id && showComments,
    retry: 1,
  });

  // ─── Version history ──────────────────────────────────────────────────
  const {
    data: versions,
    isLoading: versionsLoading,
  } = useQuery<ReviewVersionItem[]>({
    queryKey: ["review-versions", id],
    queryFn: () => reviewApi.getVersions(id),
    enabled: !!id && showHistory,
    retry: 1,
  });
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);

  // ─── Local state for inline edits (optimistic field values) ────────────
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [applyingIndex, setApplyingIndex] = useState<number | null>(null);
  const [appliedIndices, setAppliedIndices] = useState<number[]>([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);
  const [approvedSuccess, setApprovedSuccess] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [commentMutating, startCommentTransition] = useTransition();

  function fieldVal(field: string, fallback: string): string {
    return fieldValues[field] ?? fallback ?? "";
  }

  function handleSaveField(field: string) {
    return async (value: string) => {
      await reviewApi.editField(id, field, value);
      setFieldValues((prev) => ({ ...prev, [field]: value }));
      qc.invalidateQueries({ queryKey: ["review-campaign", id] });
      qc.invalidateQueries({ queryKey: ["review-versions", id] });
    };
  }

  function applySuggestion(s: Suggestion, index: number) {
    // Heuristic: try to map the suggestion to a known editable field.
    // The backend editable fields are: network, objective, budget_daily,
    // currency, dry_run, audience_spec, bid_strategy, guardrails.
    // We attempt to detect the target field from `what_to_change`.
    const target = guessSuggestionField(s.what_to_change);
    setApplyingIndex(index);
    startTransition(async () => {
      try {
        setActionError(null);
        if (target) {
          await reviewApi.editField(id, target, s.suggested_replacement);
          setFieldValues((prev) => ({ ...prev, [target]: s.suggested_replacement }));
          qc.invalidateQueries({ queryKey: ["review-campaign", id] });
          qc.invalidateQueries({ queryKey: ["review-versions", id] });
        }
        setAppliedIndices((prev) => [...prev, index]);
      } catch (err) {
        setActionError(
          `Could not apply suggestion: ${(err as Error).message}. You can still edit the field manually.`,
        );
      } finally {
        setApplyingIndex(null);
      }
    });
  }

  function doApprove() {
    setActionError(null);
    startTransition(async () => {
      try {
        await reviewApi.approveReview(id);
        setShowApproveConfirm(false);
        setApprovedSuccess(true);
        qc.invalidateQueries({ queryKey: ["review-campaign", id] });
        qc.invalidateQueries({ queryKey: ["review-queue"] });
      } catch (err) {
        setActionError(`Approve failed: ${(err as Error).message}`);
      }
    });
  }

  function doPublish() {
    setActionError(null);
    startTransition(async () => {
      try {
        await reviewApi.publishReview(id);
        qc.invalidateQueries({ queryKey: ["review-campaign", id] });
        qc.invalidateQueries({ queryKey: ["review-queue"] });
        router.push("/app/review");
      } catch (err) {
        setActionError(`Publish failed: ${(err as Error).message}`);
      }
    });
  }

  function doRequestChanges() {
    setActionError(null);
    startTransition(async () => {
      try {
        await reviewApi.requestChanges(id, feedback);
        setShowFeedback(false);
        setFeedback("");
        qc.invalidateQueries({ queryKey: ["review-campaign", id] });
        qc.invalidateQueries({ queryKey: ["review-queue"] });
        router.push("/app/review");
      } catch (err) {
        setActionError(`Request changes failed: ${(err as Error).message}`);
      }
    });
  }

  // ─── Text selection → comment flow ──────────────────────────────────────
  // When the user selects text inside the campaign preview, a small floating
  // "Comment" button appears near the selection. Clicking it opens the
  // comments sidebar with the selected text pre-filled as the anchor.
  const handlePreviewMouseUp = useCallback(() => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      setCommentFloating(null);
      return;
    }
    const text = selection.toString().trim();
    if (text.length === 0) {
      setCommentFloating(null);
      return;
    }
    // Only fire if the selection is within the preview container.
    const previewEl = previewRef.current;
    if (!previewEl) return;
    const range = selection.getRangeAt(0);
    if (!previewEl.contains(range.commonAncestorContainer)) {
      setCommentFloating(null);
      return;
    }
    const rect = range.getBoundingClientRect();
    setCommentFloating({ x: rect.left + rect.width / 2, y: rect.top - 8 });
  }, []);

  function handleFloatingCommentClick() {
    const selection = window.getSelection();
    const text = selection?.toString().trim() ?? "";
    if (text.length > 0) {
      setPendingAnchor(text);
      setRightPanel("comments");
    }
    setCommentFloating(null);
    // Clear the native selection so the highlight doesn't persist visually.
    selection?.removeAllRanges();
  }

  // ─── Comment mutations ──────────────────────────────────────────────────
  function handleAddComment(anchorText: string, body: string) {
    startCommentTransition(async () => {
      try {
        await reviewApi.addComment(id, { anchor_text: anchorText, body });
        setPendingAnchor(null);
        qc.invalidateQueries({ queryKey: ["review-comments", id] });
      } catch (err) {
        setActionError(`Comment failed: ${(err as Error).message}`);
      }
    });
  }

  function handleReply(parentId: string, anchorText: string, body: string) {
    startCommentTransition(async () => {
      try {
        await reviewApi.addComment(id, {
          anchor_text: anchorText,
          body,
          parent_id: parentId,
        });
        qc.invalidateQueries({ queryKey: ["review-comments", id] });
      } catch (err) {
        setActionError(`Reply failed: ${(err as Error).message}`);
      }
    });
  }

  function handleResolveComment(commentId: string) {
    startCommentTransition(async () => {
      try {
        await reviewApi.resolveComment(id, commentId);
        qc.invalidateQueries({ queryKey: ["review-comments", id] });
      } catch (err) {
        setActionError(`Resolve failed: ${(err as Error).message}`);
      }
    });
  }

  // ─── Version restore ──────────────────────────────────────────────────
  function handleRestoreVersion(versionNumber: number) {
    startTransition(async () => {
      try {
        setActionError(null);
        setRestoringVersion(versionNumber);
        await reviewApi.restoreVersion(id, versionNumber);
        // Clear optimistic field values so the restored values show through.
        setFieldValues({});
        qc.invalidateQueries({ queryKey: ["review-campaign", id] });
        qc.invalidateQueries({ queryKey: ["review-versions", id] });
      } catch (err) {
        setActionError(`Restore failed: ${(err as Error).message}`);
      } finally {
        setRestoringVersion(null);
      }
    });
  }

  // ─── Render ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32 rounded-lg" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="lg:col-span-2 h-96 rounded-2xl" />
          <Skeleton className="h-96 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <AlertCircle className="w-10 h-10 text-danger mx-auto mb-3" />
        <h2 className="font-display text-lg font-semibold text-text mb-1">
          Campaign not found
        </h2>
        <p className="text-sm text-text-secondary mb-6">
          {(error as Error)?.message ?? "This campaign may not be in the review queue."}
        </p>
        <Link href="/app/review" className="btn-primary inline-flex">
          <ArrowLeft className="w-4 h-4" />
          Back to queue
        </Link>
      </div>
    );
  }

  const status = campaign.status;
  const canPublish = status === "approved";

  // Stringify JSON fields for display/editing.
  const audienceSpecStr = fieldVal(
    "audience_spec",
    campaign.audience_spec ? JSON.stringify(campaign.audience_spec, null, 2) : "",
  );
  const bidStrategyStr = fieldVal(
    "bid_strategy",
    campaign.bid_strategy ? JSON.stringify(campaign.bid_strategy, null, 2) : "",
  );
  const guardrailsStr = fieldVal(
    "guardrails",
    campaign.guardrails ? JSON.stringify(campaign.guardrails, null, 2) : "",
  );

  return (
    <div className="space-y-6 pb-32">
      {/* Back link */}
      <Link
        href="/app/review"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to queue
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
          <Megaphone className="w-6 h-6 text-accent" />
        </div>
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold text-text truncate">
            {campaign.name || `${campaign.network} campaign`}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge ${statusBadgeClass(status)}`}>{statusLabel(status)}</span>
            <span className="text-xs text-text-muted">
              {campaign.network} · {campaign.objective}
            </span>
          </div>
        </div>
        {/* Panel toggles: Comments + History */}
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <button
            type="button"
            onClick={() => setRightPanel((p) => (p === "comments" ? null : "comments"))}
            className={cn(
              "btn-ghost !px-3 !py-2 !text-xs",
              showComments && "!bg-accent/10 !text-accent",
            )}
            title="Toggle inline comments"
          >
            {showComments ? (
              <>
                <PanelRightClose className="w-4 h-4" />
                <span className="hidden sm:inline">Hide comments</span>
              </>
            ) : (
              <>
                <PanelRightOpen className="w-4 h-4" />
                <span className="hidden sm:inline">Comments</span>
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => setRightPanel((p) => (p === "history" ? null : "history"))}
            className={cn(
              "btn-ghost !px-3 !py-2 !text-xs",
              showHistory && "!bg-accent/10 !text-accent",
            )}
            title="Toggle version history"
          >
            <History className="w-4 h-4" />
            <span className="hidden sm:inline">History</span>
          </button>
        </div>
      </div>

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 p-3 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
          <p className="text-xs text-danger">{actionError}</p>
        </div>
      )}

      {/* Main layout: preview + sidebar (comments / history / suggestions) */}
      <div
        className={cn(
          "grid grid-cols-1 gap-6",
          (showComments || showHistory) ? "lg:grid-cols-[1fr_380px]" : "lg:grid-cols-3",
        )}
      >
        {/* ─── Campaign preview / editable fields ─── */}
        <div className={cn("space-y-6", !(showComments || showHistory) && "lg:col-span-2")}>
          <div
            ref={previewRef}
            onMouseUp={handlePreviewMouseUp}
            className="glass-strong rounded-2xl p-6 space-y-5"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent" />
              <h2 className="font-display text-base font-semibold text-text">Campaign details</h2>
              <span className="text-xs text-text-muted ml-auto">
                {showComments ? "Highlight text to comment" : "Click any field to edit"}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
              <EditableField
                field="network"
                label="Network"
                value={fieldVal("network", campaign.network)}
                onSave={handleSaveField("network")}
              />
              <EditableField
                field="objective"
                label="Objective"
                value={fieldVal("objective", campaign.objective)}
                onSave={handleSaveField("objective")}
              />
              <EditableField
                field="budget_daily"
                label="Daily Budget"
                value={fieldVal("budget_daily", String(campaign.budget_daily))}
                onSave={handleSaveField("budget_daily")}
              />
              <EditableField
                field="currency"
                label="Currency"
                value={fieldVal("currency", campaign.currency)}
                onSave={handleSaveField("currency")}
              />
            </div>

            <div className="space-y-4 pt-2 border-t border-white/[0.04]">
              <EditableField
                field="audience_spec"
                label="Audience Spec (JSON)"
                value={audienceSpecStr}
                onSave={handleSaveField("audience_spec")}
                placeholder='{"interests": [], "geo": []}'
              />
              <EditableField
                field="bid_strategy"
                label="Bid Strategy (JSON)"
                value={bidStrategyStr}
                onSave={handleSaveField("bid_strategy")}
                placeholder='{"type": "cpc", "amount": 0}'
              />
              <EditableField
                field="guardrails"
                label="Guardrails (JSON)"
                value={guardrailsStr}
                onSave={handleSaveField("guardrails")}
                placeholder='{"max_cpa": 0, "caps": {}}'
              />
            </div>
          </div>
        </div>

        {/* ─── Right sidebar: comments / history / AI suggestions ─── */}
        <div className={cn(!(showComments || showHistory) && "lg:col-span-1")}>
          <div className="glass-strong rounded-2xl p-5 lg:sticky lg:top-6 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
            {showComments ? (
              <InlineComments
                comments={comments ?? []}
                isLoading={commentsLoading}
                pendingAnchor={pendingAnchor}
                onAddComment={handleAddComment}
                onReply={handleReply}
                onResolve={handleResolveComment}
                onClearPendingAnchor={() => setPendingAnchor(null)}
                mutating={commentMutating}
              />
            ) : showHistory ? (
              <VersionHistory
                versions={versions ?? []}
                isLoading={versionsLoading}
                onRestore={handleRestoreVersion}
                restoring={pending}
                restoringVersion={restoringVersion}
              />
            ) : (
              <SuggestionPanel
                suggestions={suggestions ?? []}
                isLoading={suggestionsLoading}
                applyingIndex={applyingIndex}
                appliedIndices={appliedIndices}
                onApply={applySuggestion}
                onRefresh={() => refetchSuggestions()}
                error={suggestionsError ? (suggestionsError as Error).message : null}
              />
            )}
          </div>
        </div>
      </div>

      {/* ─── Floating "Comment" button (appears on text selection) ─── */}
      {commentFloating && (
        <button
          type="button"
          onClick={handleFloatingCommentClick}
          className="fixed z-50 btn-primary !px-3 !py-1.5 !text-xs shadow-xl"
          style={{
            left: `${commentFloating.x}px`,
            top: `${commentFloating.y}px`,
            transform: "translate(-50%, -100%)",
          }}
        >
          <Highlighter className="w-3.5 h-3.5" />
          Comment
        </button>
      )}

      {/* ─── Feedback modal ─── */}
      {showFeedback && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => !pending && setShowFeedback(false)}
        >
          <div
            className="glass-strong rounded-2xl p-6 max-w-lg w-full space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-warning" />
              <h3 className="font-display text-lg font-semibold text-text">Request Changes</h3>
            </div>
            <p className="text-sm text-text-secondary">
              Request changes to this campaign. Tell PRACHAR AI what to fix:
            </p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="e.g. The headline doesn't mention our discount. Please add a clearer CTA…"
              rows={5}
              className="input-field resize-none"
              disabled={pending}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowFeedback(false)}
                disabled={pending}
                className="btn-ghost"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={doRequestChanges}
                disabled={pending || feedback.trim().length === 0}
                className="btn-primary"
              >
                {pending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending…
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Request Changes
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Approve confirmation modal ─── */}
      {showApproveConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => !pending && setShowApproveConfirm(false)}
        >
          <div
            className="glass-strong rounded-2xl p-6 max-w-md w-full space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-success" />
              <h3 className="font-display text-lg font-semibold text-text">Approve Campaign</h3>
            </div>
            <p className="text-sm text-text-secondary">
              Approve this campaign? It will be published to your channels.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowApproveConfirm(false)}
                disabled={pending}
                className="btn-ghost"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={doApprove}
                disabled={pending}
                className="btn-primary !bg-success/20 !text-success !border-success/30 hover:!bg-success/30"
              >
                {pending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Approving…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Approve
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── "What happens next" success screen (after approval) ─── */}
      {approvedSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass-strong rounded-2xl p-8 max-w-lg w-full space-y-5 text-center">
            <div className="w-14 h-14 rounded-full bg-success/15 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8 text-success" />
            </div>
            <h2 className="font-display text-2xl font-semibold text-text">
              Campaign approved!
            </h2>
            <p className="text-sm text-text-secondary">Here&apos;s what happens next:</p>
            <ol className="text-left space-y-3 text-sm text-text">
              <li className="flex gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-accent/15 text-accent flex items-center justify-center text-xs font-semibold">
                  1
                </span>
                <span>
                  We&apos;re publishing to{" "}
                  <span className="font-medium text-text">
                    {campaign.network}
                  </span>
                  .
                </span>
              </li>
              <li className="flex gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-accent/15 text-accent flex items-center justify-center text-xs font-semibold">
                  2
                </span>
                <span>You&apos;ll see results in Performance within 7 days.</span>
              </li>
            </ol>
            <div className="flex flex-col sm:flex-row gap-2 justify-center pt-2">
              <Link href="/app/performance" className="btn-primary inline-flex justify-center">
                View Performance
              </Link>
              <button
                type="button"
                onClick={() => router.push("/app")}
                className="btn-ghost inline-flex justify-center"
              >
                Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Bottom action bar ─── */}
      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/[0.06] bg-bg/90 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="text-xs text-text-muted hidden sm:block">
            Status: <span className="text-text font-medium">{statusLabel(status)}</span>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <button
              type="button"
              onClick={() => setShowFeedback(true)}
              disabled={pending || status === "draft"}
              className="btn-secondary"
              title={status === "draft" ? "Submit for review first" : "Send back for changes"}
            >
              <MessageSquare className="w-4 h-4" />
              Request Changes
            </button>
            <button
              type="button"
              onClick={() => setShowApproveConfirm(true)}
              disabled={pending || status === "approved" || status === "active"}
              className="btn-primary"
            >
              {pending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              Approve
            </button>
            <button
              type="button"
              onClick={doPublish}
              disabled={pending || !canPublish}
              className="btn-primary !bg-success/20 !text-success !border-success/30 hover:!bg-success/30"
              title={!canPublish ? "Approve the campaign first" : "Publish to the ad network"}
            >
              {pending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4" />
              )}
              Publish
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function statusLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "draft":
      return "badge-neutral";
    case "in_review":
      return "badge-info";
    case "changes_requested":
      return "badge-warning";
    case "approved":
      return "badge-success";
    case "active":
      return "badge-accent";
    default:
      return "badge-neutral";
  }
}

/**
 * Best-effort mapping of a suggestion's "what_to_change" text to a backend
 * editable field name. Returns null if no match — the UI will then prompt the
 * user to apply the change manually via inline edit.
 */
function guessSuggestionField(whatToChange: string): string | null {
  const text = whatToChange.toLowerCase();
  if (text.includes("network") || text.includes("channel") || text.includes("platform")) {
    return "network";
  }
  if (text.includes("objective") || text.includes("goal")) {
    return "objective";
  }
  if (text.includes("budget") || text.includes("spend") || text.includes("bid")) {
    if (text.includes("strategy")) return "bid_strategy";
    return "budget_daily";
  }
  if (text.includes("currency")) return "currency";
  if (text.includes("audience") || text.includes("targeting")) return "audience_spec";
  if (text.includes("guardrail") || text.includes("cap") || text.includes("limit")) {
    return "guardrails";
  }
  return null;
}
