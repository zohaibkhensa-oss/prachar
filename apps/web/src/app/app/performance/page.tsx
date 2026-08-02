"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  TrendingUp,
  ArrowRight,
  Sparkles,
  BarChart3,
  Calendar,
} from "lucide-react";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function PerformanceIndexPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const campaigns = plans ?? [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to see performance stories.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-semibold text-text">Performance Stories</h1>
        <p className="text-sm text-text-secondary mt-1">
          How each of your campaigns is performing — told as a story, not a dashboard.
        </p>
      </div>

      {/* No campaigns yet */}
      {campaigns.length === 0 && (
        <div className="glass-strong rounded-2xl p-12 text-center">
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
        </div>
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
                  className="block glass rounded-2xl p-5 hover:bg-white/[0.04] transition-colors group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
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
                      <ArrowRight className="w-4 h-4 text-text-muted transition-transform group-hover:translate-x-0.5" />
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
