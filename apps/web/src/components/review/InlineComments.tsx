"use client";

/**
 * InlineComments — Google Docs-style inline comments sidebar.
 *
 * Renders a list of threaded comments anchored to highlighted text snippets
 * in the campaign preview. Each comment shows the anchor text, body, author,
 * timestamp, reply button, and resolve button. Resolved comments are
 * collapsed/grayed out. An "Add comment" input is shown at the top (and per-
 * comment when replying).
 */
import { useState } from "react";
import {
  MessageSquare,
  Reply,
  CheckCircle2,
  RotateCcw,
  Send,
  Loader2,
  Highlighter,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReviewCommentItem } from "@/lib/review";

export interface InlineCommentsProps {
  comments: ReviewCommentItem[];
  isLoading?: boolean;
  /** Pre-filled anchor text from a text selection in the preview. */
  pendingAnchor?: string | null;
  /** Called when the user submits a new top-level comment. */
  onAddComment: (anchorText: string, body: string) => void | Promise<void>;
  /** Called when the user submits a reply to a comment. */
  onReply: (parentId: string, anchorText: string, body: string) => void | Promise<void>;
  /** Called when the user toggles resolve on a comment. */
  onResolve: (commentId: string) => void | Promise<void>;
  /** Called when the pending anchor is dismissed (cancel / submitted). */
  onClearPendingAnchor?: () => void;
  /** Whether a mutation is currently in-flight. */
  mutating?: boolean;
}

