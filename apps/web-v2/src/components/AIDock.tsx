"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Megaphone, BarChart3, User } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
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
  const [showHint, setShowHint] = useState(false);

  // Show first-time hint pointing at the orb
  useEffect(() => {
    const seen = localStorage.getItem("prachar_orb_hint_seen");
    if (!seen) {
      const timer = setTimeout(() => setShowHint(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleOrbClick = () => {
    localStorage.setItem("prachar_orb_hint_seen", "1");
    setShowHint(false);
    onOrbClick?.();
  };

  const dismissHint = () => {
    localStorage.setItem("prachar_orb_hint_seen", "1");
    setShowHint(false);
  };

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

      {/* Center AI orb — prominent, pulsing, labeled */}
      <div className="flex flex-col items-center gap-0.5 px-2 relative">
        {/* Pulsing ring to draw attention */}
        <motion.div
          className="absolute -top-1 left-1/2 -translate-x-1/2 rounded-full"
          style={{ width: 56, height: 56 }}
          animate={{
            boxShadow: [
              "0 0 0 0px rgba(255,140,66,0.4)",
              "0 0 0 8px rgba(255,140,66,0)",
            ],
          }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
        />
        <motion.button
          onClick={handleOrbClick}
          whileHover={{ scale: 1.12 }}
          whileTap={{ scale: 0.92 }}
          className="relative"
          aria-label="Chat with PRACHAR AI"
        >
          <AIOrb state="idle" size={52} />
        </motion.button>
        <span className="text-[11px] font-semibold text-accent tracking-wide">
          TAP TO CHAT
        </span>

        {/* First-time hint bubble */}
        <AnimatePresence>
          {showHint && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              transition={{ duration: 0.3 }}
              className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 whitespace-nowrap"
            >
              <div className="glass-strong rounded-xl px-4 py-2.5 border border-accent/30 shadow-lg">
                <p className="text-xs text-text font-medium">
                  Tap the orb to chat with your AI
                </p>
                <p className="text-[10px] text-text-muted mt-0.5">
                  Ask anything — create campaigns, check performance, generate content
                </p>
                <button
                  onClick={dismissHint}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-bg-surface border border-white/10 text-text-muted hover:text-text text-[10px] flex items-center justify-center"
                >
                  ✕
                </button>
              </div>
              {/* Arrow pointing down */}
              <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-accent/30" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
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
