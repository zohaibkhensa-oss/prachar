"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  TrendingUp,
  Eye,
  Target,
  ArrowRight,
  Sparkles,
  Megaphone,
} from "lucide-react";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function ResultsPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const activeCount = plans?.filter((p) => p.status === "active" || p.status === "approved").length ?? 0;
  const totalCampaigns = plans?.length ?? 0;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-48 rounded-xl" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="glass-strong rounded-2xl p-10 text-center max-w-md mx-auto">
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to see your results.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-semibold text-text">Your Results</h1>
        <p className="text-sm text-text-secondary mt-1">
          How {brand.name} is performing across all channels.
        </p>
      </div>

      {/* Top metrics — business language */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ResultCard
          icon={<Eye className="w-4 h-4" />}
          label="People reached"
          value="—"
          sub="This month"
          accent="text-info"
        />
        <ResultCard
          icon={<Target className="w-4 h-4" />}
          label="Customer actions"
          value="—"
          sub="Clicks, calls, visits"
          accent="text-success"
        />
        <ResultCard
          icon={<Megaphone className="w-4 h-4" />}
          label="Active campaigns"
          value={String(activeCount)}
          sub={`Out of ${totalCampaigns} total`}
          accent="text-accent"
        />
        <ResultCard
          icon={<TrendingUp className="w-4 h-4" />}
          label="Visibility"
          value={brand.visibility_score != null ? `${brand.visibility_score.toFixed(0)}/100` : "—"}
          sub="Across all channels"
          accent="text-accent"
        />
      </div>

      {/* No data yet state */}
      {totalCampaigns === 0 && (
        <div className="glass-strong rounded-2xl p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-accent" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            No results yet — let's change that
          </h2>
          <p className="text-sm text-text-secondary mb-6 max-w-sm mx-auto">
            Create your first campaign and we'll show you exactly how many people you're reaching and how they're responding.
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

      {/* Coming soon — real data after campaigns run */}
      {totalCampaigns > 0 && (
        <div className="glass-strong rounded-2xl p-8">
          <h2 className="font-display text-base font-semibold text-text mb-2">Performance over time</h2>
          <p className="text-sm text-text-secondary mb-6">
            Once your campaigns have run for a few days, you'll see:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              "How many people saw your business",
              "How many clicked, called, or visited",
              "Which channels are bringing the most customers",
              "How your visibility is improving over time",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
                <span className="text-sm text-text-secondary">{item}</span>
              </div>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2 text-xs text-text-muted">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-2 h-2 rounded-full bg-success"
            />
            <span>Your campaigns are running — data will appear here soon</span>
          </div>
        </div>
      )}
    </div>
  );
}

function ResultCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent: string;
}) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className={accent}>{icon}</span>
        <span className="label-field">{label}</span>
      </div>
      <div className="font-display text-3xl font-semibold text-text tabular-nums">{value}</div>
      <div className="text-[11px] text-text-muted mt-1.5">{sub}</div>
    </div>
  );
}
