"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { BrandNav } from "@/components/BrandNav";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Campaign } from "@/lib/schemas";

export default function CampaignsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const qc = useQueryClient();

  const { data: campaigns, isLoading } = useQuery<Campaign[]>({
    queryKey: ["campaigns", id],
    queryFn: () => apiGet<Campaign[]>(`/brands/${id}/campaigns`),
    retry: 0,
  });

  const toggle = useMutation({
    mutationFn: (c: Campaign) =>
      apiPost<Campaign>(`/campaigns/${c.id}/${c.status === "active" ? "pause" : "resume"}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns", id] }),
  });

  const setBudget = useMutation({
    mutationFn: (vars: { c: Campaign; budget: number }) =>
      apiPost<Campaign>(`/campaigns/${vars.c.id}/budget`, { budget: vars.budget }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns", id] }),
  });

  const list = campaigns ?? [];

  return (
    <div>
      <BrandNav brandId={id} active="Campaigns" />
      <div className="p-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide">Campaigns</h1>
          <Link href={`/app/brands/${id}/campaigns/new`} className="btn-yellow text-sm">
            + New campaign
          </Link>
        </div>
        {isLoading ? (
          <div className="space-y-4">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : list.length === 0 ? (
          <Card className="text-center">
            <p className="font-mono text-xs uppercase tracking-wider text-ink/60 mb-4">
              No campaigns yet
            </p>
            <Link href={`/app/brands/${id}/campaigns/new`} className="btn-yellow">
              Launch your first campaign
            </Link>
          </Card>
        ) : (
          <div className="space-y-4">
            {list.map((c) => (
              <Card key={c.id}>
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-display uppercase text-xl tracking-wide">
                        {c.name}
                      </span>
                      <Badge variant={c.status === "active" ? "yellow" : "ink"}>
                        {c.status}
                      </Badge>
                    </div>
                    <div className="mt-1 font-mono text-xs uppercase tracking-wider text-ink/60">
                      {c.network} · spend ₹{c.spend.toFixed(0)} · CPA ₹{c.cpa.toFixed(0)} · ROAS {c.roas.toFixed(1)}x
                    </div>
                  </div>
                  <Button
                    variant={c.status === "active" ? "ink" : "yellow"}
                    size="sm"
                    onClick={() => toggle.mutate(c)}
                    disabled={toggle.isPending}
                  >
                    {c.status === "active" ? "Pause" : "Resume"}
                  </Button>
                </div>
                <div className="mt-4">
                  <div className="flex items-center justify-between font-mono text-xs uppercase tracking-wider text-ink/60 mb-1">
                    <span>Budget</span>
                    <span className="tabular-nums text-ink">₹{c.budget.toFixed(0)}/mo</span>
                  </div>
                  <input
                    type="range"
                    min={500}
                    max={50000}
                    step={500}
                    defaultValue={c.budget}
                    onChange={(e) =>
                      setBudget.mutate({ c, budget: Number(e.target.value) })
                    }
                    className="w-full accent-yellow"
                  />
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
