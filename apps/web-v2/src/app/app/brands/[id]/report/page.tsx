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
  url: string;
  status: "ready" | "generating";
};

const MOCK: Report[] = Array.from({ length: 6 }).map((_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - i * 7);
  return {
    id: `r${i}`,
    week: d.toISOString().slice(0, 10),
    url: `#report-${i}`,
    status: i === 0 ? "generating" : "ready",
  };
});

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

  const { data: reports, isLoading } = useQuery<Report[]>({
    queryKey: ["reports", id],
    queryFn: () => apiGet<Report[]>(`/brands/${id}/reports`),
    retry: 0,
  });

  const list = reports ?? MOCK;

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
                  <div className="mt-1 font-mono text-xs uppercase tracking-wider text-ink/60">
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
                    onClick={() => window.open(r.url, "_blank")}
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
