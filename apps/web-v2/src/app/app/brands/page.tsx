"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Plus,
  Globe,
  ArrowRight,
  Building2,
  Sparkles,
} from "lucide-react";
import { useBrands } from "@/lib/hooks";
import { INDUSTRY_BY_ID } from "@/lib/industries";
import { Skeleton } from "@/components/ui/skeleton";

export default function BrandsListPage() {
  const router = useRouter();
  const { data: brands, isLoading } = useBrands();

  // If user has no brands, send them to onboarding
  useEffect(() => {
    if (!isLoading && brands && brands.length === 0) {
      router.replace("/onboarding");
    }
  }, [isLoading, brands, router]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-16 w-48 rounded-xl" />
          <Skeleton className="h-10 w-32 rounded-lg" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">My Brand</h1>
          <p className="text-sm text-text-secondary mt-1">
            {brands && brands.length > 0
              ? `${brands.length} ${brands.length === 1 ? "business" : "businesses"} · We promote you everywhere`
              : "Add your business to get started"}
          </p>
        </div>
        <Link href="/onboarding" className="btn-primary group">
          <Plus className="w-4 h-4" />
          Add another business
        </Link>
      </div>

      {/* Brand cards */}
      {brands && brands.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {brands.map((brand, i) => {
            const industry = brand.category ? INDUSTRY_BY_ID[brand.category] : null;
            return (
              <motion.div
                key={brand.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              >
                <Link
                  href={`/app/brands/${brand.id}`}
                  className="block glass-strong rounded-2xl p-5 hover:border-accent/20 transition-all duration-200 group h-full"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center shrink-0 border border-accent/10">
                        {industry ? (
                          <span className="text-xl">{industry.emoji}</span>
                        ) : (
                          <span className="font-display text-lg font-semibold text-accent">
                            {brand.name.charAt(0)}
                          </span>
                        )}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-display text-base font-semibold text-text truncate">
                          {brand.name}
                        </h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          {industry && (
                            <span className="badge badge-neutral text-[10px]">{industry.label}</span>
                          )}
                          {brand.website && (
                            <span className="flex items-center gap-1 text-[11px] text-text-muted truncate">
                              <Globe className="w-3 h-3 shrink-0" />
                              {brand.website}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Visibility */}
                  {brand.visibility_score != null && (
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-text-secondary">Visibility</span>
                        <span className="font-mono text-xs text-text">{brand.visibility_score.toFixed(0)}/100</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${brand.visibility_score}%` }}
                          transition={{ delay: 0.2 + i * 0.06, duration: 0.6, ease: "easeOut" }}
                          className="h-full bg-gradient-to-r from-accent to-accent/60 rounded-full"
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
                    <span className="text-xs text-text-muted">
                      {industry ? `${industry.label} · ` : ""}Added {new Date(brand.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                    </span>
                    <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {brands && brands.length === 0 && (
        <div className="glass-strong rounded-2xl p-12 text-center max-w-md mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-7 h-7 text-accent" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text mb-2">
            Add your first business
          </h2>
          <p className="text-sm text-text-secondary mb-6">
            Tell us what business you run. We'll handle the rest — strategy, ads, posts, and channels.
          </p>
          <Link href="/onboarding" className="btn-primary inline-flex group">
            <Sparkles className="w-4 h-4" />
            Get started
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      )}
    </div>
  );
}
