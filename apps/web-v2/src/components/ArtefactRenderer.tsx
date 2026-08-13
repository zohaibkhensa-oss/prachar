"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, AlertTriangle, Info, CheckCircle, XCircle, Download, Sparkles } from "lucide-react";
import { useState } from "react";

// ─── Artefact Types ─────────────────────────────────────────────────────────

export interface Artefact {
  kind: string;
  title: string;
  payload: Record<string, any>;
}

// ─── Artefact Shell (Phase G: premium wrapper) ──────────────────────────────

function ArtefactShell({
  children,
  title,
  accent = "accent",
  icon,
  exportable = true,
}: {
  children: React.ReactNode;
  title?: string;
  accent?: string;
  icon?: React.ReactNode;
  exportable?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className={cn(
        "relative rounded-2xl border border-white/[0.06] bg-gradient-to-br from-white/[0.03] to-white/[0.01]",
        "backdrop-blur-xl transition-all duration-300",
        hovered && "border-white/[0.1] shadow-lg shadow-black/20",
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {(title || icon) && (
        <div className="flex items-center gap-2 px-4 pt-3 pb-1">
          {icon && <span className={cn("text-sm", `text-${accent}`)}>{icon}</span>}
          {title && <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{title}</span>}
          {exportable && hovered && (
            <button
              className="ml-auto text-text-muted hover:text-text transition-colors"
              title="Export"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

// ─── Artefact Renderer ──────────────────────────────────────────────────────

interface ArtefactRendererProps {
  artefact: Artefact;
  onAction?: (action: string) => void;
}

/**
 * ArtefactRenderer — dispatches by artefact kind and renders the appropriate
 * rich UI component. This is the core of Phase D: Live Capability Rendering.
 *
 * Instead of streaming plain text, tools emit structured artefacts that
 * render as campaign cards, KPI widgets, images, charts, etc.
 */
export function ArtefactRenderer({ artefact, onAction }: ArtefactRendererProps) {
  const { kind, title, payload } = artefact;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="my-2"
    >
      {renderByKind(kind, title, payload, onAction)}
    </motion.div>
  );
}

function renderByKind(kind: string, title: string, payload: Record<string, any>, onAction?: (a: string) => void): React.ReactNode {
  switch (kind) {
    case "campaign_card":
      return <CampaignCard title={title} payload={payload} />;
    case "kpi_widget":
      return <KpiWidget title={title} payload={payload} />;
    case "kpi_grid":
      return <KpiGrid title={title} payload={payload} />;
    case "image":
      return <ImageArtefact title={title} payload={payload} />;
    case "image_grid":
      return <ImageGrid title={title} payload={payload} />;
    case "video_preview":
      return <VideoPreview title={title} payload={payload} />;
    case "chart":
      return <ChartArtefact title={title} payload={payload} />;
    case "budget_table":
      return <BudgetTable title={title} payload={payload} />;
    case "copy_draft":
      return <CopyDraft title={title} payload={payload} />;
    case "copy_drafts":
      return <CopyDrafts title={title} payload={payload} />;
    case "review_feedback":
      return <ReviewFeedback title={title} payload={payload} />;
    case "review_summary":
      return <ReviewSummary title={title} payload={payload} />;
    case "timeline_plan":
      return <TimelinePlan title={title} payload={payload} />;
    case "opportunity_card":
      return <OpportunityCard title={title} payload={payload} />;
    case "audience_card":
      return <AudienceCard title={title} payload={payload} />;
    case "competitor_card":
      return <CompetitorCard title={title} payload={payload} />;
    case "creative_brief":
      return <CreativeBrief title={title} payload={payload} />;
    case "media_plan":
      return <MediaPlan title={title} payload={payload} />;
    case "task_list":
      return <TaskList title={title} payload={payload} onAction={onAction} />;
    case "alert":
      return <AlertArtefact title={title} payload={payload} onAction={onAction} />;
    case "memory_insight":
      return <MemoryInsight title={title} payload={payload} />;
    // Phase L — New Capability Artefacts
    case "website_blueprint":
      return <WebsiteBlueprint title={title} payload={payload} />;
    case "page_content":
      return <PageContentArtefact title={title} payload={payload} />;
    case "seo_audit":
      return <SeoAuditArtefact title={title} payload={payload} />;
    case "keyword_grid":
      return <KeywordGridArtefact title={title} payload={payload} />;
    case "landing_page":
      return <LandingPageArtefact title={title} payload={payload} />;
    case "crm_pipeline":
      return <CrmPipelineArtefact title={title} payload={payload} />;
    case "contact_card":
      return <ContactCardArtefact title={title} payload={payload} />;
    case "email_sequence":
      return <EmailSequenceArtefact title={title} payload={payload} />;
    case "whatsapp_campaign":
      return <WhatsAppCampaignArtefact title={title} payload={payload} />;
    case "calendar_grid":
      return <CalendarGridArtefact title={title} payload={payload} />;
    case "team_board":
      return <TeamBoardArtefact title={title} payload={payload} />;
    default:
      return (
        <div className="glass rounded-xl p-3 text-xs text-text-muted">
          Unknown artefact: {kind}
        </div>
      );
  }
}

// ─── Individual Artefact Components ─────────────────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("glass rounded-xl p-4", className)}>{children}</div>;
}

function CampaignCard({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title="Campaign" icon={<Sparkles className="w-3.5 h-3.5" />} accent="accent">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-base font-display font-bold">{payload.name || title}</div>
          <div className="text-xs text-text-secondary mt-0.5">{payload.goal}</div>
        </div>
        <span className={cn(
          "text-[10px] px-2.5 py-1 rounded-full font-medium border",
          payload.status === "active" && "bg-green-500/10 text-green-400 border-green-500/20",
          payload.status === "draft" && "bg-amber-500/10 text-amber-400 border-amber-500/20",
          payload.status === "planned" && "bg-blue-500/10 text-blue-400 border-blue-500/20",
          payload.status === "in_review" && "bg-purple-500/10 text-purple-400 border-purple-500/20",
        )}>
          {payload.status}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-3">
        <div className="rounded-lg bg-white/[0.03] p-2.5">
          <div className="text-[9px] text-text-muted uppercase tracking-wider">Budget</div>
          <div className="text-sm font-semibold mt-0.5">{payload.budget}</div>
        </div>
        {payload.estimated_reach && (
          <div className="rounded-lg bg-white/[0.03] p-2.5">
            <div className="text-[9px] text-text-muted uppercase tracking-wider">Est. Reach</div>
            <div className="text-sm font-semibold mt-0.5">{payload.estimated_reach}</div>
          </div>
        )}
        {payload.expected_enquiries && (
          <div className="rounded-lg bg-white/[0.03] p-2.5">
            <div className="text-[9px] text-text-muted uppercase tracking-wider">Enquiries</div>
            <div className="text-sm font-semibold mt-0.5">{payload.expected_enquiries}</div>
          </div>
        )}
      </div>
      {payload.channels?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {payload.channels.map((ch: string) => (
            <span key={ch} className="text-[10px] px-2.5 py-1 rounded-lg bg-accent/5 text-accent border border-accent/10">
              {ch}
            </span>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function KpiWidget({ title, payload }: { title: string; payload: Record<string, any> }) {
  const trendUp = payload.trend_up !== false;
  return (
    <div className="relative rounded-xl border border-white/[0.06] bg-gradient-to-br from-white/[0.04] to-transparent p-3.5 overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-accent/0 via-accent/30 to-accent/0" />
      <div className="text-[10px] text-text-muted uppercase tracking-wider">{payload.label || title}</div>
      <div className="font-display text-2xl font-bold mt-1 bg-gradient-to-br from-text to-text-secondary bg-clip-text text-transparent">{payload.value}</div>
      {payload.trend && (
        <div className={cn("text-[11px] mt-1 flex items-center gap-1 font-medium", trendUp ? "text-success" : "text-red-400")}>
          {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {payload.trend}
        </div>
      )}
    </div>
  );
}

function KpiGrid({ title, payload }: { title: string; payload: Record<string, any> }) {
  const kpis = payload.kpis || [];
  return (
    <div>
      {title && <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">{title}</div>}
      <div className="grid grid-cols-2 gap-2">
        {kpis.map((kpi: any, i: number) => (
          <KpiWidget key={i} title={kpi.label} payload={kpi} />
        ))}
      </div>
    </div>
  );
}

function ImageArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card className="p-2">
      <img
        src={payload.url}
        alt={payload.alt || title}
        className="rounded-lg w-full max-h-64 object-cover"
        loading="lazy"
      />
      {payload.prompt && (
        <div className="text-[10px] text-text-muted mt-2 px-1 italic">"{payload.prompt}"</div>
      )}
    </Card>
  );
}

function ImageGrid({ title, payload }: { title: string; payload: Record<string, any> }) {
  const images = payload.images || [];
  return (
    <div>
      {title && <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">{title}</div>}
      <div className="grid grid-cols-2 gap-2">
        {images.map((img: any, i: number) => (
          <ImageArtefact key={i} title={img.alt || ""} payload={img} />
        ))}
      </div>
    </div>
  );
}

function VideoPreview({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card className="p-2 relative">
      <img
        src={payload.thumbnail_url}
        alt={payload.title || title}
        className="rounded-lg w-full max-h-48 object-cover"
        loading="lazy"
      />
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-12 h-12 rounded-full bg-black/50 flex items-center justify-center">
          <span className="text-white text-xl">▶</span>
        </div>
      </div>
      <div className="flex items-center justify-between mt-2 px-1">
        <span className="text-xs font-medium">{payload.title || title}</span>
        {payload.duration && <span className="text-[10px] text-text-muted">{payload.duration}</span>}
      </div>
    </Card>
  );
}

function ChartArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  const { chart_type, labels, datasets } = payload;
  // Simple bar chart rendering (for line/pie, we'd use Recharts)
  if (chart_type === "bar" && datasets?.[0]?.data) {
    const data = datasets[0].data;
    const max = Math.max(...data, 1);
    return (
      <Card>
        {title && <div className="text-xs font-semibold mb-3">{title}</div>}
        <div className="flex items-end gap-2 h-32">
          {data.map((val: number, i: number) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-gradient-to-t from-accent/40 to-accent"
                style={{ height: `${(val / max) * 100}%` }}
              />
              <span className="text-[9px] text-text-muted">{labels?.[i] || ""}</span>
            </div>
          ))}
        </div>
      </Card>
    );
  }
  // Fallback: show data as text
  return (
    <Card>
      {title && <div className="text-xs font-semibold mb-2">{title}</div>}
      <div className="text-xs text-text-secondary">Chart type: {chart_type}</div>
      <div className="text-[10px] text-text-muted mt-1">{labels?.length || 0} data points</div>
    </Card>
  );
}

function BudgetTable({ title, payload }: { title: string; payload: Record<string, any> }) {
  const rows = payload.rows || [];
  return (
    <Card>
      <div className="text-xs font-semibold mb-2">{title}</div>
      <div className="space-y-1.5">
        {rows.map((row: any, i: number) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">{row.channel || row.name}</span>
            <div className="flex items-center gap-2">
              <span className="font-medium">{row.amount || row.budget}</span>
              {row.percentage && <span className="text-text-muted text-[10px]">{row.percentage}</span>}
            </div>
          </div>
        ))}
      </div>
      {payload.total && (
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/[0.06] text-xs">
          <span className="font-semibold">Total</span>
          <span className="font-bold text-accent">{payload.total}</span>
        </div>
      )}
    </Card>
  );
}

function CopyDraft({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] px-2 py-0.5 rounded bg-accent/10 text-accent font-medium">
          {payload.platform}
        </span>
      </div>
      {payload.headline && (
        <div className="text-sm font-semibold mb-1">{payload.headline}</div>
      )}
      <div className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
        {payload.body}
      </div>
      {payload.hashtags?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {payload.hashtags.map((tag: string) => (
            <span key={tag} className="text-[10px] text-accent">{tag}</span>
          ))}
        </div>
      )}
      {payload.cta && (
        <div className="text-xs text-accent mt-2 font-medium">{payload.cta}</div>
      )}
    </Card>
  );
}

function CopyDrafts({ title, payload }: { title: string; payload: Record<string, any> }) {
  const drafts = payload.drafts || [];
  return (
    <div>
      {title && <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">{title}</div>}
      <div className="space-y-2">
        {drafts.map((draft: any, i: number) => (
          <CopyDraft key={i} title="" payload={draft} />
        ))}
      </div>
    </div>
  );
}

function ReviewFeedback({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card className="border-l-2 border-l-blue-400/30">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold">{payload.director}</span>
        {payload.score != null && (
          <span className="text-xs font-bold text-blue-400">{payload.score}/10</span>
        )}
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">{payload.opinion}</p>
      <div className="flex items-center gap-2 mt-2">
        <div className="flex-1 h-1 rounded-full bg-white/[0.06]">
          <div className="h-full rounded-full bg-blue-400" style={{ width: `${payload.confidence * 100}%` }} />
        </div>
        <span className="text-[10px] text-text-muted">{Math.round(payload.confidence * 100)}%</span>
      </div>
      {payload.risks?.length > 0 && (
        <div className="mt-2 space-y-1">
          {payload.risks.map((risk: string, i: number) => (
            <div key={i} className="text-[10px] text-orange-400">⚠ {risk}</div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ReviewSummary({ title, payload }: { title: string; payload: Record<string, any> }) {
  const approved = payload.approved;
  const score = payload.score;
  const scoreColor = score >= 8 ? "text-green-400" : score >= 6 ? "text-amber-400" : "text-red-400";
  return (
    <ArtefactShell
      title={title}
      icon={approved ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
      accent={approved ? "green-400" : "orange-400"}
    >
      <div className="flex items-center gap-4 mb-3">
        <div className="relative w-16 h-16 flex items-center justify-center">
          <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="28" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
            <circle
              cx="32" cy="32" r="28" fill="none" stroke="currentColor"
              strokeWidth="4" strokeLinecap="round"
              strokeDasharray={`${(score / 10) * 176} 176`}
              className={scoreColor}
            />
          </svg>
          <span className={cn("absolute text-lg font-bold", scoreColor)}>{score}</span>
        </div>
        <div>
          <span className={cn("text-sm font-bold", approved ? "text-green-400" : "text-orange-400")}>
            {approved ? "Approved" : "Needs Revision"}
          </span>
          {payload.consensus && (
            <p className="text-xs text-text-secondary mt-1 max-w-xs">{payload.consensus}</p>
          )}
        </div>
      </div>
      {payload.key_points?.length > 0 && (
        <ul className="space-y-1.5">
          {payload.key_points.map((point: string, i: number) => (
            <li key={i} className="text-xs text-text-secondary flex items-start gap-2">
              <span className={cn("mt-0.5", approved ? "text-green-400" : "text-orange-400")}>•</span>
              {point}
            </li>
          ))}
        </ul>
      )}
    </ArtefactShell>
  );
}

function TimelinePlan({ title, payload }: { title: string; payload: Record<string, any> }) {
  const weeks = payload.weeks || [];
  return (
    <Card>
      <div className="text-xs font-semibold mb-3">{title}</div>
      <div className="space-y-3">
        {weeks.map((week: any, i: number) => (
          <div key={i} className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center text-[10px] font-bold text-accent">
              W{i + 1}
            </div>
            <div className="flex-1">
              <div className="text-xs font-medium">{week.objective || week.title}</div>
              {week.content && <div className="text-[10px] text-text-muted mt-0.5">{week.content}</div>}
              {week.channels?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {week.channels.map((ch: string) => (
                    <span key={ch} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04] text-text-muted">{ch}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function OpportunityCard({ title, payload }: { title: string; payload: Record<string, any> }) {
  const impactColor = payload.impact === "high" ? "text-green-400" : payload.impact === "medium" ? "text-amber-400" : "text-text-muted";
  const diffColor = payload.difficulty === "easy" ? "text-green-400" : payload.difficulty === "medium" ? "text-amber-400" : "text-red-400";
  return (
    <Card className="border-l-2 border-l-accent/30">
      <div className="text-sm font-semibold mb-1">{payload.title || title}</div>
      {payload.description && <p className="text-xs text-text-secondary mb-2">{payload.description}</p>}
      <div className="flex items-center gap-3 text-[10px]">
        <span className={impactColor}>Impact: {payload.impact}</span>
        <span className={diffColor}>Difficulty: {payload.difficulty}</span>
        {payload.timeframe && <span className="text-text-muted">{payload.timeframe}</span>}
      </div>
    </Card>
  );
}

function AudienceCard({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card>
      <div className="text-xs font-semibold mb-2">{title}</div>
      {payload.demographics && (
        <div className="text-xs text-text-secondary mb-2">
          {Object.entries(payload.demographics).map(([k, v]) => `${k}: ${v}`).join(" · ")}
        </div>
      )}
      {payload.interests?.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-text-muted mb-1">Interests</div>
          <div className="flex flex-wrap gap-1">
            {payload.interests.map((interest: string) => (
              <span key={interest} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-text-secondary">{interest}</span>
            ))}
          </div>
        </div>
      )}
      {payload.behaviours?.length > 0 && (
        <div>
          <div className="text-[10px] text-text-muted mb-1">Behaviours</div>
          <div className="flex flex-wrap gap-1">
            {payload.behaviours.map((behaviour: string) => (
              <span key={behaviour} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-text-secondary">{behaviour}</span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function CompetitorCard({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold">{payload.name || title}</span>
        {payload.market_share && <span className="text-xs text-text-muted">{payload.market_share}</span>}
      </div>
      {payload.strengths?.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-green-400 mb-1">Strengths</div>
          {payload.strengths.map((s: string, i: number) => (
            <div key={i} className="text-xs text-text-secondary">+ {s}</div>
          ))}
        </div>
      )}
      {payload.weaknesses?.length > 0 && (
        <div>
          <div className="text-[10px] text-red-400 mb-1">Weaknesses</div>
          {payload.weaknesses.map((w: string, i: number) => (
            <div key={i} className="text-xs text-text-secondary">- {w}</div>
          ))}
        </div>
      )}
    </Card>
  );
}

function CreativeBrief({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card className="border-l-2 border-l-purple-400/30">
      <div className="text-xs font-semibold mb-2">{title}</div>
      <div className="text-xs text-text-secondary mb-1"><span className="text-text-muted">Concept: </span>{payload.concept}</div>
      <div className="text-xs text-text-secondary mb-1"><span className="text-text-muted">Style: </span>{payload.style}</div>
      <div className="text-xs text-text-secondary mb-2"><span className="text-text-muted">Tone: </span>{payload.tone}</div>
      {payload.colors?.length > 0 && (
        <div className="flex gap-1.5 mb-2">
          {payload.colors.map((color: string) => (
            <div key={color} className="w-5 h-5 rounded" style={{ background: color }} title={color} />
          ))}
        </div>
      )}
      {payload.references?.length > 0 && (
        <div className="text-[10px] text-text-muted">Refs: {payload.references.join(", ")}</div>
      )}
    </Card>
  );
}

function MediaPlan({ title, payload }: { title: string; payload: Record<string, any> }) {
  const channels = payload.channels || [];
  return (
    <Card>
      <div className="text-xs font-semibold mb-2">{title}</div>
      <div className="space-y-1.5">
        {channels.map((ch: any, i: number) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">{ch.channel || ch.name}</span>
            <div className="flex items-center gap-2">
              <span className="font-medium">{ch.budget || ch.amount}</span>
              {ch.percentage && <span className="text-text-muted text-[10px]">{ch.percentage}</span>}
            </div>
          </div>
        ))}
      </div>
      {payload.total_budget && (
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/[0.06] text-xs">
          <span className="font-semibold">Total</span>
          <span className="font-bold text-accent">{payload.total_budget}</span>
        </div>
      )}
    </Card>
  );
}

function TaskList({ title, payload, onAction }: { title: string; payload: Record<string, any>; onAction?: (a: string) => void }) {
  const tasks = payload.tasks || [];
  return (
    <Card>
      <div className="text-xs font-semibold mb-2">{title}</div>
      <div className="space-y-1.5">
        {tasks.map((task: any, i: number) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className={cn(
              "w-1.5 h-1.5 rounded-full",
              task.priority === "high" ? "bg-red-400" : task.priority === "medium" ? "bg-amber-400" : "bg-text-muted"
            )} />
            <span className="text-text-secondary flex-1">{task.title || task.action}</span>
            {task.action && onAction && (
              <button
                onClick={() => onAction(task.action)}
                className="text-[10px] text-accent hover:text-accent/80"
              >
                →
              </button>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function AlertArtefact({ title, payload, onAction }: { title: string; payload: Record<string, any>; onAction?: (a: string) => void }) {
  const severity = payload.severity || "info";
  const colors = {
    info: "border-l-blue-400/40 text-blue-400",
    warning: "border-l-amber-400/40 text-amber-400",
    critical: "border-l-red-400/40 text-red-400",
  };
  const icons = { info: Info, warning: AlertTriangle, critical: AlertTriangle };
  const Icon = icons[severity as keyof typeof icons] || Info;
  return (
    <Card className={cn("border-l-2", colors[severity as keyof typeof colors])}>
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <div className="text-sm font-semibold">{payload.title || title}</div>
          <p className="text-xs text-text-secondary mt-1">{payload.detail}</p>
          {payload.action && onAction && (
            <button
              onClick={() => onAction(payload.action)}
              className="text-xs text-accent mt-2 hover:text-accent/80"
            >
              {payload.action} →
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

function MemoryInsight({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <Card className="border-l-2 border-l-purple-400/30 bg-purple-400/[0.02]">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-400/10 text-purple-400 font-medium">
          🧠 {payload.category || title}
        </span>
        {payload.confidence > 0 && (
          <span className="text-[10px] text-text-muted">{Math.round(payload.confidence * 100)}% confidence</span>
        )}
      </div>
      <p className="text-xs text-text-secondary">{payload.insight}</p>
    </Card>
  );
}

// ─── Phase L — New Capability Artefact Components ───────────────────────────

function WebsiteBlueprint({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Website Blueprint"} icon="🌐">
      <div className="space-y-3">
        {payload.pages?.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pages ({payload.pages.length})</div>
            <div className="flex flex-wrap gap-1.5">
              {payload.pages.map((p: any, i: number) => (
                <span key={i} className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-text-secondary">
                  /{p.slug} — {p.title}
                </span>
              ))}
            </div>
          </div>
        )}
        {payload.design_system?.colors?.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Design System</div>
            <div className="flex items-center gap-2">
              {payload.design_system.colors.map((c: string, i: number) => (
                <div key={i} className="w-5 h-5 rounded-md border border-white/10" style={{ background: c }} title={c} />
              ))}
              <span className="text-[10px] text-text-muted">{payload.design_system.typography?.heading || ""}</span>
            </div>
          </div>
        )}
        {payload.seo_foundation?.target_keywords?.length > 0 && (
          <div>
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">SEO Keywords</div>
            <div className="flex flex-wrap gap-1">
              {payload.seo_foundation.target_keywords.slice(0, 8).map((k: string, i: number) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">{k}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </ArtefactShell>
  );
}

function PageContentArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || payload.title || "Page"} icon="📄">
      <p className="text-[11px] text-text-muted mb-2">{payload.meta_description}</p>
      {payload.headings?.length > 0 && (
        <div className="space-y-1 mb-2">
          {payload.headings.slice(0, 5).map((h: any, i: number) => (
            <div key={i} className={`text-xs ${h.level === 1 ? "font-semibold text-text" : h.level === 2 ? "font-medium text-text-secondary" : "text-text-muted"}`}>
              {"  ".repeat(h.level - 1)}{h.text}
            </div>
          ))}
        </div>
      )}
      {payload.body && <p className="text-[11px] text-text-secondary line-clamp-4">{payload.body}</p>}
      {payload.cta && <span className="inline-block mt-2 text-[10px] px-2 py-1 rounded-lg bg-accent/10 text-accent">CTA: {payload.cta}</span>}
    </ArtefactShell>
  );
}

function SeoAuditArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  const score = payload.score || 0;
  const scoreColor = score >= 80 ? "text-green-400" : score >= 50 ? "text-amber-400" : "text-red-400";
  return (
    <ArtefactShell title={title || "SEO Audit"} icon="🔍">
      <div className="flex items-center gap-3 mb-3">
        <div className={`text-2xl font-bold ${scoreColor}`}>{score}</div>
        <div className="text-[10px] text-text-muted">/ 100</div>
      </div>
      {payload.issues?.length > 0 && (
        <div className="space-y-1.5 mb-2">
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Issues ({payload.issues.length})</div>
          {payload.issues.slice(0, 5).map((issue: any, i: number) => (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className={`px-1.5 py-0.5 rounded font-medium ${
                issue.severity === "high" ? "bg-red-500/10 text-red-400" :
                issue.severity === "medium" ? "bg-amber-500/10 text-amber-400" :
                "bg-white/[0.04] text-text-muted"
              }`}>{issue.severity}</span>
              <span className="text-text-secondary">{issue.issue}</span>
            </div>
          ))}
        </div>
      )}
      {payload.passed?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {payload.passed.slice(0, 5).map((p: string, i: number) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">✓ {p}</span>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function KeywordGridArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Keyword Research"} icon="🔑">
      {payload.keywords?.length > 0 && (
        <div className="space-y-1.5">
          {payload.keywords.slice(0, 10).map((kw: any, i: number) => (
            <div key={i} className="flex items-center justify-between text-[11px] py-1 border-b border-white/[0.04] last:border-0">
              <span className="text-text-secondary">{kw.keyword}</span>
              <div className="flex items-center gap-2">
                <span className="text-text-muted">{kw.search_volume?.toLocaleString() || 0}</span>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                  kw.opportunity === "high" ? "bg-green-500/10 text-green-400" :
                  kw.opportunity === "medium" ? "bg-amber-500/10 text-amber-400" :
                  "bg-white/[0.04] text-text-muted"
                }`}>{kw.opportunity || "low"}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function LandingPageArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Landing Page"} icon="🚀">
      {payload.hero && (
        <div className="mb-3 p-3 rounded-lg bg-gradient-to-br from-accent/5 to-transparent">
          <div className="text-sm font-semibold text-text mb-1">{payload.hero.headline}</div>
          <div className="text-[11px] text-text-secondary">{payload.hero.subheadline}</div>
          {payload.hero.cta && <span className="inline-block mt-2 text-[10px] px-2 py-1 rounded-lg bg-accent/10 text-accent">{payload.hero.cta}</span>}
        </div>
      )}
      {payload.benefits?.length > 0 && (
        <div className="space-y-1.5 mb-2">
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Benefits</div>
          {payload.benefits.slice(0, 4).map((b: any, i: number) => (
            <div key={i} className="text-[11px] text-text-secondary">
              <span className="font-medium text-text">{b.title}</span> — {b.description}
            </div>
          ))}
        </div>
      )}
      {payload.variants?.length > 0 && (
        <div className="flex gap-2 mt-2">
          {payload.variants.map((v: any, i: number) => (
            <span key={i} className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-text-muted">
              A/B: {v.angle}
            </span>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function CrmPipelineArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Sales Pipeline"} icon="📊">
      {payload.stages?.length > 0 && (
        <div className="flex items-center gap-1 mb-3">
          {payload.stages.map((s: any, i: number) => (
            <div key={i} className="flex-1 text-center">
              <div className="text-[10px] text-text-muted uppercase">{s.stage}</div>
              <div className="text-sm font-semibold text-text">{s.count}</div>
              <div className="text-[9px] text-text-muted">₹{s.value?.toLocaleString() || 0}</div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-text-muted">Total: {payload.contact_count || 0} contacts</span>
        <span className="font-semibold text-text">{payload.total_value}</span>
      </div>
    </ArtefactShell>
  );
}

function ContactCardArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || payload.name || "Contact"} icon="👤">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text">{payload.name}</span>
        <span className="text-[10px] px-2 py-1 rounded-lg bg-accent/10 text-accent capitalize">{payload.stage}</span>
      </div>
      {payload.value && <div className="text-[11px] text-text-secondary mb-1">Value: <span className="font-medium text-text">{payload.value}</span></div>}
      {payload.next_action && <div className="text-[11px] text-text-muted">→ {payload.next_action}</div>}
    </ArtefactShell>
  );
}

function EmailSequenceArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Email Sequence"} icon="📧">
      {payload.target_segment && <div className="text-[11px] text-text-muted mb-2">Segment: {payload.target_segment}</div>}
      {payload.steps?.length > 0 && (
        <div className="space-y-2">
          {payload.steps.map((step: any, i: number) => (
            <div key={i} className="flex items-start gap-2">
              <div className="w-5 h-5 rounded-full bg-accent/10 text-accent text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                {step.step_number || i + 1}
              </div>
              <div className="flex-1">
                <div className="text-[11px] font-medium text-text">{step.subject_line || step.name}</div>
                <div className="text-[10px] text-text-muted">{step.send_delay} — {step.cta}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function WhatsAppCampaignArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "WhatsApp Campaign"} icon="💬">
      {payload.templates?.length > 0 && (
        <div className="space-y-2 mb-2">
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Templates</div>
          {payload.templates.slice(0, 3).map((t: any, i: number) => (
            <div key={i} className="p-2 rounded-lg bg-green-500/5 border border-green-500/10">
              <div className="text-[11px] font-medium text-text">{t.name}</div>
              <div className="text-[10px] text-text-secondary line-clamp-2">{t.message}</div>
            </div>
          ))}
        </div>
      )}
      {payload.compliance_notes && (
        <div className="text-[10px] text-amber-400/80 mt-2 p-2 rounded-lg bg-amber-500/5">
          ⚠ {payload.compliance_notes}
        </div>
      )}
    </ArtefactShell>
  );
}

function CalendarGridArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Marketing Calendar"} icon="📅">
      {payload.theme && <div className="text-[11px] text-text-muted mb-2">Theme: {payload.theme}</div>}
      {payload.weeks?.length > 0 && (
        <div className="space-y-2">
          {payload.weeks.slice(0, 6).map((w: any, i: number) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium">W{w.week_number || i + 1}</span>
              <div className="flex-1">
                <div className="text-[11px] font-medium text-text">{w.theme}</div>
                {w.content_pieces?.length > 0 && (
                  <div className="text-[10px] text-text-muted">{w.content_pieces.length} content pieces</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </ArtefactShell>
  );
}

function TeamBoardArtefact({ title, payload }: { title: string; payload: Record<string, any> }) {
  return (
    <ArtefactShell title={title || "Team Board"} icon="👥">
      {payload.members?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {payload.members.slice(0, 6).map((m: any, i: number) => (
            <span key={i} className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-text-secondary">
              {m.name} · <span className="text-text-muted">{m.role}</span>
            </span>
          ))}
        </div>
      )}
      {payload.tasks?.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Tasks ({payload.tasks.length})</div>
          {payload.tasks.slice(0, 5).map((t: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-[11px]">
              <span className={`w-1.5 h-1.5 rounded-full ${
                t.priority === "high" ? "bg-red-400" : t.priority === "medium" ? "bg-amber-400" : "bg-text-muted"
              }`} />
              <span className="text-text-secondary">{t.title}</span>
            </div>
          ))}
        </div>
      )}
      {payload.pending_approvals?.length > 0 && (
        <div className="mt-2 text-[10px] px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400">
          {payload.pending_approvals.length} pending approvals
        </div>
      )}
    </ArtefactShell>
  );
}
