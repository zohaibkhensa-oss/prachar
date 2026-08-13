"use client";

import { use, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { apiPost, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { INDUSTRY_BY_ID, CHANNEL_LABELS } from "@/lib/industries";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Zap,
  TrendingUp,
  Users,
  Store,
  Target,
  Check,
  Lightbulb,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Phase = "form" | "generating" | "result" | "error";

interface FullCampaignResponse {
  id: string;
  brand_id: string;
  name: string;
  goal: string;
  status: string;
  overall_confidence: number;
  campaign: Record<string, unknown>;
}

export default function NewCampaignPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense fallback={<div className="max-w-3xl mx-auto py-20 text-center text-text-muted">Loading…</div>}>
      <NewCampaignPageInner params={params} />
    </Suspense>
  );
}

function NewCampaignPageInner({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { brand } = useActiveBrand();
  const industry = brand?.category ? INDUSTRY_BY_ID[brand.category] : null;

  // Pre-fill from proactive recommendation (P5.5 — one-click launch).
  const prefillGoal = searchParams.get("goal");
  const prefillBudget = searchParams.get("budget");
  const prefillPracharMessage = searchParams.get("prachar_message");
  const prefillDirections = searchParams.get("directions");
  const hasPrefill = !!(prefillGoal || prefillPracharMessage);

  const [goal, setGoal] = useState<string>(prefillGoal ?? industry?.goals[0] ?? "Get more customers");
  const [budget, setBudget] = useState<number>(() => {
    if (prefillBudget) {
      const parsed = parseInt(prefillBudget.replace(/[^\d]/g, ""), 10);
      if (!isNaN(parsed)) return parsed;
    }
    return industry?.defaultBudget ?? 15000;
  });
  const [phase, setPhase] = useState<Phase>("form");
  const [result, setResult] = useState<FullCampaignResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const creativeDirections = prefillDirections
    ? prefillDirections.split("|").filter(Boolean)
    : [];

  const budgetRange = industry?.budgetRange ?? [5000, 100000];
  const channels = industry?.defaultChannels ?? ["google", "instagram"];

  async function generate() {
    setPhase("generating");
    setErrorMsg("");
    try {
      const res = await apiPost<FullCampaignResponse>("/campaign-brain/full-campaign", {
        brand_id: id,
        goal,
        budget: `₹${budget.toLocaleString("en-IN")}/month`,
        save: true,
        ...(creativeDirections.length > 0
          ? { additional_context: `Creative directions from PRACHAR AI: ${creativeDirections.join(", ")}` }
          : {}),
      });
      setResult(res);
      setPhase("result");
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setErrorMsg("You've reached your monthly AI usage limit. Contact support to upgrade.");
      } else {
        setErrorMsg("We couldn't generate your campaign right now. Please try again in a moment.");
      }
      setPhase("error");
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back */}
      <Link
        href={`/app/brands/${id}/campaigns`}
        className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to campaigns
      </Link>

      <AnimatePresence mode="wait">
        {/* ─── FORM: 1-step ─── */}
        {phase === "form" && (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="space-y-6"
          >
            <div>
              <h1 className="font-display text-3xl font-semibold text-text">
                Let's grow {brand?.name ?? "your business"}
              </h1>
              <p className="text-text-secondary mt-2 text-sm leading-relaxed">
                Tell me what you're trying to achieve. I'll look at your business and recommend the best approach — strategy, channels, ads, and posts. You review, you approve, nothing goes live without you.
              </p>
            </div>

            {/* PRACHAR AI recommendation banner (P5.5 pre-fill) */}
            {hasPrefill && prefillPracharMessage && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50"
              >
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                    <Lightbulb className="w-4 h-4 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-accent block mb-1.5">
                      PRACHAR AI's recommendation
                    </span>
                    <p className="text-sm text-text leading-relaxed">{prefillPracharMessage}</p>
                    {creativeDirections.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {creativeDirections.map((d, i) => (
                          <span
                            key={i}
                            className="text-[11px] px-2 py-1 rounded-md bg-accent/10 text-accent/90"
                          >
                            {d}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="text-[11px] text-text-muted mt-3">
                      I've pre-filled the form below based on this. Review and tweak anything you want.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Q1: What do you want to achieve? */}
            <div className="glass-strong rounded-2xl p-6">
              <label className="label-field block mb-3">What do you want to achieve?</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {(industry?.goals ?? defaultGoals()).map((g) => (
                  <button
                    key={g}
                    onClick={() => setGoal(g)}
                    className={cn(
                      "flex items-start gap-3 p-3.5 rounded-xl text-left transition-all border",
                      goal === g
                        ? "bg-accent/10 border-accent/30 text-text"
                        : "bg-white/[0.02] border-transparent text-text-secondary hover:border-white/10 hover:text-text",
                    )}
                  >
                    <div className={cn(
                      "w-5 h-5 rounded-full flex items-center justify-center shrink-0 border mt-0.5",
                      goal === g ? "bg-accent border-accent" : "border-white/20",
                    )}>
                      {goal === g && <Check className="w-3 h-3 text-text" />}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{g}</div>
                      <div className="text-[11px] text-text-muted mt-0.5 leading-snug">
                        {goalReasoning(g)}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Q2: Budget */}
            <div className="glass-strong rounded-2xl p-6">
              <label className="label-field block mb-3">How much can you spend each month?</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={budgetRange[0]}
                  max={budgetRange[1]}
                  step={1000}
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                  className="flex-1 accent-yellow"
                />
                <div className="text-right shrink-0">
                  <div className="font-display text-2xl font-semibold text-text tabular-nums">
                    ₹{budget.toLocaleString("en-IN")}
                  </div>
                  <div className="text-[11px] text-text-muted">per month</div>
                </div>
              </div>
              <div className="flex items-center justify-between mt-2 text-[11px] text-text-muted">
                <span>₹{budgetRange[0].toLocaleString("en-IN")}</span>
                <span>₹{budgetRange[1].toLocaleString("en-IN")}</span>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider text-accent/80 shrink-0">
                  {budgetHint(budget).label}
                </span>
                <span className="text-[11px] text-text-muted leading-relaxed">
                  {budgetHint(budget).detail}
                </span>
              </div>
              <p className="text-[11px] text-text-muted mt-2 leading-relaxed">
                That's about ₹{Math.round(budget / 30).toLocaleString("en-IN")}/day. You can change this anytime.
              </p>
            </div>

            {/* What we'll do — preview */}
            <div className="glass rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-accent" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent">Here's what we'll do</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <PreviewItem icon={<Target className="w-3.5 h-3.5" />} text="Build your strategy" />
                <PreviewItem icon={<Zap className="w-3.5 h-3.5" />} text="Write your ads & posts" />
                <PreviewItem icon={<Users className="w-3.5 h-3.5" />} text={`Promote on ${channels.map((c) => CHANNEL_LABELS[c] ?? c).join(", ")}`} />
              </div>
            </div>

            {/* CTA */}
            <button onClick={generate} className="btn-primary w-full group text-base">
              <Sparkles className="w-5 h-5" />
              Build my campaign
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <p className="text-[11px] text-text-muted text-center">
              Takes ~30 seconds · You approve everything before it goes live
            </p>
          </motion.div>
        )}

        {/* ─── GENERATING: progress ─── */}
        {phase === "generating" && (
          <motion.div
            key="generating"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="glass-strong rounded-2xl p-10 text-center"
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="w-12 h-12 rounded-full border border-accent/20 border-t-accent mx-auto mb-6"
            />
            <h2 className="font-display text-xl font-semibold text-text mb-2">
              Building your campaign…
            </h2>
            <p className="text-sm text-text-secondary mb-8 max-w-sm mx-auto">
              I'm analysing {industryLabelLower(industry)} trends, choosing your channels, and writing your ad copy for {brand?.name ?? "your business"}.
            </p>

            <div className="max-w-xs mx-auto space-y-3 text-left">
              {[
                { label: `Analysing ${industryLabelLower(industry)} trends`, delay: 0 },
                { label: "Choosing channels based on your audience", delay: 0.6 },
                { label: "Writing your ad copy", delay: 1.2 },
                { label: "Setting your budget split", delay: 1.8 },
                { label: "Preparing your campaign", delay: 2.4 },
              ].map((item, i) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: item.delay, duration: 0.4 }}
                  className="flex items-center gap-3"
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: item.delay + 0.3, type: "spring", stiffness: 300 }}
                    className="w-5 h-5 rounded-full bg-success/20 flex items-center justify-center shrink-0"
                  >
                    <Check className="w-3 h-3 text-success" />
                  </motion.div>
                  <span className="text-sm text-text-secondary">{item.label}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ─── ERROR ─── */}
        {phase === "error" && (
          <motion.div
            key="error"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-strong rounded-2xl p-10 text-center"
          >
            <h2 className="font-display text-xl font-semibold text-text mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-text-secondary mb-6">{errorMsg}</p>
            <button onClick={() => setPhase("form")} className="btn-primary">
              Try again
            </button>
          </motion.div>
        )}

        {/* ─── RESULT ─── */}
        {phase === "result" && result && (
          <CampaignResult
            result={result}
            brandId={id}
            onApprove={() => router.push(`/app/brands/${id}/campaigns` as Route)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Campaign result presentation ──────────────────────────────────────────


function CampaignResult({
  result,
  brandId,
  onApprove,
}: {
  result: FullCampaignResponse;
  brandId: string;
  onApprove: () => void;
}) {
  const campaign = result.campaign as Record<string, unknown>;
  const strategy = (campaign.campaign_strategy ?? campaign.strategy ?? {}) as Record<string, unknown>;
  const mediaPlan = (campaign.media_plan ?? {}) as Record<string, unknown>;
  const creativeDirection = (campaign.creative_direction ?? {}) as Record<string, unknown>;
  const budgetIntel = (campaign.budget_intelligence ?? campaign.budget ?? {}) as Record<string, unknown>;

  const coreMessage = String(strategy.core_message ?? strategy.primary_message ?? "");
  const targetAudience = String(strategy.target_audience ?? strategy.audience ?? "");
  const recommendedChannels = Array.isArray(mediaPlan.recommended_channels)
    ? (mediaPlan.recommended_channels as string[])
    : Array.isArray(mediaPlan.channels)
      ? (mediaPlan.channels as string[])
      : [];
  const channelBreakdown = (mediaPlan.channel_breakdown ?? mediaPlan.channel_allocation ?? {}) as Record<string, unknown>;
  const creativeConcept = String(creativeDirection.creative_concept ?? creativeDirection.concept ?? "");
  const tone = String(creativeDirection.tone ?? creativeDirection.voice ?? "");
  const budgetAllocation = (budgetIntel.allocation ?? budgetIntel.budget_breakdown ?? {}) as Record<string, unknown>;
  const expectedOutcome = String(strategy.expected_outcome ?? strategy.expected_result ?? "");

  return (
    <motion.div
      key="result"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="glass-strong rounded-2xl p-6 border-l-2 border-l-success/50">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-lg bg-success/20 flex items-center justify-center">
            <Check className="w-4 h-4 text-success" />
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider text-success">Your campaign is ready</span>
        </div>
        <h1 className="font-display text-2xl font-semibold text-text">{result.name}</h1>
        <p className="text-sm text-text-secondary mt-1">{result.goal}</p>
      </div>

      {/* Executive Summary */}
      <Section title="Executive Summary" icon={<Sparkles className="w-4 h-4 text-accent" />}>
        <p className="text-sm text-text leading-relaxed">
          {coreMessage || "Your campaign is built around a clear, compelling message that speaks directly to your target customers."}
        </p>
        {targetAudience && (
          <div className="mt-4 pt-4 border-t border-white/[0.04]">
            <span className="label-field block mb-1">Who we're targeting</span>
            <p className="text-sm text-text-secondary">{targetAudience}</p>
          </div>
        )}
        {expectedOutcome && (
          <div className="mt-4 pt-4 border-t border-white/[0.04]">
            <span className="label-field block mb-1">Expected outcome</span>
            <p className="text-sm text-text-secondary">{expectedOutcome}</p>
          </div>
        )}
      </Section>

      {/* Why this strategy */}
      <Section title="Why we chose this strategy" icon={<TrendingUp className="w-4 h-4 text-info" />}>
        <ul className="space-y-2.5">
          {recommendedChannels.slice(0, 3).map((ch) => (
            <li key={ch} className="flex items-start gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0" />
              <span className="text-sm text-text-secondary">
                <span className="text-text font-medium">{CHANNEL_LABELS[ch] ?? ch}</span> reaches your audience where they already spend time
              </span>
            </li>
          ))}
          {creativeConcept && (
            <li className="flex items-start gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0" />
              <span className="text-sm text-text-secondary">
                <span className="text-text font-medium">Creative angle:</span> {creativeConcept}
              </span>
            </li>
          )}
          {tone && (
            <li className="flex items-start gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0" />
              <span className="text-sm text-text-secondary">
                <span className="text-text font-medium">Tone:</span> {tone}
              </span>
            </li>
          )}
        </ul>
      </Section>

      {/* Budget breakdown */}
      {Object.keys(budgetAllocation).length > 0 && (
        <Section title="Where your budget goes" icon={<Store className="w-4 h-4 text-success" />}>
          <div className="space-y-2">
            {Object.entries(budgetAllocation).slice(0, 5).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02]">
                <span className="text-sm text-text-secondary">{CHANNEL_LABELS[key] ?? key}</span>
                <span className="font-mono text-sm text-text">{formatBudget(val)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Channel breakdown */}
      {Object.keys(channelBreakdown).length > 0 && (
        <Section title="What we'll post on each channel" icon={<Users className="w-4 h-4 text-warning" />}>
          <div className="space-y-3">
            {Object.entries(channelBreakdown).slice(0, 4).map(([ch, detail]) => (
              <div key={ch} className="p-3 rounded-lg bg-white/[0.02]">
                <div className="text-sm text-text font-medium mb-1">{CHANNEL_LABELS[ch] ?? ch}</div>
                <div className="text-xs text-text-muted">{typeof detail === "string" ? detail : JSON.stringify(detail)}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Next recommended actions */}
      <Section title="What happens next" icon={<ArrowRight className="w-4 h-4 text-accent" />}>
        <ol className="space-y-3">
          {[
            "Review the campaign above — tweak anything you want",
            "Approve to start reaching customers",
            "We'll publish across your channels automatically",
            "You'll see results on your dashboard within a few days",
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center shrink-0 font-mono text-xs text-accent">
                {i + 1}
              </div>
              <span className="text-sm text-text-secondary pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </Section>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3 sticky bottom-4 z-10">
        <button onClick={onApprove} className="btn-primary flex-1 group text-base">
          <Check className="w-5 h-5" />
          Approve & launch
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
        <Link
          href={`/app/brands/${brandId}/campaigns`}
          className="btn-secondary text-base"
        >
          Review later
        </Link>
      </div>
    </motion.div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────


function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h2 className="font-display text-base font-semibold text-text">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function PreviewItem({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.02]">
      <span className="text-accent shrink-0">{icon}</span>
      <span className="text-xs text-text-secondary">{text}</span>
    </div>
  );
}

function defaultGoals(): string[] {
  return [
    "Get more customers",
    "Promote a new product or service",
    "Build my brand awareness",
    "Get more enquiries and leads",
  ];
}

/**
 * Consultant-style reasoning for each goal option.
 * Explains WHY a goal is a good choice, not just what it is.
 */
const GOAL_REASONING: Record<string, string> = {
  // Default goals
  "Get more customers": "Best for growing businesses — focuses on reaching new people",
  "Promote a new product or service": "Best for launches — focuses on creating buzz and awareness",
  "Build my brand awareness": "Best for new businesses — focuses on getting your name out",
  "Get more enquiries and leads": "Best for service businesses — focuses on generating leads",
  // Restaurant
  "Get more customers walking in": "Best for filling tables — focuses on reaching hungry locals",
  "Promote my menu & specials": "Best for showcasing food — focuses on tempting your audience",
  "Build a loyal customer base": "Best for long-term growth — focuses on repeat visits",
  "Get more table reservations": "Best for busy nights — focuses on driving bookings",
  // Clinic
  "Get more patient appointments": "Best for growing your practice — focuses on reaching new patients",
  "Build trust in my community": "Best for new clinics — focuses on establishing credibility",
  "Get more walk-ins": "Best for immediate capacity — focuses on local visibility",
  // Retail
  "Get more foot traffic": "Best for growing stores — focuses on reaching local shoppers",
  "Promote my products": "Best for showcasing inventory — focuses on driving purchases",
  "Clear out old stock": "Best for inventory turnover — focuses on clearance sales",
  // Real estate
  "Get more property enquiries": "Best for closing deals — focuses on generating qualified leads",
  "Showcase my listings": "Best for visual appeal — focuses on property showcase",
  "Build my brand as an agent": "Best for new agents — focuses on establishing your name",
  "Get more site visits": "Best for serious buyers — focuses on driving in-person viewings",
  // Education
  "Get more student enrolments": "Best for growing admissions — focuses on reaching parents and students",
  "Promote my courses": "Best for showcasing curriculum — focuses on course awareness",
  "Build my institute's reputation": "Best for new institutes — focuses on establishing credibility",
  "Get more demo class signups": "Best for trial conversion — focuses on getting students in the door",
  // Gym
  "Get more memberships": "Best for growing your gym — focuses on reaching fitness-minded locals",
  "Promote my classes": "Best for filling sessions — focuses on class awareness",
  "Build a fitness community": "Best for long-term retention — focuses on member engagement",
  "Get more trial sessions": "Best for conversion — focuses on getting people in the door",
  // Salon
  "Get more appointments": "Best for filling your calendar — focuses on reaching local clients",
  "Showcase my work": "Best for visual appeal — focuses on portfolio showcase",
  "Build a loyal client base": "Best for long-term growth — focuses on repeat bookings",
  // Hotel
  "Get more bookings": "Best for filling rooms — focuses on reaching travellers",
  "Showcase my property": "Best for visual appeal — focuses on property showcase",
  "Build my hotel's reputation": "Best for new hotels — focuses on establishing credibility",
  "Get more direct reservations": "Best for reducing OTA fees — focuses on direct bookings",
  // Professional
  "Get more client enquiries": "Best for growing your practice — focuses on generating qualified leads",
  "Build my professional brand": "Best for new consultants — focuses on establishing authority",
  "Get more leads": "Best for service businesses — focuses on lead generation",
  "Establish thought leadership": "Best for credibility — focuses on content and authority",
};

function goalReasoning(goal: string): string {
  if (GOAL_REASONING[goal]) return GOAL_REASONING[goal];
  // Keyword-based fallback for any goal not explicitly mapped
  const g = goal.toLowerCase();
  if (g.includes("loyal") || g.includes("community")) return "Best for long-term growth — focuses on repeat business";
  if (g.includes("enquir") || g.includes("lead") || g.includes("appointment") || g.includes("reservation") || g.includes("booking") || g.includes("signup") || g.includes("visit")) return "Best for generating leads — focuses on getting people to contact you";
  if (g.includes("brand") || g.includes("reputation") || g.includes("trust") || g.includes("awareness")) return "Best for new businesses — focuses on getting your name out";
  if (g.includes("promote") || g.includes("showcase")) return "Best for highlighting offerings — focuses on what you sell";
  if (g.includes("customer") || g.includes("traffic") || g.includes("walking") || g.includes("membership")) return "Best for growing businesses — focuses on reaching new people";
  return "Focuses on the best outcome for your business";
}

/**
 * Contextual budget hint shown as the slider moves.
 * Tells the user what their budget level actually gets them.
 */
function budgetHint(budget: number): { label: string; detail: string } {
  if (budget < 10000) return { label: "Lean start", detail: "1-2 channels, organic focus" };
  if (budget < 25000) return { label: "Balanced", detail: "2 channels, small paid boost" };
  if (budget < 60000) return { label: "Aggressive", detail: "3 channels, significant paid spend" };
  return { label: "Scale", detail: "all channels, dominant local presence" };
}

/**
 * Lowercased industry label for natural inline use in sentences,
 * e.g. "Analysing restaurant trends".
 */
function industryLabelLower(industry: { label: string } | null | undefined): string {
  return industry?.label.toLowerCase() ?? "your industry";
}

function formatBudget(val: unknown): string {
  if (typeof val === "number") return `₹${val.toLocaleString("en-IN")}`;
  if (typeof val === "string") return val;
  if (val && typeof val === "object") {
    const obj = val as Record<string, unknown>;
    const amount = obj.amount ?? obj.budget ?? obj.monthly ?? obj.value;
    if (typeof amount === "number") return `₹${amount.toLocaleString("en-IN")}`;
    if (typeof amount === "string") return amount;
  }
  return "—";
}
