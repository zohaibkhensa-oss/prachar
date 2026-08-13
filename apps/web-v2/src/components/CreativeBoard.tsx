"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { CreativeAsset } from "@/lib/schemas";

export function CreativeBoard({ creatives }: { creatives: CreativeAsset[] }) {
  const groups = new Map<string, CreativeAsset[]>();
  for (const c of creatives) {
    const g = c.variant_group || "default";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(c);
  }
  return (
    <div className="space-y-6">
      {Array.from(groups.entries()).map(([group, items]) => (
        <div key={group}>
          <div className="font-mono text-xs uppercase tracking-wider text-text-secondary mb-3">
            VARIANT GROUP / {group}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "border border-white/[0.06] bg-bg-card p-4 flex flex-col gap-3",
                  c.is_winner && "ring-2 ring-accent ring-offset-2 ring-offset-bg-card",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-secondary">
                    {c.channel} · {c.locale} · {c.type}
                  </span>
                  {c.is_winner && <Badge variant="yellow">WINNER</Badge>}
                </div>
                {c.image_url ? (
                  <div className="aspect-video bg-white/[0.04] border-2 border-white/[0.04] flex items-center justify-center">
                    <img
                      src={c.image_url}
                      alt={c.id}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="aspect-video bg-white/[0.02] border-2 border-dashed border-white/[0.04] flex items-center justify-center font-mono text-[10px] uppercase text-text-muted">
                    IMAGE
                  </div>
                )}
                <p className="font-body text-sm text-text leading-snug">{c.copy}</p>
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="text-text-secondary uppercase tracking-wider">CTR</span>
                  <span className="tabular-nums text-text">
                    {c.ctr != null ? `${c.ctr.toFixed(2)}%` : "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
