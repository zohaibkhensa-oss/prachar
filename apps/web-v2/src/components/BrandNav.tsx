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
    <nav className="flex border-b-3 border-ink bg-paper overflow-x-auto">
      {TABS.map((t) => {
        const href = `/app/brands/${brandId}${t.href}`;
        const isActive = t.label === active;
        return (
          <Link
            key={t.label}
            href={href}
            className={cn(
              "px-5 py-3 font-mono text-xs uppercase tracking-wider whitespace-nowrap border-r-3 border-ink last:border-r-0",
              isActive ? "bg-ink text-paper" : "bg-paper text-ink hover:bg-ink/10",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
