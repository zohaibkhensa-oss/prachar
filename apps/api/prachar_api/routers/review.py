from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import Actor, Brand, Campaign, ReviewComment, ReviewVersion, User
from ..models.enums import CampaignStatus
from ..schemas import CampaignOut
from prachar_shared.ai_gateway import AIGateway
from prachar_shared.marketing_intelligence.review_engine import (
    Suggestion,
    generate_suggestions,
)

router = APIRouter(prefix="/review", tags=["review"])

# Statuses that appear in the review queue.
_QUEUE_STATUSES = (
    CampaignStatus.draft,
    CampaignStatus.in_review,
    CampaignStatus.changes_requested,
)

# Fields that may be inline-edited via PATCH /review/{id}/field.
# Maps field name → coercion callable that converts the incoming string value
# to the correct Python type for the column.
_EDITABLE_FIELDS: dict[str, Any] = {
    "network": str,
    "objective": str,
    "budget_daily": float,
    "currency": str,
    "dry_run": lambda v: str(v).lower() in ("true", "1", "yes"),
    "audience_spec": json.loads,
    "bid_strategy": json.loads,
    "guardrails": json.loads,
}


class RequestChangesIn(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)


class SuggestionOut(BaseModel):
    what_to_change: str
    why: str
    suggested_replacement: str


class FieldEditIn(BaseModel):
    field: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=0, max_length=10000)


async def _get_tenant_campaign(
    session: SessionDep, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> Campaign:
    res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    )
    camp = res.scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found")
    return camp


def _campaign_snapshot(camp: Campaign) -> dict[str, Any]:
    """Build a JSON-serialisable snapshot of the campaign's editable state."""
    return CampaignOut.model_validate(camp).model_dump(mode="json")


async def _next_version_number(
    session: SessionDep, campaign_id: uuid.UUID
) -> int:
    """Return the next version_number for a campaign (1-based)."""
    res = await session.execute(
        select(func.coalesce(func.max(ReviewVersion.version_number), 0)).where(
            ReviewVersion.campaign_id == campaign_id
        )
    )
    return int(res.scalar_one()) + 1


async def _create_version(
    session: SessionDep,
    camp: Campaign,
    author_id: uuid.UUID,
    tenant_id: uuid.UUID,
    change_summary: str | None,
) -> ReviewVersion:
    """Persist a new ReviewVersion snapshot for ``camp``."""
    version = ReviewVersion(
        tenant_id=tenant_id,
        campaign_id=camp.id,
        author_id=author_id,
        version_number=await _next_version_number(session, camp.id),
        snapshot=_campaign_snapshot(camp),
        change_summary=change_summary,
    )
    session.add(version)
    await session.flush()
    return version


@router.get("/queue", response_model=list[CampaignOut])
async def queue(user: CurrentUser, session: SessionDep) -> list[CampaignOut]:
    """List all draft / in_review / changes_requested campaigns for the tenant."""
    res = await session.execute(
        select(Campaign)
        .where(Campaign.tenant_id == user.tenant_id, Campaign.status.in_(_QUEUE_STATUSES))
        .order_by(Campaign.created_at.desc())
    )
    return [CampaignOut.model_validate(c) for c in res.scalars().all()]


@router.post("/{campaign_id}/request-changes", response_model=CampaignOut)
async def request_changes(
    campaign_id: uuid.UUID,
    body: RequestChangesIn,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    # Only campaigns that are currently under review (or freshly drafted and
    # submitted for review) can be sent back for changes.
    if camp.status not in (CampaignStatus.in_review, CampaignStatus.approved):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot request changes from status '{camp.status}'",
        )
    camp.status = CampaignStatus.changes_requested
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.request_changes",
        entity_type="campaign",
        entity_id=camp.id,
        payload={"feedback": body.feedback, "from_status": str(camp.status)},
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


@router.post("/{campaign_id}/approve", response_model=CampaignOut)
async def approve(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    if camp.status not in (CampaignStatus.draft, CampaignStatus.in_review, CampaignStatus.changes_requested):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot approve from status '{camp.status}'",
        )
    camp.status = CampaignStatus.approved
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.approve",
        entity_type="campaign",
        entity_id=camp.id,
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


@router.post("/{campaign_id}/reject", response_model=CampaignOut)
async def reject(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    """Reject a campaign outright (terminal — moves status → rejected)."""
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    if camp.status not in (CampaignStatus.draft, CampaignStatus.in_review, CampaignStatus.changes_requested):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot reject from status '{camp.status}'",
        )
    camp.status = CampaignStatus.rejected
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.reject",
        entity_type="campaign",
        entity_id=camp.id,
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


