"use client";

import { Search, Bell } from "lucide-react";
import { motion } from "framer-motion";

interface TopBarProps {
  onSearchClick?: () => void;
  onNotificationsClick?: () => void;
  notifCount?: number;
  email?: string;
}

/**
 * TopBar — search (⌘K), notifications bell, user avatar.
 * Same as v1 but simplified.
 */
export function TopBar({ onSearchClick, onNotificationsClick, notifCount = 0, email = "" }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 glass-strong border-b border-white/[0.04] px-4 lg:px-6 h-14 flex items-center justify-between gap-4">
      {/* Search */}
      <button
        onClick={onSearchClick}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-text-muted hover:text-text hover:border-white/[0.1] transition-all"
      >
        <Search className="w-3.5 h-3.5" />
        <span className="text-xs font-mono">Search...</span>
        <kbd className="font-mono text-[10px] px-1 py-0.5 rounded bg-white/[0.04] ml-2">⌘K</kbd>
      </button>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <button
          onClick={onNotificationsClick}
          className="relative text-text-secondary hover:text-text transition-colors"
          title="Notifications"
        >
          <motion.div
            animate={notifCount > 0 ? { scale: [1, 1.15, 1] } : { scale: 1 }}
            transition={{ duration: 0.5, repeat: notifCount > 0 ? Infinity : 0 }}
          >
            <Bell className="w-5 h-5" />
          </motion.div>
          {notifCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-danger text-white text-[9px] font-bold min-w-[16px] h-4 rounded-full flex items-center justify-center px-1">
              {notifCount}
            </span>
          )}
        </button>

        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-info to-purple-400 flex items-center justify-center text-xs font-semibold">
          {email[0]?.toUpperCase() || "P"}
        </div>
      </div>
    </header>
  );
}
