"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home, Megaphone, Sparkles, CircleCheckBig, TrendingUp,
  Video, Image, Palette, Building2, Share2, Calendar, Star,
  Settings, ChevronLeft, ChevronRight, LogOut, Zap, Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getToken, clearToken } from "@/lib/auth";
import { useRouter } from "next/navigation";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSection {
  section: string;
  items: NavItem[];
}

const BUSINESS_NAV: NavSection[] = [
  {
    section: "Main",
    items: [
      { label: "Home", href: "/app", icon: Home },
      { label: "Campaigns", href: "/app/campaigns", icon: Megaphone },
      { label: "Creative Studio", href: "/app/creative-studio", icon: Sparkles },
      { label: "Review", href: "/app/review", icon: CircleCheckBig },
      { label: "Performance", href: "/app/performance", icon: TrendingUp },
      { label: "Timeline", href: "/app/timeline", icon: Clock },
    ],
  },
  {
    section: "Creative AI",
    items: [
      { label: "AI Video", href: "/app/video", icon: Video },
      { label: "AI Image Studio", href: "/app/images", icon: Image },
      { label: "Design AI", href: "/app/design", icon: Palette },
    ],
  },
  {
    section: "Brand",
    items: [
      { label: "My Brand", href: "/app/brands", icon: Building2 },
      { label: "Channels", href: "/app/channels", icon: Share2 },
      { label: "Content Calendar", href: "/app/calendar", icon: Calendar },
      { label: "Customer Reviews", href: "/app/reviews", icon: Star },
    ],
  },
  {
    section: "Settings",
    items: [
      { label: "Settings", href: "/app/settings", icon: Settings },
    ],
  },
];

/**
 * Sidebar — collapsible, collapsed by default (60px).
 * Expandable to 240px. On mobile, slides in as a drawer.
 */
export function Sidebar({ mobileOpen, onMobileClose }: { mobileOpen?: boolean; onMobileClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(true);
  const [email, setEmail] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem("prachar_email");
    if (stored) setEmail(stored);
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    if (onMobileClose) onMobileClose();
  }, [pathname, onMobileClose]);

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  const sidebarContent = (
    <>
      {/* Logo + collapse toggle */}
      <div className="flex items-center justify-between p-3 border-b border-white/[0.04] h-14">
        {collapsed ? (
          <Link href="/app" className="mx-auto lg:mx-0">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <Zap className="w-4 h-4 text-accent" />
            </div>
          </Link>
        ) : (
          <Link href="/app" className="flex items-center gap-2 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center">
              <Zap className="w-4 h-4 text-bg" />
            </div>
            <span className="font-display text-sm font-bold text-gradient-accent">PRACHAR AI</span>
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex text-text-muted hover:text-text transition-colors p-1"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
        {/* Mobile close button */}
        <button
          onClick={onMobileClose}
          className="lg:hidden text-text-muted hover:text-text transition-colors p-1"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      </div>

      {/* Workspace selector (only when expanded) */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="px-3 py-2.5 border-b border-white/[0.04] overflow-hidden"
          >
            <div className="flex items-center gap-2 p-2 rounded-lg hover:bg-white/[0.03] transition-colors">
              <div className="w-7 h-7 rounded-md bg-gradient-to-br from-info/20 to-accent/20 flex items-center justify-center shrink-0">
                <span className="font-display text-xs font-bold text-text">
                  {email[0]?.toUpperCase() || "P"}
                </span>
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="text-xs font-medium text-text truncate">My Workspace</div>
                <div className="text-[10px] text-text-muted truncate">{email || "demo@prachar.app"}</div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto scrollbar-none px-2 py-3 space-y-4">
        {BUSINESS_NAV.map((section) => (
          <div key={section.section}>
            <AnimatePresence>
              {!collapsed && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="px-3 mb-1.5 label-field text-[9px]"
                >
                  {section.section}
                </motion.div>
              )}
            </AnimatePresence>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 group relative",
                      active
                        ? "bg-accent/15 text-accent font-medium"
                        : "text-text-secondary hover:text-text hover:bg-white/[0.03]",
                      collapsed && "justify-center px-0",
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    {active && (
                      <motion.div
                        layoutId="sidebar-active"
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r-full"
                      />
                    )}
                    <Icon className="w-4 h-4 shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Status indicator */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="px-3 py-2.5 border-t border-white/[0.04] overflow-hidden"
          >
            <div className="glass rounded-lg p-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="w-3 h-3 rounded-full bg-success"
                />
                <span className="font-mono text-[10px] uppercase tracking-wider text-success">
                  Your marketing is live
                </span>
              </div>
              <div className="text-[10px] text-text-muted">Working in the background</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Logout */}
      <div className="p-3 border-t border-white/[0.04]">
        <button
          onClick={handleLogout}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-danger hover:bg-danger/5 transition-all w-full",
            collapsed && "justify-center px-0",
          )}
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden lg:flex fixed lg:sticky top-0 z-40 h-screen bg-bg-surface border-r border-white/[0.04] flex-col transition-all duration-300 ease-out-quart",
          collapsed ? "w-[60px]" : "w-[240px]",
        )}
      >
        {sidebarContent}
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onMobileClose}
              className="lg:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="lg:hidden fixed top-0 left-0 z-50 h-screen w-[260px] bg-bg-surface border-r border-white/[0.06] flex flex-col"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
