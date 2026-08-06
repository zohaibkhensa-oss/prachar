"use client";

import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowLeft,
  Globe,
  Zap,
  Megaphone,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Eye,
  Target,
} from "lucide-react";
import { useBrands, useCampaignPlans } from "@/lib/hooks";
import { INDUSTRY_BY_ID, CHANNEL_LABELS } from "@/lib/industries";
import { Skeleton } from "@/components/ui/skeleton";

export default function BrandWorkspacePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data: brands, isLoading } = useBrands();
  const brand = brands?.find((b) => b.id === id) ?? null;
  const { data: plans } = useCampaignPlans(brand?.id ?? null);

  const industry = brand?.category ? INDUSTRY_BY_ID[brand.category] : null;
  const activePlans = plans?.filter((p) => p.status === "active" || p.status === "approved") ?? [];
  const pendingPlans = plans?.filter((p) => p.status === "pending" || p.status === "draft") ?? [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32 rounded-lg" />
        <Skeleton className="h-24 rounded-2xl" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <h2 className="font-display text-xl font-semibold text-text mb-2">Business not found</h2>
        <p className="text-sm text-text-secondary mb-6">This business may have been deleted.</p>
        <Link href="/app/brands" className="btn-primary inline-flex">Back to my brands</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back */}
      <Link
        href="/app/brands"
        className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        All brands
      </Link>

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/25 to-accent/5 flex items-center justify-center border border-accent/15 shrink-0">
            {industry ? (
              <span className="text-3xl">{industry.emoji}</span>
            ) : (
              <span className="font-display text-2xl font-semibold text-accent">
                {brand.name.charAt(0)}
              </span>
            )}
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold text-text">{brand.name}</h1>
              {industry && <span className="badge badge-neutral">{industry.label}</span>}
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
              {brand.website && (
                <span className="flex items-center gap-1">
                  <Globe className="w-3 h-3" />
                  {brand.website}
                </span>
              )}
            </div>
          </div>
        </div>
        <Link href={`/app/brands/${id}/campaigns/new`} className="btn-primary group">
          <Zap className="w-4 h-4" />
          Create campaign
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>

      {/* Visibility + quick metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Visibility */}
        <div className="glass-strong rounded-2xl p-6 flex flex-col items-center">
          <span className="label-field mb-3">How visible is your business?</span>
          {brand.visibility_score != null ? (
            <>
              <div className="font-display text-4xl sm:text-5xl font-semibold text-gradient-accent tabular-nums">
                {brand.visibility_score.toFixed(0)}
              </div>
              <div className="text-sm text-text-muted mt-1">out of 100</div>
            </>
          ) : (
            <div className="text-center py-4">
              <div className="font-display text-xl text-text-secondary">Coming soon</div>
              <div className="text-xs text-text-muted mt-1">After your first campaign runs</div>
            </div>
          )}
        </div>

        {/* Active campaigns */}
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <Megaphone className="w-4 h-4 text-accent" />
            <span className="label-field">Active campaigns</span>
          </div>
          <div className="font-display text-3xl font-semibold text-text tabular-nums">
            {activePlans.length}
          </div>
          <p className="text-xs text-text-muted mt-2">
            Promoting {brand.name} right now
          </p>
        </div>

        {/* Awaiting approval */}
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-warning" />
            <span className="label-field">Awaiting your approval</span>
          </div>
          <div className="font-display text-3xl font-semibold text-text tabular-nums">
            {pendingPlans.length}
          </div>
          <p className="text-xs text-text-muted mt-2">
            {pendingPlans.length > 0 ? "Review to start reaching customers" : "All caught up"}
          </p>
        </div>
      </div>

      {/* Campaigns list */}
      <div className="glass-strong rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-base font-semibold text-text">Your campaigns</h2>
          <Link
            href={`/app/brands/${id}/campaigns`}
            className="text-xs text-accent hover:underline"
          >
            View all →
          </Link>
        </div>

        {plans && plans.length > 0 ? (
          <div className="space-y-2">
            {plans.slice(0, 5).map((plan) => (
              <Link
                key={plan.id}
                href={`/app/brands/${id}/campaigns`}
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
                  <StatusBadge status={plan.status} />
                  <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-text transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-sm text-text-secondary mb-4">No campaigns yet. Let's fix that.</p>
            <Link href={`/app/brands/${id}/campaigns/new`} className="btn-primary inline-flex group">
              <Zap className="w-4 h-4" />
              Create your first campaign
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}
      </div>

      {/* What we recommend */}
      {industry && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">What we recommend for {industry.label.toLowerCase()}</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02]">
              <TrendingUp className="w-4 h-4 text-success shrink-0 mt-0.5" />
              <div>
                <div className="text-sm text-text font-medium">Focus on {industry.defaultChannels.slice(0, 2).map((c) => CHANNEL_LABELS[c] ?? c).join(" & ")}</div>
                <div className="text-xs text-text-muted mt-0.5">Where your customers already spend time</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02]">
              <Target className="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <div>
                <div className="text-sm text-text font-medium">Budget around ₹{industry.defaultBudget.toLocaleString("en-IN")}/month</div>
                <div className="text-xs text-text-muted mt-0.5">A good starting point for {industry.label.toLowerCase()}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    active: { label: "Running", className: "badge-success" },
    approved: { label: "Running", className: "badge-success" },
    pending: { label: "Needs review", className: "badge-warning" },
    draft: { label: "Draft", className: "badge-neutral" },
    rejected: { label: "Rejected", className: "badge-danger" },
  };
  const s = map[status] ?? { label: status, className: "badge-neutral" };
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}
