"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Plus,
  Megaphone,
  ArrowRight,
  Sparkles,
  Clock,
  CheckCircle2,
  TrendingUp,
  Target,
  Zap,
} from "lucide-react";
import { useActiveBrand, useCampaignPlans, type CampaignPlan } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function CampaignsPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const active = plans?.filter((p) => p.status === "active" || p.status === "approved") ?? [];
  const pending = plans?.filter((p) => p.status === "pending" || p.status === "draft") ?? [];
  const past =
    plans?.filter((p) => !active.includes(p) && !pending.includes(p)) ?? [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to start running campaigns.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  const isEmpty = !plans || plans.length === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Campaigns</h1>
          <p className="text-sm text-text-secondary mt-1">
            {isEmpty
              ? "Let's create your first campaign"
              : `${active.length} running · ${pending.length} need your review`}
          </p>
        </div>
        <Link href={`/app/brands/${brand.id}/campaigns/new`} className="btn-primary group">
          <Plus className="w-4 h-4" />
          New campaign
        </Link>
      </div>

      {/* ─── Beautiful empty state ─── */}
      {isEmpty && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="glass-strong rounded-2xl p-10 lg:p-14 text-center max-w-2xl mx-auto"
        >
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
            className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/20 to-orange-500/10 flex items-center justify-center mx-auto mb-5 glow-ring"
          >
            <Megaphone className="w-7 h-7 text-accent" />
          </motion.div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            Your first campaign is one click away
          </h2>
          <p className="text-sm text-text-secondary leading-relaxed max-w-md mx-auto mb-6">
            Tell PRACHAR AI what you want to achieve. I&apos;ll build the strategy, pick the right
            channels, write the ads, and schedule the posts — you just review and approve.
          </p>
          <div className="flex flex-wrap gap-3 justify-center mb-6">
            {[
              { icon: Target, label: "AI strategy" },
              { icon: Zap, label: "Auto-generated ads" },
              { icon: CheckCircle2, label: "You approve everything" },
            ].map((f) => (
              <span
                key={f.label}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-xs text-text-secondary"
              >
                <f.icon className="w-3.5 h-3.5 text-accent/70" />
                {f.label}
              </span>
            ))}
          </div>
          <Link
            href={`/app/brands/${brand.id}/campaigns/new`}
            className="btn-primary inline-flex group"
          >
            <Sparkles className="w-4 h-4" />
            Create your first campaign
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      )}

      {/* Needs your attention */}
      {!isEmpty && pending.length > 0 && (
        <div className="glass-strong rounded-2xl p-6 border-l-2 border-l-warning/50">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-warning" />
            <h2 className="font-display text-base font-semibold text-text">Waiting for your approval</h2>
          </div>
          <div className="space-y-2">
            {pending.map((plan) => (
              <CampaignRow key={plan.id} plan={plan} brandId={brand.id} variant="pending" />
            ))}
          </div>
        </div>
      )}

      {/* Running campaigns */}
      {!isEmpty && (
        <div className="glass-strong rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <h2 className="font-display text-base font-semibold text-text">Running now</h2>
          </div>
          {active.length > 0 ? (
            <div className="space-y-2">
              {active.map((plan) => (
                <CampaignRow key={plan.id} plan={plan} brandId={brand.id} variant="active" />
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <p className="text-sm text-text-secondary mb-3">No campaigns running yet.</p>
              <Link
                href={`/app/brands/${brand.id}/campaigns/new`}
                className="btn-primary inline-flex group"
              >
                <Sparkles className="w-4 h-4" />
                Create a campaign
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Past campaigns */}
      {!isEmpty && past.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-text-muted" />
            <h2 className="font-display text-base font-semibold text-text">Past campaigns</h2>
          </div>
          <div className="space-y-2">
            {past.slice(0, 10).map((plan) => (
              <CampaignRow key={plan.id} plan={plan} brandId={brand.id} variant="past" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CampaignRow({
  plan,
  brandId,
  variant,
}: {
  plan: CampaignPlan;
  brandId: string;
  variant: "active" | "pending" | "past";
}) {
  const statusLabel: Record<string, string> = {
    active: "Running",
    approved: "Running",
    pending: "Needs review",
    draft: "Draft",
    rejected: "Rejected",
  };
  const statusClass: Record<string, string> = {
    active: "badge-success",
    approved: "badge-success",
    pending: "badge-warning",
    draft: "badge-neutral",
    rejected: "badge-danger",
  };

  return (
    <Link
      href={`/app/brands/${brandId}/campaigns`}
      className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Megaphone className="w-4 h-4 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="text-sm text-text font-medium truncate">{plan.name}</div>
          <div className="text-xs text-text-muted truncate">{plan.goal}</div>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span className={`badge ${statusClass[plan.status] ?? "badge-neutral"}`}>
          {statusLabel[plan.status] ?? plan.status}
        </span>
        {variant === "pending" && (
          <span className="text-xs text-accent font-medium">Review →</span>
        )}
        <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-text transition-colors" />
      </div>
    </Link>
  );
}
