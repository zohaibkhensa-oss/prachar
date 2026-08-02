"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { BrandNav } from "@/components/BrandNav";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { Connection } from "@/lib/schemas";

export default function ChannelsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: connections, isLoading } = useQuery<Connection[]>({
    queryKey: ["connections", id],
    queryFn: () => apiGet<Connection[]>(`/connections?brand_id=${id}`),
    retry: 0,
  });

  const list = connections ?? [];

  return (
    <div>
      <BrandNav brandId={id} active="Channels" />
      <div className="p-8">
        <h1 className="font-display uppercase text-4xl tracking-wide mb-8">Channels</h1>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : list.length === 0 ? (
          <Card className="text-center">
            <p className="font-mono text-xs uppercase tracking-wider text-ink/60">
              No channels connected. Visit Connections to add platforms.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {list.map((c) => (
              <Card key={c.id}>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-display uppercase text-xl tracking-wide">
                    {c.channel}
                  </span>
                  <Badge
                    variant={
                      c.status === "connected"
                        ? "yellow"
                        : c.status === "error"
                          ? "ink"
                          : "paper"
                    }
                  >
                    {c.status}
                  </Badge>
                </div>
                <div className="space-y-1 font-mono text-xs uppercase tracking-wider text-ink/60">
                  <div>Region: {c.region || "—"}</div>
                  <div>Last publish: {c.last_publish ?? "never"}</div>
                  <div className="text-ink">Next: {c.next_action || "—"}</div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
