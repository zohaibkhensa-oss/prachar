"""Artefact Events — structured UI components streamed from tools.

Phase D / Step 3: Instead of streaming plain text, tools emit artefact events
with structured payloads. The frontend renders these as rich UI components:
campaign cards, KPI widgets, images, charts, copy drafts, review feedback.

An artefact event is a regular AIEvent with:
- type: "artefact.<kind>" (e.g. "artefact.campaign_card", "artefact.image")
- data.artefact: { kind, title, payload }

The frontend ArtefactRenderer dispatches by kind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ─── Artefact Kinds ─────────────────────────────────────────────────────────

ArtefactKind = Literal[
    "campaign_card",      # campaign summary with goal, budget, channels, status
    "kpi_widget",         # single KPI: label, value, trend, sparkline data
    "kpi_grid",           # grid of KPI widgets
    "image",              # generated image: url, alt, prompt
    "image_grid",         # multiple images
    "video_preview",      # video: thumbnail, duration, url
    "chart",              # chart: type (line/bar/pie), labels, datasets
    "budget_table",       # budget breakdown: rows of channel/amount/percentage
    "copy_draft",         # text content: platform, headline, body, hashtags
    "copy_drafts",        # multiple copy drafts
    "review_feedback",    # council review: director, opinion, score
    "review_summary",     # council consensus: approved, score, key points
    "timeline_plan",      # 30-day plan: weeks with objectives/content/channels
    "opportunity_card",   # growth opportunity: title, impact, difficulty
    "audience_card",      # audience profile: demographics, interests, behaviours
    "competitor_card",    # competitor: name, strengths, weaknesses, market_share
    "creative_brief",     # creative direction: concept, style, tone, references
    "media_plan",         # media plan: channels, budget split, schedule
    "task_list",          # next actions: list of tasks with priority
    "alert",              # proactive alert: severity, title, detail, action
    "memory_insight",     # learning: category, insight, confidence
    "progress_bar",       # progress: label, current, total
    # Phase L — New Capabilities
    "website_blueprint",  # website structure: pages, navigation, sections
    "page_content",       # web page: title, meta, headings, body, CTA
    "seo_audit",          # SEO audit: score, issues, recommendations
    "keyword_grid",       # keyword research: keyword, volume, difficulty, intent
    "landing_page",       # landing page: hero, benefits, proof, CTA, variants
    "crm_pipeline",       # CRM pipeline: stages, contacts, values
    "contact_card",       # CRM contact: name, stage, value, next action
    "email_sequence",     # email sequence: steps, subjects, bodies, timing
    "whatsapp_campaign",  # WhatsApp campaign: templates, segments, schedule
    "calendar_grid",      # marketing calendar: weeks, content, channels
    "team_board",         # team board: members, roles, tasks, approvals
]


# ─── Artefact ───────────────────────────────────────────────────────────────


@dataclass
class Artefact:
    """A structured UI component emitted by a tool.

    The frontend renders this as a rich component instead of plain text.
    """

    kind: ArtefactKind
    title: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artefact":
        return cls(
            kind=data.get("kind", "alert"),
            title=data.get("title", ""),
            payload=data.get("payload", {}),
        )


# ─── Artefact Factories ─────────────────────────────────────────────────────


def campaign_card(
    name: str,
    goal: str,
    budget: str,
    channels: list[str],
    status: str = "draft",
    estimated_reach: str = "",
    expected_enquiries: str = "",
) -> Artefact:
    """Create a campaign card artefact."""
    return Artefact(
        kind="campaign_card",
        title=name,
        payload={
            "name": name,
            "goal": goal,
            "budget": budget,
            "channels": channels,
            "status": status,
            "estimated_reach": estimated_reach,
            "expected_enquiries": expected_enquiries,
        },
    )


def kpi_widget(
    label: str,
    value: str | int | float,
    trend: str = "",
    trend_up: bool = True,
    sparkline: list[float] | None = None,
) -> Artefact:
    """Create a single KPI widget."""
    return Artefact(
        kind="kpi_widget",
        title=label,
        payload={
            "label": label,
            "value": value,
            "trend": trend,
            "trend_up": trend_up,
            "sparkline": sparkline or [],
        },
    )


def kpi_grid(kpis: list[dict[str, Any]]) -> Artefact:
    """Create a grid of KPI widgets."""
    return Artefact(
        kind="kpi_grid",
        title="Performance Overview",
        payload={"kpis": kpis},
    )


def image_artefact(
    url: str,
    alt: str = "",
    prompt: str = "",
    width: int = 0,
    height: int = 0,
) -> Artefact:
    """Create an image artefact."""
    return Artefact(
        kind="image",
        title=alt,
        payload={
            "url": url,
            "alt": alt,
            "prompt": prompt,
            "width": width,
            "height": height,
        },
    )


def image_grid(images: list[dict[str, Any]]) -> Artefact:
    """Create a grid of images."""
    return Artefact(
        kind="image_grid",
        title="Generated Images",
        payload={"images": images},
    )


def video_preview(
    thumbnail_url: str,
    duration: str = "",
    url: str = "",
    title: str = "",
) -> Artefact:
    """Create a video preview artefact."""
    return Artefact(
        kind="video_preview",
        title=title,
        payload={
            "thumbnail_url": thumbnail_url,
            "duration": duration,
            "url": url,
            "title": title,
        },
    )


def chart(
    chart_type: str,  # "line", "bar", "pie", "area"
    labels: list[str],
    datasets: list[dict[str, Any]],
    title: str = "",
) -> Artefact:
    """Create a chart artefact."""
    return Artefact(
        kind="chart",
        title=title,
        payload={
            "chart_type": chart_type,
            "labels": labels,
            "datasets": datasets,
        },
    )


def budget_table(
    rows: list[dict[str, Any]],
    total: str = "",
    title: str = "Budget Breakdown",
) -> Artefact:
    """Create a budget table artefact."""
    return Artefact(
        kind="budget_table",
        title=title,
        payload={"rows": rows, "total": total},
    )


def copy_draft(
    platform: str,
    headline: str,
    body: str,
    hashtags: list[str] | None = None,
    cta: str = "",
) -> Artefact:
    """Create a copy draft artefact."""
    return Artefact(
        kind="copy_draft",
        title=f"{platform} Post",
        payload={
            "platform": platform,
            "headline": headline,
            "body": body,
            "hashtags": hashtags or [],
            "cta": cta,
        },
    )


def copy_drafts(drafts: list[dict[str, Any]]) -> Artefact:
    """Create multiple copy drafts."""
    return Artefact(
        kind="copy_drafts",
        title="Copy Variations",
        payload={"drafts": drafts},
    )


def review_feedback(
    director: str,
    opinion: str,
    confidence: float,
    score: float | None = None,
    risks: list[str] | None = None,
) -> Artefact:
    """Create a review feedback artefact (from Agency Council)."""
    return Artefact(
        kind="review_feedback",
        title=f"{director} Review",
        payload={
            "director": director,
            "opinion": opinion,
            "confidence": confidence,
            "score": score,
            "risks": risks or [],
        },
    )


def review_summary(
    approved: bool,
    score: float,
    key_points: list[str],
    consensus: str = "",
) -> Artefact:
    """Create a review summary artefact (from Consensus Engine)."""
    return Artefact(
        kind="review_summary",
        title="Council Consensus",
        payload={
            "approved": approved,
            "score": score,
            "key_points": key_points,
            "consensus": consensus,
        },
    )


def timeline_plan(weeks: list[dict[str, Any]]) -> Artefact:
    """Create a 30-day plan timeline artefact."""
    return Artefact(
        kind="timeline_plan",
        title="30-Day Plan",
        payload={"weeks": weeks},
    )


def opportunity_card(
    title: str,
    impact: str,
    difficulty: str,
    timeframe: str = "",
    description: str = "",
) -> Artefact:
    """Create a growth opportunity card."""
    return Artefact(
        kind="opportunity_card",
        title=title,
        payload={
            "title": title,
            "impact": impact,
            "difficulty": difficulty,
            "timeframe": timeframe,
            "description": description,
        },
    )


def audience_card(
    demographics: dict[str, Any],
    interests: list[str],
    behaviours: list[str],
    platforms: list[str] | None = None,
) -> Artefact:
    """Create an audience profile card."""
    return Artefact(
        kind="audience_card",
        title="Target Audience",
        payload={
            "demographics": demographics,
            "interests": interests,
            "behaviours": behaviours,
            "platforms": platforms or [],
        },
    )


def competitor_card(
    name: str,
    strengths: list[str],
    weaknesses: list[str],
    market_share: str = "",
    url: str = "",
) -> Artefact:
    """Create a competitor card."""
    return Artefact(
        kind="competitor_card",
        title=name,
        payload={
            "name": name,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "market_share": market_share,
            "url": url,
        },
    )


def creative_brief(
    concept: str,
    style: str,
    tone: str,
    references: list[str] | None = None,
    colors: list[str] | None = None,
) -> Artefact:
    """Create a creative brief artefact."""
    return Artefact(
        kind="creative_brief",
        title="Creative Direction",
        payload={
            "concept": concept,
            "style": style,
            "tone": tone,
            "references": references or [],
            "colors": colors or [],
        },
    )


def media_plan(
    channels: list[dict[str, Any]],
    total_budget: str = "",
    schedule: str = "",
) -> Artefact:
    """Create a media plan artefact."""
    return Artefact(
        kind="media_plan",
        title="Media Plan",
        payload={
            "channels": channels,
            "total_budget": total_budget,
            "schedule": schedule,
        },
    )


def task_list(tasks: list[dict[str, Any]]) -> Artefact:
    """Create a task list artefact (next actions)."""
    return Artefact(
        kind="task_list",
        title="Next Actions",
        payload={"tasks": tasks},
    )


def alert(
    severity: str,  # "info", "warning", "critical"
    title: str,
    detail: str,
    action: str = "",
) -> Artefact:
    """Create a proactive alert artefact."""
    return Artefact(
        kind="alert",
        title=title,
        payload={
            "severity": severity,
            "title": title,
            "detail": detail,
            "action": action,
        },
    )


def memory_insight(
    category: str,
    insight: str,
    confidence: float = 0.0,
    source: str = "",
) -> Artefact:
    """Create a memory insight artefact."""
    return Artefact(
        kind="memory_insight",
        title=category,
        payload={
            "category": category,
            "insight": insight,
            "confidence": confidence,
            "source": source,
        },
    )


# ─── Phase L — New Capability Artefacts ─────────────────────────────────────


def website_blueprint(
    pages: list[dict[str, Any]],
    navigation: list[dict[str, Any]],
    design_system: dict[str, Any],
    seo_foundation: dict[str, Any],
) -> Artefact:
    """Create a website blueprint artefact."""
    return Artefact(
        kind="website_blueprint",
        title="Website Blueprint",
        payload={
            "pages": pages,
            "navigation": navigation,
            "design_system": design_system,
            "seo_foundation": seo_foundation,
        },
    )


def page_content(
    title: str,
    meta_description: str,
    headings: list[dict[str, Any]],
    body: str,
    cta: str = "",
    seo_keywords: list[str] | None = None,
) -> Artefact:
    """Create a web page content artefact."""
    return Artefact(
        kind="page_content",
        title=title,
        payload={
            "title": title,
            "meta_description": meta_description,
            "headings": headings,
            "body": body,
            "cta": cta,
            "seo_keywords": seo_keywords or [],
        },
    )


def seo_audit(
    score: int,
    issues: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    passed: list[str] | None = None,
) -> Artefact:
    """Create an SEO audit artefact."""
    return Artefact(
        kind="seo_audit",
        title="SEO Audit",
        payload={
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "passed": passed or [],
        },
    )


def keyword_grid(
    keywords: list[dict[str, Any]],
    total_volume: int = 0,
) -> Artefact:
    """Create a keyword research grid artefact."""
    return Artefact(
        kind="keyword_grid",
        title="Keyword Research",
        payload={
            "keywords": keywords,
            "total_volume": total_volume,
        },
    )


def landing_page(
    hero: dict[str, Any],
    benefits: list[dict[str, Any]],
    social_proof: list[dict[str, Any]],
    cta: str,
    variants: list[dict[str, Any]] | None = None,
) -> Artefact:
    """Create a landing page artefact."""
    return Artefact(
        kind="landing_page",
        title="Landing Page",
        payload={
            "hero": hero,
            "benefits": benefits,
            "social_proof": social_proof,
            "cta": cta,
            "variants": variants or [],
        },
    )


def crm_pipeline(
    stages: list[dict[str, Any]],
    total_value: str = "",
    contact_count: int = 0,
) -> Artefact:
    """Create a CRM pipeline artefact."""
    return Artefact(
        kind="crm_pipeline",
        title="Sales Pipeline",
        payload={
            "stages": stages,
            "total_value": total_value,
            "contact_count": contact_count,
        },
    )


def contact_card(
    name: str,
    stage: str,
    value: str = "",
    next_action: str = "",
    last_contact: str = "",
    email: str = "",
    phone: str = "",
) -> Artefact:
    """Create a CRM contact card artefact."""
    return Artefact(
        kind="contact_card",
        title=name,
        payload={
            "name": name,
            "stage": stage,
            "value": value,
            "next_action": next_action,
            "last_contact": last_contact,
            "email": email,
            "phone": phone,
        },
    )


def email_sequence(
    steps: list[dict[str, Any]],
    total_duration: str = "",
    target_segment: str = "",
) -> Artefact:
    """Create an email sequence artefact."""
    return Artefact(
        kind="email_sequence",
        title="Email Sequence",
        payload={
            "steps": steps,
            "total_duration": total_duration,
            "target_segment": target_segment,
        },
    )


def whatsapp_campaign(
    templates: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    schedule: str = "",
    compliance_notes: str = "",
) -> Artefact:
    """Create a WhatsApp campaign artefact."""
    return Artefact(
        kind="whatsapp_campaign",
        title="WhatsApp Campaign",
        payload={
            "templates": templates,
            "segments": segments,
            "schedule": schedule,
            "compliance_notes": compliance_notes,
        },
    )


def calendar_grid(
    weeks: list[dict[str, Any]],
    theme: str = "",
) -> Artefact:
    """Create a marketing calendar artefact."""
    return Artefact(
        kind="calendar_grid",
        title="Marketing Calendar",
        payload={
            "weeks": weeks,
            "theme": theme,
        },
    )


def team_board(
    members: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    pending_approvals: list[dict[str, Any]] | None = None,
) -> Artefact:
    """Create a team board artefact."""
    return Artefact(
        kind="team_board",
        title="Team Board",
        payload={
            "members": members,
            "tasks": tasks,
            "pending_approvals": pending_approvals or [],
        },
    )
