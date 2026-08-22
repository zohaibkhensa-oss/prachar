"use client";

import { useState, useEffect, useRef, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import * as LucideIcons from "lucide-react";
import { cn } from "@/lib/utils";
import { clearToken, getToken } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { CommandPalette } from "@/components/ui/command-palette";
import { VoiceAssistant } from "@/components/VoiceAssistant";
import { ProactiveNotifications } from "@/components/ProactiveNotifications";
import { getPracharMessages } from "@/lib/proactive";
import { unifiedConsultApi, type NavSection } from "@/lib/unified-consult";
import {
  LayoutDashboard,
  Building2,
  Megaphone,
  Share2,
  BarChart3,
  Settings,
  ChevronLeft,
  Bell,
  Search,
  LogOut,
  Zap,
  CircleDot,
  Menu,
  X,
  Star,
  Calendar as CalIcon,
  Video,
  RefreshCw,
  Users,
  type LucideIcon,
} from "lucide-react";

// Fallback nav (used while the backend config loads, or if the endpoint is unavailable)
// 3 clear sections: Main (day-to-day), Brand (brand management), Settings.
// "Customer Reviews" is deliberately distinct from the "Review" workflow item.
const BUSINESS_NAV_FALLBACK: NavSection[] = [
  { section: "Main", items: [
    { label: "Home", path: "/app", icon: "LayoutDashboard" },
    { label: "Campaigns", path: "/app/campaigns", icon: "Megaphone" },
    { label: "Creative Studio", path: "/app/creative-studio", icon: "Sparkles" },
    { label: "Review", path: "/app/review", icon: "CircleCheckBig" },
    { label: "Performance", path: "/app/performance", icon: "TrendingUp" },
  ]},
  { section: "Brand", items: [
    { label: "My Brand", path: "/app/brands", icon: "Building2" },
    { label: "Channels", path: "/app/channels", icon: "Share2" },
    { label: "Content Calendar", path: "/app/calendar", icon: "Calendar" },
    { label: "Customer Reviews", path: "/app/reviews", icon: "Star" },
  ]},
  { section: "Settings", items: [
    { label: "Settings", path: "/app/settings", icon: "Settings" },
  ]},
];

const CREATOR_NAV_FALLBACK: NavSection[] = [
  { section: "Main", items: [
    { label: "Home", path: "/app", icon: "LayoutDashboard" },
    { label: "Content", path: "/app/campaigns", icon: "Megaphone" },
    { label: "Creative Studio", path: "/app/creative-studio", icon: "Sparkles" },
    { label: "Review", path: "/app/review", icon: "CircleCheckBig" },
    { label: "Performance", path: "/app/performance", icon: "TrendingUp" },
    { label: "Repurpose video", path: "/app/repurpose", icon: "RefreshCw" },
    { label: "Plan YouTube video", path: "/app/youtube-plan", icon: "Video" },
  ]},
  { section: "Channel", items: [
    { label: "My Channel", path: "/app/brands", icon: "Video" },
    { label: "Channels", path: "/app/channels", icon: "Share2" },
    { label: "Content Calendar", path: "/app/calendar", icon: "Calendar" },
    { label: "Audience", path: "/app/analytics", icon: "Users" },
  ]},
  { section: "Settings", items: [
    { label: "Settings", path: "/app/settings", icon: "Settings" },
  ]},
];

function getLucideIcon(name: string): LucideIcon {
  const icons = LucideIcons as unknown as Record<string, LucideIcon>;
  return icons[name] ?? icons.LayoutDashboard ?? (icons.Circle as unknown as LucideIcon);
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [customerType, setCustomerType] = useState<"business" | "creator">("business");
  const [notifOpen, setNotifOpen] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    // If user hasn't completed onboarding, send them to the conversation
    const onboarded = window.localStorage.getItem("prachar_onboarded");
    if (!onboarded) {
      router.replace("/onboarding");
      return;
    }
    setEmail(window.localStorage.getItem("prachar_email") ?? "you@curv.app");
    setCustomerType(window.localStorage.getItem("prachar_customer_type") === "creator" ? "creator" : "business");
    setReady(true);
  }, [router]);

  // Fetch nav from the Domain Pack registry (driven by the backend)
  const domain = customerType === "creator" ? "creator" : "business";
  const { data: navSections } = useQuery({
    queryKey: ["domain-nav", domain],
    queryFn: async () => {
      const config = await unifiedConsultApi.config(domain);
      return config.nav_sections;
    },
    enabled: ready,
    staleTime: 5 * 60 * 1000,
  });

  const activeNav = navSections ?? (customerType === "creator" ? CREATOR_NAV_FALLBACK : BUSINESS_NAV_FALLBACK);

  // Fetch pending proactive notification count for the bell badge.
  const { data: pracharMessagesData } = useQuery({
    queryKey: ["prachar-messages-count"],
    queryFn: getPracharMessages,
    enabled: ready,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
  const notifCount = pracharMessagesData?.count ?? 0;

  // Pulse the bell icon when the notification count increases.
  const prevNotifCount = useRef(notifCount);
  const [bellPulse, setBellPulse] = useState(false);
  useEffect(() => {
    if (notifCount > prevNotifCount.current) {
      setBellPulse(true);
      const t = setTimeout(() => setBellPulse(false), 1200);
      prevNotifCount.current = notifCount;
      return () => clearTimeout(t);
    }
    prevNotifCount.current = notifCount;
  }, [notifCount]);

  function logout() {
    clearToken();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
          className="w-8 h-8 rounded-full border-2 border-accent/20 border-t-accent"
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex">
      <CommandPalette />
      <VoiceAssistant />
      <ProactiveNotifications open={notifOpen} onClose={() => setNotifOpen(false)} />

      {/* ─── Mobile overlay ─── */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* ─── Sidebar ─── */}
      <aside
        className={cn(
          "fixed lg:sticky top-0 z-50 h-screen bg-bg-surface border-r border-white/[0.04] flex flex-col transition-all duration-300 ease-out-quart",
          collapsed ? "w-[60px]" : "w-[240px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        {/* Logo + collapse */}
        <div className="flex items-center justify-between p-3 border-b border-white/[0.04]">
          {!collapsed && (
            <Link href="/app" className="flex items-center gap-2 overflow-hidden">
              <Logo size="sm" className="max-h-[32px] w-auto" />
            </Link>
          )}
          {collapsed && (
            <Link href="/app" className="mx-auto">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Zap className="w-4 h-4 text-accent" />
              </div>
            </Link>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex text-text-muted hover:text-text transition-colors p-1"
          >
            <ChevronLeft className={cn("w-4 h-4 transition-transform", collapsed && "rotate-180")} />
          </button>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden text-text-muted hover:text-text p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Workspace selector */}
        {!collapsed && (
          <div className="px-3 py-2.5 border-b border-white/[0.04]">
            <button className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-white/[0.03] transition-colors group">
              <div className="w-7 h-7 rounded-md bg-gradient-to-br from-info/20 to-accent/20 flex items-center justify-center shrink-0">
                <span className="font-display text-xs font-bold text-text">
                  {email[0]?.toUpperCase() || "P"}
                </span>
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="text-xs font-medium text-text truncate">My Workspace</div>
                <div className="text-[10px] text-text-muted truncate">{email}</div>
              </div>
            </button>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto scrollbar-none px-2 py-3 space-y-4">
          {activeNav.map((section) => (
            <div key={section.section}>
              {!collapsed && (
                <div className="px-3 mb-1.5 label-field text-[9px]">{section.section}</div>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const active = pathname === item.path || pathname.startsWith(item.path + "/");
                  const Icon = getLucideIcon(item.icon);
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      onClick={() => setMobileOpen(false)}
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

        {/* Status */}
        {!collapsed && (
          <div className="px-3 py-2.5 border-t border-white/[0.04]">
            <div className="glass rounded-lg p-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <CircleDot className="w-3 h-3 text-success" />
                </motion.div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-success">
                  Your marketing is live
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-muted">Working in the background</span>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-3 border-t border-white/[0.04]">
          <button
            onClick={logout}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-danger hover:bg-danger/5 transition-all",
              collapsed && "justify-center px-0",
            )}
            title={collapsed ? "Logout" : undefined}
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* ─── Main content ─── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Top bar */}
        <header className="sticky top-0 z-30 glass-strong border-b border-white/[0.04] px-4 lg:px-6 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden text-text-secondary hover:text-text"
            >
              <Menu className="w-5 h-5" />
            </button>
            <button
              onClick={() => {
                const event = new KeyboardEvent("keydown", { key: "k", metaKey: true });
                document.dispatchEvent(event);
              }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-text-muted hover:text-text hover:border-white/[0.1] transition-all"
            >
              <Search className="w-3.5 h-3.5" />
              <span className="text-xs font-mono">Search...</span>
              <kbd className="font-mono text-[10px] px-1 py-0.5 rounded bg-white/[0.04] ml-2">⌘K</kbd>
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNotifOpen(true)}
              className="relative text-text-secondary hover:text-text transition-colors"
              title="Notifications"
            >
              <motion.div
                animate={
                  bellPulse
                    ? { scale: [1, 1.25, 0.9, 1.15, 1], rotate: [0, -12, 10, -8, 0] }
                    : { scale: 1, rotate: 0 }
                }
                transition={{ duration: 0.9, ease: "easeInOut" }}
              >
                <Bell className="w-4 h-4" />
              </motion.div>
              {notifCount > 0 && (
                <motion.span
                  key={notifCount}
                  initial={{ scale: 0.6, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 20 }}
                  className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent text-ink text-[10px] font-bold flex items-center justify-center"
                >
                  {notifCount > 9 ? "9+" : notifCount}
                </motion.span>
              )}
            </button>
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-info/20 to-accent/20 flex items-center justify-center">
              <span className="font-display text-xs font-bold text-text">
                {email[0]?.toUpperCase() || "P"}
              </span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
