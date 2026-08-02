"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function DiffView({
  before,
  after,
  delta,
}: {
  before: string;
  after: string;
  delta?: number;
}) {
  const [open, setOpen] = useState(false);
  const positive = delta != null && delta > 0;
  return (
    <div className="border-3 border-ink bg-paper">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 font-mono text-xs uppercase tracking-wider hover:bg-ink/5"
      >
        <span>{open ? "HIDE DIFF" : "SHOW DIFF"}</span>
        {delta != null && (
          <Badge variant={positive ? "yellow" : "ink"}>
            GSC {positive ? "+" : ""}
            {delta}
          </Badge>
        )}
      </button>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-2 border-t-3 border-ink">
          <div className="p-4 border-b-3 md:border-b-0 md:border-r-3 border-ink">
            <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50 mb-2">
              BEFORE
            </div>
            <p className="font-body text-sm whitespace-pre-wrap text-ink/70 line-through decoration-ink/30">
              {before}
            </p>
          </div>
          <div className={cn("p-4", positive && "bg-yellow/10")}>
            <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50 mb-2">
              AFTER
            </div>
            <p className="font-body text-sm whitespace-pre-wrap text-ink">{after}</p>
          </div>
        </div>
      )}
    </div>
  );
}
