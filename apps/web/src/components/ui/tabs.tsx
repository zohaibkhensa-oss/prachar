"use client";

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabsProps {
  tabs: { label: string; value: string; content: ReactNode }[];
  defaultValue?: string;
  className?: string;
}

export function Tabs({ tabs, defaultValue, className }: TabsProps) {
  const [active, setActive] = useState(defaultValue ?? tabs[0]?.value ?? "");
  const current = tabs.find((t) => t.value === active);

  return (
    <div className={cn("", className)}>
      <div className="flex border-3 border-ink">
        {tabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setActive(t.value)}
            className={cn(
              "px-4 py-2 font-mono text-xs uppercase tracking-wider transition-colors flex-1",
              active === t.value
                ? "bg-ink text-paper"
                : "bg-paper text-ink hover:bg-ink/10",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="border-3 border-t-0 border-ink p-4">{current?.content}</div>
    </div>
  );
}
