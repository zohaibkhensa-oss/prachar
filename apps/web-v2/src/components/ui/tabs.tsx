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
      <div className="flex gap-1 p-1 bg-bg-surface rounded-lg border border-white/[0.06]">
        {tabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setActive(t.value)}
            className={cn(
              "px-4 py-2 text-sm font-body font-medium rounded-md transition-all duration-200 flex-1 min-h-[36px]",
              active === t.value
                ? "bg-bg-elevated text-text shadow-sm"
                : "text-text-secondary hover:text-text hover:bg-white/[0.04]",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-4">{current?.content}</div>
    </div>
  );
}
