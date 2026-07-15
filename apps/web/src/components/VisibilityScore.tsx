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
    <div className="border-3 border-ink bg-ink text-paper p-8">
      <div className="flex items-end gap-4">
        <span
          className="font-display text-[96px] leading-none text-yellow tabular-nums"
          style={{ fontSize: "96px" }}
        >
          {Math.round(display)}
        </span>
        <span className="font-mono text-xs uppercase tracking-wider text-paper/60 pb-3">
          VISIBILITY SCORE / {score.week}
        </span>
      </div>
      <div className="mt-6 space-y-3">
        {BARS.map((b) => {
          const val = (score[b.key] as number) ?? 0;
          return (
            <div key={b.key}>
              <div className="flex items-center justify-between font-mono text-xs uppercase tracking-wider text-paper/70">
                <span>{b.label}</span>
                <span className="tabular-nums text-paper">
                  {val.toFixed(1)} <span className="text-paper/40">w{b.weight}</span>
                </span>
              </div>
              <div className="mt-1 h-3 w-full bg-paper/10 border border-paper/20">
                <div
                  className="h-full bg-yellow"
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
    <div className={cn("border-3 border-ink bg-paper p-4 flex items-center gap-4")}>
      <span className="font-display text-4xl leading-none text-ink tabular-nums">
        {Math.round(score.overall)}
      </span>
      <span className="font-mono text-[10px] uppercase tracking-wider text-ink/60">
        VIS / {score.week}
      </span>
    </div>
  );
}