@router.post("/{campaign_id}/publish", response_model=CampaignOut)
async def publish(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    if camp.status != CampaignStatus.approved:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot publish from status '{camp.status}' — must be approved first",
        )
    camp.status = CampaignStatus.active
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.publish",
        entity_type="campaign",
        entity_id=camp.id,
    )
    await session.commit()

    # Fire-and-forget: enqueue the publish_campaign Celery task so the
    # campaign is pushed to each connected channel adapter.  The import is
    # lazy to avoid a circular dependency between the API and worker packages.
    # Broker failures are swallowed so the endpoint never breaks if Redis is
    # down — the campaign is already marked active in the DB.
    try:
        from prachar_workers.celery_app import app as celery_app

        celery_app.send_task(
            "prachar_workers.publish.publish_campaign",
            args=[str(camp.id)],
            queue="ads",
        )
    except Exception:  # noqa: BLE001 - fire and forget
        pass

    return CampaignOut.model_validate(camp)


@router.post("/{campaign_id}/suggestions", response_model=list[SuggestionOut])
async def suggestions(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[SuggestionOut]:
    """Generate 3-5 AI-powered improvement suggestions for a draft campaign."""
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    # Load the brand for context.
    brand_res = await session.execute(
        select(Brand).where(Brand.id == camp.brand_id)
    )
    brand = brand_res.scalar_one_or_none()
    brand_name = getattr(brand, "name", "") if brand else ""

    campaign_context: dict[str, Any] = {
        "brand_name": brand_name,
        "goal": str(getattr(camp, "objective", "") or ""),
        "budget": str(getattr(camp, "budget_daily", "") or ""),
        "network": str(getattr(camp, "network", "") or ""),
        "objective": str(getattr(camp, "objective", "") or ""),
        "audience": str(getattr(camp, "audience_spec", "") or ""),
        "campaign_analysis": str(getattr(camp, "guardrails", "") or ""),
    }

    plan = await get_tenant_plan(session, user)
    gw = AIGateway()
    raw_suggestions = generate_suggestions(
        campaign_context=campaign_context,
        gateway=gw,
        tenant_id=user.tenant_id,
        plan=plan,
    )
    return [SuggestionOut(**s.to_dict()) for s in raw_suggestions]


@router.patch("/{campaign_id}/field", response_model=CampaignOut)
async def edit_field(
    campaign_id: uuid.UUID,
    body: FieldEditIn,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    """Inline-edit a single field on a campaign during review.

    Only fields in the ``_EDITABLE_FIELDS`` whitelist may be modified. Each
    edit writes an ``AuditEvent`` recording the old and new values so the
    audit log serves as the version history.
    """
    if body.field not in _EDITABLE_FIELDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"field '{body.field}' is not editable",
        )

    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    coerce = _EDITABLE_FIELDS[body.field]
    try:
        new_value = coerce(body.value)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"invalid value for field '{body.field}': {exc}",
        ) from exc

    old_value = getattr(camp, body.field)
    setattr(camp, body.field, new_value)

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.edit_field",
        entity_type="campaign",
        entity_id=camp.id,
        payload={
            "field": body.field,
            "old_value": old_value,
            "new_value": new_value,
        },
    )
    # Create a version snapshot so the edit is recorded in version history.
    await _create_version(
        session,
        camp,
        author_id=user.id,
        tenant_id=user.tenant_id,
        change_summary=f"Edited {body.field}",
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


# ─── Inline comments (Google Docs-style) ──────────────────────────────────────


class CommentAuthorOut(BaseModel):
    id: uuid.UUID
    email: str


class CommentOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    campaign_id: uuid.UUID
    author_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    anchor_text: str
    body: str
    resolved: bool
    created_at: datetime
    updated_at: datetime
    author: CommentAuthorOut | None = None
    replies: list[CommentOut] = []


class CommentIn(BaseModel):
    anchor_text: str = Field(min_length=1, max_length=2000)
    body: str = Field(min_length=1, max_length=4000)
    parent_id: uuid.UUID | None = None


def _comment_to_out(c: ReviewComment, author_email: str | None = None, replies: list[CommentOut] | None = None) -> CommentOut:
    """Build a CommentOut from a ReviewComment row.

    ``author_email`` and ``replies`` are passed explicitly to avoid triggering
    lazy loads outside the async greenlet context.
    """
    author = CommentAuthorOut(id=c.author_id, email=author_email) if author_email else None
    return CommentOut(
        id=c.id,
        campaign_id=c.campaign_id,
        author_id=c.author_id,
        parent_id=c.parent_id,
        anchor_text=c.anchor_text,
        body=c.body,
        resolved=c.resolved,
        created_at=c.created_at,
        updated_at=c.updated_at,
        author=author,
        replies=replies or [],
    )


async def _load_author_emails(session: SessionDep, comments: list[ReviewComment]) -> dict[uuid.UUID, str]:
    """Batch-load author emails for a list of comments."""
    if not comments:
        return {}
    author_ids = {c.author_id for c in comments}
    res = await session.execute(select(User).where(User.id.in_(author_ids)))
    return {u.id: u.email for u in res.scalars().all()}


@router.get("/{campaign_id}/comments", response_model=list[CommentOut])
async def list_comments(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[CommentOut]:
    """List all comments (with threaded replies) for a campaign.

    Only top-level comments (``parent_id IS NULL``) are returned at the top
    level; their replies are nested via the ``replies`` field.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    # Load ALL comments for the campaign (top-level + replies) in one query,
    # then build the tree in Python. This avoids N+1 queries and lazy-load
    # issues in the async context.
    res = await session.execute(
        select(ReviewComment)
        .where(
            ReviewComment.campaign_id == campaign_id,
            ReviewComment.tenant_id == user.tenant_id,
        )
        .order_by(ReviewComment.created_at.asc())
    )
    all_comments = res.scalars().all()
    emails = await _load_author_emails(session, all_comments)

    # Group replies by parent_id.
    replies_by_parent: dict[uuid.UUID, list[CommentOut]] = {}
    for c in all_comments:
        if c.parent_id is not None:
            replies_by_parent.setdefault(c.parent_id, []).append(
                _comment_to_out(c, author_email=emails.get(c.author_id))
            )

    # Build top-level comments with their replies nested.
    return [
        _comment_to_out(
            c,
            author_email=emails.get(c.author_id),
            replies=replies_by_parent.get(c.id, []),
        )
        for c in all_comments
        if c.parent_id is None
    ]


@router.post("/{campaign_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    campaign_id: uuid.UUID,
    body: CommentIn,
    user: CurrentUser,
    session: SessionDep,
) -> CommentOut:
    """Add a comment (or reply) to a campaign.

    If ``parent_id`` is supplied the new row is a reply to that comment; the
    ``anchor_text`` is inherited from the parent for replies so the thread
    stays anchored to the same snippet.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    anchor = body.anchor_text
    if body.parent_id is not None:
        # Verify the parent exists and belongs to the same campaign/tenant.
        parent_res = await session.execute(
            select(ReviewComment).where(
                ReviewComment.id == body.parent_id,
                ReviewComment.campaign_id == campaign_id,
                ReviewComment.tenant_id == user.tenant_id,
            )
        )
        parent = parent_res.scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "parent comment not found"
            )
        # Replies inherit the parent's anchor so the thread stays coherent.
        anchor = parent.anchor_text

    comment = ReviewComment(
        tenant_id=user.tenant_id,
        campaign_id=campaign_id,
        author_id=user.id,
        parent_id=body.parent_id,
        anchor_text=anchor,
        body=body.body,
        resolved=False,
    )
    session.add(comment)
    await session.flush()

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.add_comment",
        entity_type="campaign",
        entity_id=campaign_id,
        payload={
            "comment_id": str(comment.id),
            "parent_id": str(body.parent_id) if body.parent_id else None,
            "anchor_text": anchor,
        },
    )
    # Build the response before commit — a new comment has no replies.
    out = _comment_to_out(comment, author_email=user.email, replies=[])
    await session.commit()
    return out


