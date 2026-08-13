"use client";

import { cn } from "@/lib/utils";

export const LOOP_STAGES = [
  "INGEST-DELTA",
  "MEASURE",
  "DIAGNOSE",
  "REGENERATE",
  "PUBLISH",
  "REALLOCATE-BUDGET",
  "REPORT",
] as const;

export function LoopStatus({
  stage,
  stages = LOOP_STAGES as unknown as string[],
}: {
  stage: string;
  stages?: string[];
}) {
  const activeIdx = Math.max(0, stages.indexOf(stage));
  return (
    <div className="border border-white/[0.06] bg-bg-surface text-text p-4 overflow-x-auto">
      <div className="font-mono text-xs uppercase tracking-wider text-text-secondary mb-3">
        WEEKLY LOOP / STAGE {activeIdx + 1} of {stages.length}
      </div>
      <div className="flex items-stretch gap-0 min-w-max">
        {stages.map((s, i) => {
          const completed = i < activeIdx;
          const active = i === activeIdx;
          return (
            <div key={s} className="flex items-stretch">
              <div
                className={cn(
                  "px-4 py-2 font-mono text-xs uppercase tracking-wider border",
                  active
                    ? "bg-accent text-text border-white/[0.06]"
                    : completed
                      ? "bg-bg-card text-text border-white/[0.06]"
                      : "bg-bg-surface text-text-muted border-white/[0.06]",
                )}
              >
                {String(i + 1).padStart(2, "0")} · {s}
              </div>
              {i < stages.length - 1 && (
                <div className="w-3 self-center h-px bg-white/[0.06]" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
