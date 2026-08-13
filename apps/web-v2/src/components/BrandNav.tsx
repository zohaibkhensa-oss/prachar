"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "", label: "Overview" },
  { href: "/channels", label: "Channels" },
  { href: "/content", label: "Content" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/report", label: "Report" },
];

export function BrandNav({ brandId, active }: { brandId: string; active: string }) {
  return (
    <nav className="flex border-b border-white/[0.06] bg-bg-card overflow-x-auto">
      {TABS.map((t) => {
        const href = `/app/brands/${brandId}${t.href}`;
        const isActive = t.label === active;
        return (
          <Link
            key={t.label}
            href={href}
            className={cn(
              "px-5 py-3 font-mono text-xs uppercase tracking-wider whitespace-nowrap border-r border-white/[0.06] last:border-r-0",
              isActive ? "bg-bg-surface text-text" : "bg-bg-card text-text hover:bg-white/[0.04]",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