@router.post(
    "/{campaign_id}/comments/{comment_id}/resolve", response_model=CommentOut
)
async def resolve_comment(
    campaign_id: uuid.UUID,
    comment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CommentOut:
    """Toggle the resolved status of a comment."""
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    res = await session.execute(
        select(ReviewComment).where(
            ReviewComment.id == comment_id,
            ReviewComment.campaign_id == campaign_id,
            ReviewComment.tenant_id == user.tenant_id,
        )
    )
    comment = res.scalar_one_or_none()
    if comment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "comment not found"
        )

    comment.resolved = not comment.resolved
    await session.flush()

    # Load author email + replies explicitly (no lazy loading).
    author_res = await session.execute(select(User).where(User.id == comment.author_id))
    author = author_res.scalar_one_or_none()
    author_email = author.email if author else None

    replies_res = await session.execute(
        select(ReviewComment)
        .where(ReviewComment.parent_id == comment.id)
        .order_by(ReviewComment.created_at.asc())
    )
    reply_rows = replies_res.scalars().all()
    reply_emails = await _load_author_emails(session, reply_rows)
    reply_outs = [
        _comment_to_out(r, author_email=reply_emails.get(r.author_id))
        for r in reply_rows
    ]

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.resolve_comment" if comment.resolved else "campaign.unresolve_comment",
        entity_type="campaign",
        entity_id=campaign_id,
        payload={"comment_id": str(comment.id), "resolved": comment.resolved},
    )
    out = _comment_to_out(comment, author_email=author_email, replies=reply_outs)
    await session.commit()
    return out


