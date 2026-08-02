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
} from "lucide-react";
import { useActiveBrand, useCampaignPlans, type CampaignPlan } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function CampaignsPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const active = plans?.filter((p) => p.status === "active" || p.status === "approved") ?? [];
  const pending = plans?.filter((p) => p.status === "pending" || p.status === "draft") ?? [];

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Campaigns</h1>
          <p className="text-sm text-text-secondary mt-1">
            {plans && plans.length > 0
              ? `${active.length} running · ${pending.length} need your review`
              : "Let's create your first campaign"}
          </p>
        </div>
        <Link
          href={`/app/brands/${brand.id}/campaigns/new`}
          className="btn-primary group"
        >
          <Plus className="w-4 h-4" />
          New campaign
        </Link>
      </div>

      {/* Needs your attention */}
      {pending.length > 0 && (
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
          <div className="text-center py-8">
            <Megaphone className="w-10 h-10 text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-secondary mb-4">No campaigns running yet.</p>
            <Link
              href={`/app/brands/${brand.id}/campaigns/new`}
              className="btn-primary inline-flex group"
            >
              <Sparkles className="w-4 h-4" />
              Create your first campaign
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}
      </div>

      {/* Past campaigns */}
      {plans && plans.length > active.length + pending.length && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-text-muted" />
            <h2 className="font-display text-base font-semibold text-text">Past campaigns</h2>
          </div>
          <div className="space-y-2">
            {plans.filter((p) => !active.includes(p) && !pending.includes(p)).slice(0, 10).map((plan) => (
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
