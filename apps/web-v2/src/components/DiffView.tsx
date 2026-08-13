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
    <div className="border border-white/[0.06] bg-bg-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 font-mono text-xs uppercase tracking-wider hover:bg-white/[0.02]"
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
        <div className="grid grid-cols-1 md:grid-cols-2 border-t border-white/[0.06]">
          <div className="p-4 border-b md:border-b-0 md:border-r border-white/[0.06]">
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
              BEFORE
            </div>
            <p className="font-body text-sm whitespace-pre-wrap text-text-secondary line-through decoration-white/[0.08]">
              {before}
            </p>
          </div>
          <div className={cn("p-4", positive && "bg-accent/10")}>
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
              AFTER
            </div>
            <p className="font-body text-sm whitespace-pre-wrap text-text">{after}</p>
          </div>
        </div>
      )}
    </div>
  );
}
