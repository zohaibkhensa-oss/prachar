"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { VisibilityScore } from "@/lib/schemas";

const BARS: { key: keyof VisibilityScore; label: string; weight: number }[] = [
  { key: "organic_rank_index", label: "ORGANIC", weight: 0.35 },
  { key: "ai_citation_rate", label: "AI CITATIONS", weight: 0.15 },
  { key: "social_reach_index", label: "SOCIAL", weight: 0.25 },
  { key: "paid_efficiency", label: "PAID EFF.", weight: 0.15 },
  { key: "momentum", label: "MOMENTUM", weight: 0.1 },
];

export function VisibilityScoreHero({ score }: { score: VisibilityScore }) {
  const [display, setDisplay] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    const target = score.overall;
    const start = performance.now();
    const dur = 900;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(target * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [score.overall]);

  return (
    <div className="border border-white/[0.06] bg-bg-surface text-text p-8">
      <div className="flex items-end gap-4">
        <span
          className="font-display text-[96px] leading-none text-accent tabular-nums"
          style={{ fontSize: "96px" }}
        >
          {Math.round(display)}
        </span>
        <span className="font-mono text-xs uppercase tracking-wider text-text-secondary pb-3">
          VISIBILITY SCORE / {score.week}
        </span>
      </div>
      <div className="mt-6 space-y-3">
        {BARS.map((b) => {
          const val = (score[b.key] as number) ?? 0;
          return (
            <div key={b.key}>
              <div className="flex items-center justify-between font-mono text-xs uppercase tracking-wider text-text-secondary">
                <span>{b.label}</span>
                <span className="tabular-nums text-text">
                  {val.toFixed(1)} <span className="text-text-muted">w{b.weight}</span>
                </span>
              </div>
              <div className="mt-1 h-3 w-full bg-white/[0.04] border border-white/[0.06]">
                <div
                  className="h-full bg-accent"
                  style={{ width: `${Math.min(100, val)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function VisibilityScoreCompact({ score }: { score: VisibilityScore }) {
  return (
    <div className={cn("border border-white/[0.06] bg-bg-card p-4 flex items-center gap-4")}>
      <span className="font-display text-4xl leading-none text-text tabular-nums">
        {Math.round(score.overall)}
      </span>
      <span className="font-mono text-[10px] uppercase tracking-wider text-text-secondary">
        VIS / {score.week}
      </span>
    </div>
  );
}
