"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Megaphone, BarChart3, User } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { AIOrb } from "./AIOrb";

const DOCK_ITEMS = [
  { label: "Home", href: "/app", icon: Home },
  { label: "Campaigns", href: "/app/campaigns", icon: Megaphone },
  { label: "Analytics", href: "/app/analytics", icon: BarChart3 },
  { label: "Profile", href: "/app/settings", icon: User },
];

/**
 * AIDock — persistent bottom navigation.
 * PRACHAR AI orb is the center item, always present, always glowing.
 */
export function AIDock({ onOrbClick }: { onOrbClick?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="fixed bottom-0 left-0 lg:left-[60px] right-0 z-50 h-16 bg-bg-surface/90 backdrop-blur-lg border-t border-white/[0.04] flex items-center justify-center">
      {/* Left items (2) */}
      <div className="flex items-center flex-1 justify-end gap-1 pr-4">
        {DOCK_ITEMS.slice(0, 2).map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg transition-colors",
                active ? "text-accent" : "text-text-muted hover:text-text-secondary",
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Center AI orb */}
      <div className="flex flex-col items-center gap-0.5 px-2">
        <motion.button
          onClick={onOrbClick}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className="relative"
          aria-label="Open PRACHAR AI"
        >
          <AIOrb state="idle" size={44} />
        </motion.button>
        <span className="text-[10px] font-medium text-accent">AI</span>
      </div>

      {/* Right items (2) */}
      <div className="flex items-center flex-1 justify-start gap-1 pl-4">
        {DOCK_ITEMS.slice(2).map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-lg transition-colors",
                active ? "text-accent" : "text-text-muted hover:text-text-secondary",
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