export function InlineComments({
  comments,
  isLoading,
  pendingAnchor,
  onAddComment,
  onReply,
  onResolve,
  onClearPendingAnchor,
  mutating,
}: InlineCommentsProps) {
  const [newCommentBody, setNewCommentBody] = useState("");
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [collapsedResolved, setCollapsedResolved] = useState<Set<string>>(new Set());

  async function submitTopLevel() {
    if (!pendingAnchor || newCommentBody.trim().length === 0) return;
    await onAddComment(pendingAnchor, newCommentBody.trim());
    setNewCommentBody("");
    onClearPendingAnchor?.();
  }

  async function submitReply(parentId: string, anchorText: string) {
    if (replyBody.trim().length === 0) return;
    await onReply(parentId, anchorText, replyBody.trim());
    setReplyBody("");
    setReplyingTo(null);
  }

  function toggleCollapse(commentId: string) {
    setCollapsedResolved((prev) => {
      const next = new Set(prev);
      if (next.has(commentId)) next.delete(commentId);
      else next.add(commentId);
      return next;
    });
  }

  const unresolvedCount = comments.filter((c) => !c.resolved).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-accent" />
          </div>
          <div>
            <div className="font-display text-sm font-semibold text-text">Comments</div>
            <div className="text-xs text-text-muted">
              {isLoading
                ? "Loading…"
                : `${unresolvedCount} open · ${comments.length - unresolvedCount} resolved`}
            </div>
          </div>
        </div>
      </div>

      {/* Add comment box (always visible; anchor pre-filled when text selected) */}
      <div className="glass rounded-xl p-4 space-y-3">
        {pendingAnchor ? (
          <div className="flex items-start gap-2 rounded-lg bg-accent/10 border border-accent/20 px-3 py-2">
            <Highlighter className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="text-xs text-accent font-medium mb-0.5">Selected text</div>
              <p className="text-xs text-text line-clamp-2 break-words">&ldquo;{pendingAnchor}&rdquo;</p>
            </div>
            <button
              type="button"
              onClick={() => {
                onClearPendingAnchor?.();
                setNewCommentBody("");
              }}
              className="text-xs text-text-muted hover:text-text shrink-0 ml-auto"
            >
              ✕
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Highlighter className="w-3.5 h-3.5" />
            <span>Highlight text in the preview to comment on it</span>
          </div>
        )}
        <textarea
          value={newCommentBody}
          onChange={(e) => setNewCommentBody(e.target.value)}
          placeholder="Write a comment…"
          rows={2}
          className="input-field resize-none text-sm"
          disabled={mutating}
        />
        <div className="flex justify-end">
          <button
            type="button"
            onClick={submitTopLevel}
            disabled={mutating || !pendingAnchor || newCommentBody.trim().length === 0}
            className="btn-primary !px-3 !py-1.5 !text-xs"
          >
            {mutating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Posting…
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                Comment
              </>
            )}
          </button>
        </div>
      </div>

      {/* Loading skeleton */}
      {isLoading && comments.length === 0 && (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <div key={i} className="glass rounded-xl p-4 space-y-2 animate-pulse">
              <div className="h-3 w-1/3 rounded bg-white/[0.06]" />
              <div className="h-2 w-full rounded bg-white/[0.04]" />
              <div className="h-2 w-4/5 rounded bg-white/[0.04]" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && comments.length === 0 && (
        <div className="glass rounded-xl p-6 text-center">
          <MessageSquare className="w-8 h-8 text-text-muted mx-auto mb-2" />
          <p className="text-sm text-text-secondary">No comments yet.</p>
          <p className="text-xs text-text-muted mt-1">
            Highlight text in the campaign preview to start a discussion.
          </p>
        </div>
      )}

      {/* Comments list */}
      {comments.length > 0 && (
        <div className="space-y-3">
          {comments.map((comment) => (
            <CommentThread
              key={comment.id}
              comment={comment}
              collapsed={collapsedResolved.has(comment.id)}
              onToggleCollapse={() => toggleCollapse(comment.id)}
              replyingTo={replyingTo}
              replyBody={replyBody}
              onReplyBodyChange={setReplyBody}
              onStartReply={() => {
                setReplyingTo(replyingTo === comment.id ? null : comment.id);
                setReplyBody("");
              }}
              onSubmitReply={() => submitReply(comment.id, comment.anchor_text)}
              onCancelReply={() => {
                setReplyingTo(null);
                setReplyBody("");
              }}
              onResolve={() => onResolve(comment.id)}
              mutating={mutating}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Single comment thread (top-level + replies) ────────────────────────────

interface CommentThreadProps {
  comment: ReviewCommentItem;
  collapsed: boolean;
  onToggleCollapse: () => void;
  replyingTo: string | null;
  replyBody: string;
  onReplyBodyChange: (v: string) => void;
  onStartReply: () => void;
  onSubmitReply: () => void | Promise<void>;
  onCancelReply: () => void;
  onResolve: () => void | Promise<void>;
  mutating?: boolean;
}

function CommentThread({
  comment,
  collapsed,
  onToggleCollapse,
  replyingTo,
  replyBody,
  onReplyBodyChange,
  onStartReply,
  onSubmitReply,
  onCancelReply,
  onResolve,
  mutating,
}: CommentThreadProps) {
  const isResolved = comment.resolved;
  const isReplying = replyingTo === comment.id;

  return (
    <div
      className={cn(
        "glass rounded-xl overflow-hidden transition-opacity",
        isResolved && "opacity-60",
      )}
    >
      {/* Anchor text banner */}
      <div className="flex items-start gap-2 bg-accent/[0.06] border-b border-accent/10 px-4 py-2">
        <Highlighter className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
        <p className="text-xs text-text-secondary line-clamp-2 break-words flex-1">
          &ldquo;{comment.anchor_text}&rdquo;
        </p>
        {isResolved && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="text-text-muted hover:text-text shrink-0"
          >
            {collapsed ? (
              <ChevronRight className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        )}
      </div>

      {/* Comment body — hidden when resolved + collapsed */}
      {!(isResolved && collapsed) && (
        <div className="p-4 space-y-3">
          {/* Main comment */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-text">
                {comment.author?.email ?? "Unknown"}
              </span>
              <span className="text-xs text-text-muted">
                {formatTimestamp(comment.created_at)}
              </span>
              {isResolved && (
                <span className="badge badge-success !text-[10px] !px-1.5 !py-0.5">
                  Resolved
                </span>
              )}
            </div>
            <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
              {comment.body}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onStartReply}
              disabled={mutating}
              className="btn-ghost !px-2 !py-1 !text-xs"
            >
              <Reply className="w-3.5 h-3.5" />
              Reply
            </button>
            <button
              type="button"
              onClick={onResolve}
              disabled={mutating}
              className={cn(
                "btn-ghost !px-2 !py-1 !text-xs",
                isResolved && "!text-success",
              )}
            >
              {isResolved ? (
                <>
                  <RotateCcw className="w-3.5 h-3.5" />
                  Reopen
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Resolve
                </>
              )}
            </button>
          </div>

          {/* Reply input */}
          {isReplying && (
            <div className="space-y-2 pl-4 border-l-2 border-accent/20">
              <textarea
                value={replyBody}
                onChange={(e) => onReplyBodyChange(e.target.value)}
                placeholder="Write a reply…"
                rows={2}
                className="input-field resize-none text-sm"
                disabled={mutating}
                autoFocus
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onSubmitReply}
                  disabled={mutating || replyBody.trim().length === 0}
                  className="btn-primary !px-3 !py-1.5 !text-xs"
                >
                  {mutating ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                  Reply
                </button>
                <button
                  type="button"
                  onClick={onCancelReply}
                  disabled={mutating}
                  className="btn-ghost !px-3 !py-1.5 !text-xs"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Threaded replies */}
          {comment.replies.length > 0 && (
            <div className="space-y-3 pl-4 border-l-2 border-white/[0.06]">
              {comment.replies.map((reply) => (
                <div key={reply.id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-text">
                      {reply.author?.email ?? "Unknown"}
                    </span>
                    <span className="text-xs text-text-muted">
                      {formatTimestamp(reply.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
                    {reply.body}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
