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
  BarChart3,
  Clock,
} from "lucide-react";
import { useActiveBrand, useCampaignPlans } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function ResultsPage() {
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const { data: plans, isLoading: plansLoading } = useCampaignPlans(brand?.id ?? null);

  const isLoading = brandLoading || plansLoading;
  const activeCount = plans?.filter((p) => p.status === "active" || p.status === "approved").length ?? 0;
  const totalCampaigns = plans?.length ?? 0;
  const hasData = totalCampaigns > 0;

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
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
          <BarChart3 className="w-7 h-7 text-accent" />
        </div>
        <h2 className="font-display text-xl font-semibold text-text mb-2">Add your business first</h2>
        <p className="text-sm text-text-secondary mb-6">Create a brand to see your results.</p>
        <Link href="/onboarding" className="btn-primary inline-flex">Get started</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Your Results</h1>
          <p className="text-sm text-text-secondary mt-1">
            How {brand.name} is performing across all channels.
          </p>
        </div>
        {hasData && (
          <span className="badge badge-accent shrink-0">
            <TrendingUp className="w-3 h-3" />
            {totalCampaigns} campaign{totalCampaigns > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Top metrics — honest empty states when no data */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ResultCard
          icon={<Eye className="w-4 h-4" />}
          label="People reached"
          value={hasData ? "—" : "—"}
          sub={hasData ? "Data coming soon" : "No campaigns yet"}
          accent="text-info"
          dimmed={!hasData}
        />
        <ResultCard
          icon={<Target className="w-4 h-4" />}
          label="Customer actions"
          value={hasData ? "—" : "—"}
          sub={hasData ? "Clicks, calls, visits" : "No campaigns yet"}
          accent="text-success"
          dimmed={!hasData}
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
          sub={brand.visibility_score != null ? "Across all channels" : "Not scored yet"}
          accent="text-accent"
          dimmed={brand.visibility_score == null}
        />
      </div>

      {/* No data yet state */}
      {totalCampaigns === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-12 text-center"
        >
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-accent" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            No results yet — let&apos;s change that
          </h2>
          <p className="text-sm text-text-secondary mb-6 max-w-sm mx-auto">
            Create your first campaign and we&apos;ll show you exactly how many people you&apos;re reaching and how they&apos;re responding.
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

      {/* Campaigns exist but no performance data yet */}
      {totalCampaigns > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-2xl p-8"
        >
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="w-4 h-4 text-accent" />
            <h2 className="font-display text-base font-semibold text-text">Performance over time</h2>
          </div>
          <p className="text-sm text-text-secondary mb-6">
            Once your campaigns have run for a few days, you&apos;ll see:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              "How many people saw your business",
              "How many clicked, called, or visited",
              "Which channels are bringing the most customers",
              "How your visibility is improving over time",
            ].map((item, i) => (
              <motion.div
                key={item}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
                <span className="text-sm text-text-secondary">{item}</span>
              </motion.div>
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
        </motion.div>
      )}

      {/* Link to individual performance stories */}
      {totalCampaigns > 0 && plans && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-text-muted" />
            <span className="label-field">Campaign performance stories</span>
          </div>
          {plans.slice(0, 3).map((plan, i) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Link
                href={`/app/performance/${plan.id}`}
                className="block glass rounded-xl p-4 hover:bg-white/[0.04] hover:border-white/[0.1] transition-all group"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-text truncate">{plan.name || "Untitled campaign"}</h3>
                    {plan.goal && <p className="text-xs text-text-muted truncate mt-0.5">{plan.goal}</p>}
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent shrink-0" />
                </div>
              </Link>
            </motion.div>
          ))}
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
  dimmed,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent: string;
  dimmed?: boolean;
}) {
  return (
    <div className={`glass rounded-2xl p-5 transition-all ${dimmed ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={accent}>{icon}</span>
        <span className="label-field">{label}</span>
      </div>
      <div className="font-display text-3xl font-semibold text-text tabular-nums">{value}</div>
      <div className="text-[11px] text-text-muted mt-1.5">{sub}</div>
    </div>
  );
}
