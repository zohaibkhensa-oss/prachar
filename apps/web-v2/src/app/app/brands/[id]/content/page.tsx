"use client";

import { Fragment, use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { BrandNav } from "@/components/BrandNav";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { DiffView } from "@/components/DiffView";
import type { Brand, CreativeAsset } from "@/lib/schemas";

type ContentItem = {
  id: string;
  title: string;
  channel: string;
  status: string;
  before: string;
  after: string;
  gsc_delta?: number;
};

const MOCK: ContentItem[] = [
  {
    id: "c1",
    title: "Homepage hero copy",
    channel: "google",
    status: "published",
    before: "We make great coffee for everyone.",
    after: "Single-origin coffee, roasted weekly, delivered fresh across India.",
    gsc_delta: 7,
  },
  {
    id: "c2",
    title: "Instagram reel hook",
    channel: "instagram",
    status: "published",
    before: "Check out our new beans.",
    after: "POV: your morning brew just got a passport. #coffee #specialty",
    gsc_delta: 3,
  },
];

export default function ContentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: brand } = useQuery<Brand>({
    queryKey: ["brand", id],
    queryFn: () => apiGet<Brand>(`/brands/${id}`),
    retry: 0,
  });

  const { data: creatives } = useQuery<CreativeAsset[]>({
    queryKey: ["content", id],
    queryFn: () => apiGet<CreativeAsset[]>(`/brands/${id}/content`),
    retry: 0,
  });

  const items: ContentItem[] = creatives
    ? creatives.map((c) => ({
        id: c.id,
        title: c.copy.slice(0, 40) || c.id,
        channel: c.channel,
        status: c.policy_status,
        before: "",
        after: c.copy,
        gsc_delta: undefined,
      }))
    : MOCK;

  return (
    <div>
      <BrandNav brandId={id} active="Content" />
      <div className="p-8">
        <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide mb-8">
          Content / {brand?.name ?? "Brand"}
        </h1>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Delta</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((it) => (
              <Fragment key={it.id}>
                <TableRow
                  className="cursor-pointer hover:bg-bg-surface/5"
                  onClick={() => setExpanded(expanded === it.id ? null : it.id)}
                >
                  <TableCell className="font-body">{it.title}</TableCell>
                  <TableCell className="font-mono text-xs uppercase">{it.channel}</TableCell>
                  <TableCell>
                    <Badge variant={it.status === "approved" || it.status === "published" ? "yellow" : "ink"}>
                      {it.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {"gsc_delta" in it && it.gsc_delta != null ? `+${it.gsc_delta}` : "—"}
                  </TableCell>
                </TableRow>
                {expanded === it.id && (
                  <TableRow className="bg-bg-card">
                    <TableCell colSpan={4} className="p-4">
                      {"before" in it && it.before ? (
                        <DiffView before={it.before} after={it.after} delta={it.gsc_delta} />
                      ) : (
                        <div className="border border-white/[0.06] p-4 font-body text-sm">
                          {it.after}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
