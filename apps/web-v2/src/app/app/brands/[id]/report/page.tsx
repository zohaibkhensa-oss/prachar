"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { BrandNav } from "@/components/BrandNav";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Brand } from "@/lib/schemas";

type Report = {
  id: string;
  week: string;
  url: string | null;
  status: "ready" | "generating";
};

type ApiReport = {
  id: string;
  week: string;
  status: "ready" | "generating";
  download_url: string | null;
  pdf_s3_key: string | null;
};

export default function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: brand } = useQuery<Brand>({
    queryKey: ["brand", id],
    queryFn: () => apiGet<Brand>(`/brands/${id}`),
    retry: 0,
  });

  const { data: reports, isLoading } = useQuery<ApiReport[]>({
    queryKey: ["reports", id],
    queryFn: () => apiGet<ApiReport[]>(`/reports/brands/${id}/reports`),
    retry: 0,
  });

  const list: Report[] = (reports ?? []).map((r) => ({
    id: r.id,
    week: r.week,
    url: r.download_url,
    status: r.status,
  }));

  const download = async (r: Report) => {
    if (!r.url) return;
    const { url } = await apiGet<{ url: string }>(r.url);
    window.open(url, "_blank");
  };

  return (
    <div>
      <BrandNav brandId={id} active="Report" />
      <div className="p-8">
        <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide mb-8">
          Reports / {brand?.name ?? "Brand"}
        </h1>
        {isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {list.map((r) => (
              <Card key={r.id} className="flex items-center justify-between">
                <div>
                  <div className="font-display uppercase text-xl tracking-wide">
                    Week of {r.week}
                  </div>
                  <div className="mt-1 font-mono text-xs uppercase tracking-wider text-text/60">
                    Weekly visibility report
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={r.status === "ready" ? "yellow" : "ink"}>
                    {r.status}
                  </Badge>
                  <Button
                    variant="ink"
                    size="sm"
                    disabled={r.status !== "ready"}
                    onClick={() => void download(r)}
                  >
                    Download PDF
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
