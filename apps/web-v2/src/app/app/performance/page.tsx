"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight,
  Sparkles,
  BarChart3,
  TrendingUp,
  Target,
  Eye,
} from "lucide-react";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function PerformanceIndexPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const campaigns = plans ?? [];
  const activeCount = campaigns.filter((p) => p.status === "active" || p.status === "approved").length;
  const draftCount = campaigns.filter((p) => p.status === "draft").length;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
          <BarChart3 className="w-7 h-7 text-accent" />
        </div>
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to see performance stories.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">
            Performance Stories
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            How each of your campaigns is performing — told as a story, not a dashboard.
          </p>
        </div>
        {campaigns.length > 0 && (
          <span className="badge badge-accent shrink-0">
            <BarChart3 className="w-3 h-3" />
            {campaigns.length} campaign{campaigns.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Summary stats bar */}
      {campaigns.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-3.5 h-3.5 text-accent" />
              <span className="label-field">Total</span>
            </div>
            <div className="font-display text-2xl font-semibold text-text tabular-nums">{campaigns.length}</div>
            <div className="text-[10px] text-text-muted mt-0.5">All campaigns</div>
          </div>
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-3.5 h-3.5 text-success" />
              <span className="label-field">Active</span>
            </div>
            <div className="font-display text-2xl font-semibold text-text tabular-nums">{activeCount}</div>
            <div className="text-[10px] text-text-muted mt-0.5">Running now</div>
          </div>
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Eye className="w-3.5 h-3.5 text-text-muted" />
              <span className="label-field">Drafts</span>
            </div>
            <div className="font-display text-2xl font-semibold text-text tabular-nums">{draftCount}</div>
            <div className="text-[10px] text-text-muted mt-0.5">Not yet live</div>
          </div>
        </div>
      )}

      {/* No campaigns yet */}
      {campaigns.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-12 text-center"
        >
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-accent" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            No campaigns to report on yet
          </h2>
          <p className="text-sm text-text-secondary mb-6 max-w-sm mx-auto">
            Create your first campaign and we&apos;ll tell you exactly how many people you reached and how they responded.
          </p>
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

      {/* Campaign list — each links to its performance story */}
      {campaigns.length > 0 && (
        <div className="space-y-3">
          {campaigns.map((plan, i) => {
            const status = plan.status;
            const isActive = status === "active" || status === "approved";
            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  href={`/app/performance/${plan.id}`}
                  className="block glass rounded-2xl p-5 hover:bg-white/[0.04] hover:border-white/[0.1] transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
                          isActive
                            ? "bg-success/10 text-success"
                            : status === "draft"
                            ? "bg-text-muted/10 text-text-muted"
                            : "bg-accent/10 text-accent"
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            isActive ? "bg-success" : "bg-text-muted"
                          }`} />
                          {isActive ? "Running" : status}
                        </span>
                        {plan.overall_confidence > 0 && (
                          <span className="font-mono text-[10px] text-text-muted">
                            {Math.round(plan.overall_confidence)}% confidence
                          </span>
                        )}
                      </div>
                      <h3 className="font-display text-base font-semibold text-text truncate">
                        {plan.name || "Untitled campaign"}
                      </h3>
                      {plan.goal && (
                        <p className="text-xs text-text-secondary mt-1 truncate">
                          {plan.goal}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="hidden sm:flex items-center gap-1.5 text-xs text-text-muted">
                        <BarChart3 className="w-3.5 h-3.5" />
                        <span>View story</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
