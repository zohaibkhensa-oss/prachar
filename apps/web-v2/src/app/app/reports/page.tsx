"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ChevronDown,
  FileText,
  Sparkles,
  AlertCircle,
  TrendingUp,
  Download,
  Eye,
  Calendar,
  Gauge,
  RefreshCw,
} from "lucide-react";
import { Card } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveBrand } from "@/lib/hooks";
import { apiGet, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIME_RANGES = ["7D", "30D", "90D", "12W", "1Y"];

interface ReportItem {
  id: string;
  week: string;
  pdf_s3_key: string | null;
  score_snapshot: Record<string, unknown> | null;
  created_at: string | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

function scoreValue(snapshot: Record<string, unknown> | null): number | null {
  if (!snapshot) return null;
  const v =
    (snapshot as Record<string, unknown>).visibility_score ??
    (snapshot as Record<string, unknown>).score ??
    (snapshot as Record<string, unknown>).overall;
  return typeof v === "number" ? v : null;
}

function scoreLabel(snapshot: Record<string, unknown> | null): string | null {
  const v = scoreValue(snapshot);
  return v !== null ? `${v.toFixed(0)}/100` : null;
}

function scoreColor(v: number | null): string {
  if (v === null) return "text-text-secondary";
  if (v >= 70) return "text-success";
  if (v >= 40) return "text-accent";
  return "text-warning";
}

export default function ReportsPage() {
  const { brand, brands, isLoading: brandLoading } = useActiveBrand();
  const [range, setRange] = useState("12W");
  const [brandOpen, setBrandOpen] = useState(false);
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);

  const activeBrandId = selectedBrandId ?? brand?.id ?? null;

  const { data: reports, isLoading, error, refetch, isFetching } = useQuery<
    ReportItem[]
  >({
    queryKey: ["reports", activeBrandId, range],
    queryFn: () =>
      apiGet<ReportItem[]>(`/reports/brands/${activeBrandId}/reports`),
    enabled: !!activeBrandId,
    retry: 1,
  });

  const brandList = brands ?? [];
  const selectedBrand =
    brandList.find((b) => b.id === activeBrandId) ?? brand;

  const loading = brandLoading || isLoading;
  const apiError =
    error instanceof ApiError && error.status === 404
      ? null
      : error;

  const handleDownload = (r: ReportItem) => {
    if (!r.pdf_s3_key) return;
    // The PDF is stored in S3/MinIO; open the key in a new tab via the API proxy
    window.open(`/api/reports/brands/${activeBrandId}/reports/${r.id}/pdf`, "_blank");
  };

  return (
    <div className="p-4 lg:p-8 max-w-[1600px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide text-text mb-1">
            Reports
          </h1>
          <p className="text-sm text-text-secondary">
            Performance intelligence across all channels and regions.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Brand selector */}
          {brandList.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setBrandOpen((v) => !v)}
                className="btn-secondary flex items-center gap-2"
              >
                <span className="text-text">
                  {selectedBrand?.name ?? "Select brand"}
                </span>
                <ChevronDown className="w-4 h-4 text-text-secondary" />
              </button>
              {brandOpen && (
                <div className="absolute top-full mt-2 right-0 z-30 glass-strong rounded-lg p-1 min-w-[200px] border border-white/10">
                  {brandList.map((b) => (
                    <button
                      key={b.id}
                      onClick={() => {
                        setSelectedBrandId(b.id);
                        setBrandOpen(false);
                      }}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-md text-sm transition-colors hover:bg-white/5",
                        b.id === activeBrandId
                          ? "text-accent"
                          : "text-text-secondary",
                      )}
                    >
                      {b.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* Time range */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.04]">
            {TIME_RANGES.map((t) => (
              <button
                key={t}
                onClick={() => setRange(t)}
                className={cn(
                  "px-3 py-1.5 rounded-md font-mono text-xs transition-all",
                  t === range
                    ? "bg-accent text-bg font-medium"
                    : "text-text-secondary hover:text-text",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          {/* Refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn-ghost flex items-center gap-2"
            aria-label="Refresh reports"
          >
            <RefreshCw
              className={cn("w-4 h-4", isFetching && "animate-spin")}
            />
          </button>
        </div>
      </div>

      {loading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      )}

      {!loading && apiError && (
        <Card className="text-center py-16">
          <div className="w-14 h-14 rounded-2xl bg-danger/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7 text-danger" />
          </div>
          <h3 className="font-display text-lg font-medium text-text mb-2">
            Couldn&apos;t load reports
          </h3>
          <p className="text-sm text-text-secondary mb-6">
            Something went wrong fetching your reports. Please try again.
          </p>
          <button
            onClick={() => refetch()}
            className="btn-primary inline-flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" /> Try Again
          </button>
        </Card>
      )}

      {!loading && !apiError && (reports?.length ?? 0) === 0 && (
        <Card className="text-center py-20">
          <motion.div
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5 glow-ring"
          >
            <Sparkles className="w-8 h-8 text-accent" />
          </motion.div>
          <h3 className="font-display text-xl font-medium text-text mb-2">
            No reports yet
          </h3>
          <p className="text-sm text-text-secondary max-w-sm mx-auto mb-6 leading-relaxed">
            Reports are generated automatically as your campaigns run. Create a
            campaign and the AI will produce your first weekly performance
            report.
          </p>
          <Link href="/app/campaigns" className="btn-primary inline-flex group">
            Create a campaign
          </Link>
        </Card>
      )}

      {!loading && !apiError && (reports?.length ?? 0) > 0 && (() => {
        const list = reports!;
        const latest = list[0];
        const latestScore = scoreValue(latest?.score_snapshot ?? null);
        return (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <SummaryStat
              icon={<FileText className="w-4 h-4" />}
              label="Total Reports"
              value={list.length}
            />
            <SummaryStat
              icon={<TrendingUp className="w-4 h-4" />}
              label="Latest Score"
              value={latestScore !== null ? `${latestScore.toFixed(0)}` : "—"}
              valueClass={scoreColor(latestScore)}
            />
            <SummaryStat
              icon={<Calendar className="w-4 h-4" />}
              label="Latest Week"
              value={latest ? `W${latest.week}` : "—"}
            />
            <SummaryStat
              icon={<Gauge className="w-4 h-4" />}
              label="Avg Score"
              value={(() => {
                const scores = list
                  .map((r) => scoreValue(r.score_snapshot))
                  .filter((v): v is number => v !== null);
                if (scores.length === 0) return "—";
                return (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(0);
              })()}
            />
          </div>

          {/* Latest report highlight */}
          {latest && (
            <Card className="mb-8 border-l-2 border-l-accent/40" hover={false}>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center glow-ring">
                    <TrendingUp className="w-6 h-6 text-accent" />
                  </div>
                  <div>
                    <span className="font-display text-lg font-medium text-text">
                      Latest Report — Week {latest.week}
                    </span>
                    <p className="text-sm text-text-secondary mt-0.5">
                      Generated on {formatDate(latest.created_at)}
                      {scoreLabel(latest.score_snapshot) && (
                        <>
                          {" "}
                          · Visibility score{" "}
                          <span className={cn("font-medium", scoreColor(latestScore))}>
                            {scoreLabel(latest.score_snapshot)}
                          </span>
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {latest.pdf_s3_key && (
                    <button
                      onClick={() => handleDownload(latest)}
                      className="btn-primary flex items-center gap-2"
                    >
                      <Eye className="w-4 h-4" /> View PDF
                    </button>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Report History */}
          <Card hover={false}>
            <SectionHeader
              title="Report History"
              subtitle={`${list.length} report${list.length === 1 ? "" : "s"}`}
              icon={<FileText className="w-4 h-4" />}
            />
            <div className="space-y-2">
              {list.map((r, i) => {
                const sv = scoreValue(r.score_snapshot);
                return (
                  <motion.div
                    key={r.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-white/[0.03] transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary group-hover:text-accent transition-colors">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <p className="font-display text-sm text-text">
                          Weekly Report — W{r.week}
                        </p>
                        <p className="text-xs text-text-muted font-mono flex items-center gap-1.5">
                          <Calendar className="w-3 h-3" />
                          {formatDate(r.created_at)}
                          {scoreLabel(r.score_snapshot) && (
                            <>
                              <span className="text-text-muted/40">·</span>
                              <span className={scoreColor(sv)}>
                                {scoreLabel(r.score_snapshot)}
                              </span>
                            </>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {r.pdf_s3_key ? (
                        <>
                          <button
                            onClick={() => handleDownload(r)}
                            className="btn-ghost flex items-center gap-1.5 text-xs"
                            title="View report"
                          >
                            <Eye className="w-3.5 h-3.5" /> View
                          </button>
                          <button
                            onClick={() => handleDownload(r)}
                            className="btn-ghost flex items-center gap-1.5 text-xs"
                            title="Download PDF"
                          >
                            <Download className="w-3.5 h-3.5" /> PDF
                          </button>
                        </>
                      ) : (
                        <span className="text-[10px] text-text-muted font-mono">
                          no pdf
                        </span>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </>
        );
      })()}
    </div>
  );
}

function SummaryStat({
  icon,
  label,
  value,
  valueClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  valueClass?: string;
}) {
  return (
    <div className="card-3d rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary">
          {icon}
        </div>
        <p className="label-field">{label}</p>
      </div>
      <p className={cn("font-display text-2xl font-semibold text-text", valueClass)}>
        {value}
      </p>
    </div>
  );
}