# ─── Version history (Google Docs-style) ────────────────────────────────────


class VersionAuthorOut(BaseModel):
    id: uuid.UUID
    email: str


class VersionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    campaign_id: uuid.UUID
    author_id: uuid.UUID
    version_number: int
    snapshot: dict[str, Any]
    change_summary: str | None = None
    created_at: datetime
    author: VersionAuthorOut | None = None


async def _version_to_out(
    v: ReviewVersion, author_email: str | None = None
) -> VersionOut:
    author = VersionAuthorOut(id=v.author_id, email=author_email) if author_email else None
    return VersionOut(
        id=v.id,
        campaign_id=v.campaign_id,
        author_id=v.author_id,
        version_number=v.version_number,
        snapshot=v.snapshot,
        change_summary=v.change_summary,
        created_at=v.created_at,
        author=author,
    )


@router.get("/{campaign_id}/versions", response_model=list[VersionOut])
async def list_versions(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[VersionOut]:
    """List all versions for a campaign, newest first."""
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    res = await session.execute(
        select(ReviewVersion)
        .where(
            ReviewVersion.campaign_id == campaign_id,
            ReviewVersion.tenant_id == user.tenant_id,
        )
        .order_by(ReviewVersion.version_number.desc())
    )
    versions = res.scalars().all()
    author_ids = {v.author_id for v in versions}
    emails: dict[uuid.UUID, str] = {}
    if author_ids:
        ures = await session.execute(select(User).where(User.id.in_(author_ids)))
        emails = {u.id: u.email for u in ures.scalars().all()}
    return [await _version_to_out(v, author_email=emails.get(v.author_id)) for v in versions]


@router.get(
    "/{campaign_id}/versions/{version_number}", response_model=VersionOut
)
async def get_version(
    campaign_id: uuid.UUID,
    version_number: int,
    user: CurrentUser,
    session: SessionDep,
) -> VersionOut:
    """Get a specific version's snapshot."""
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    res = await session.execute(
        select(ReviewVersion).where(
            ReviewVersion.campaign_id == campaign_id,
            ReviewVersion.tenant_id == user.tenant_id,
            ReviewVersion.version_number == version_number,
        )
    )
    version = res.scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "version not found"
        )
    ares = await session.execute(select(User).where(User.id == version.author_id))
    author = ares.scalar_one_or_none()
    return await _version_to_out(
        version, author_email=author.email if author else None
    )


@router.post(
    "/{campaign_id}/versions/{version_number}/restore",
    response_model=CampaignOut,
)
async def restore_version(
    campaign_id: uuid.UUID,
    version_number: int,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignOut:
    """Restore a previous version.

    Copies the snapshot's editable fields back onto the campaign and creates a
    new ReviewVersion row recording the restore (so the restore itself appears
    in the history).
    """
    camp = await _get_tenant_campaign(session, campaign_id, user.tenant_id)
    res = await session.execute(
        select(ReviewVersion).where(
            ReviewVersion.campaign_id == campaign_id,
            ReviewVersion.tenant_id == user.tenant_id,
            ReviewVersion.version_number == version_number,
        )
    )
    version = res.scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "version not found"
        )

    snap = version.snapshot
    # Only restore the editable fields captured in the snapshot.
    for field in _EDITABLE_FIELDS:
        if field in snap:
            setattr(camp, field, snap[field])

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="campaign.restore_version",
        entity_type="campaign",
        entity_id=camp.id,
        payload={"restored_version": version_number},
    )
    await _create_version(
        session,
        camp,
        author_id=user.id,
        tenant_id=user.tenant_id,
        change_summary=f"Restored version {version_number}",
    )
    await session.commit()
    return CampaignOut.model_validate(camp)
