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
    <div className="border-3 border-ink bg-ink text-paper p-4 overflow-x-auto">
      <div className="font-mono text-xs uppercase tracking-wider text-paper/60 mb-3">
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
                  "px-4 py-2 font-mono text-xs uppercase tracking-wider border-3",
                  active
                    ? "bg-yellow text-ink border-ink"
                    : completed
                      ? "bg-paper text-ink border-ink"
                      : "bg-ink text-paper/50 border-paper/20",
                )}
              >
                {String(i + 1).padStart(2, "0")} · {s}
              </div>
              {i < stages.length - 1 && (
                <div className="w-3 self-center h-px bg-paper/30" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
