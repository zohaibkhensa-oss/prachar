"use client";

import { useState, useEffect, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { clearToken, getToken } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { CommandPalette } from "@/components/ui/command-palette";
import { VoiceAssistant } from "@/components/VoiceAssistant";
import {
  LayoutDashboard,
  Building2,
  Megaphone,
  Sparkles,
  Share2,
  BarChart3,
  FileText,
  Users,
  Store,
  BookOpen,
  Settings,
  ChevronLeft,
  Bell,
  Search,
  LogOut,
  Zap,
  CircleDot,
  Menu,
  X,
  Video,
  Image as ImageIcon,
  Radio,
  Star,
  Calendar as CalIcon,
  Link as LinkIcon,
  UserPlus,
  ShoppingBag,
  Palette,
} from "lucide-react";

const NAV_ITEMS = [
  { section: "Overview", items: [
    { label: "Mission Control", icon: LayoutDashboard, path: "/app" },
  ]},
  { section: "Workspace", items: [
    { label: "Brands", icon: Building2, path: "/app/brands" },
    { label: "Campaign Studio", icon: Megaphone, path: "/app/campaigns" },
    { label: "Creative AI", icon: Sparkles, path: "/app/creative" },
    { label: "AI Video Studio", icon: Video, path: "/app/video" },
    { label: "AI Image Studio", icon: ImageIcon, path: "/app/images" },
    { label: "Design Studio", icon: Palette, path: "/app/design" },
  ]},
  { section: "Distribution", items: [
    { label: "Channels", icon: Share2, path: "/app/channels" },
    { label: "Content Calendar", icon: CalIcon, path: "/app/calendar" },
    { label: "Link-in-Bio", icon: LinkIcon, path: "/app/bio" },
    { label: "Audience Builder", icon: Users, path: "/app/audience" },
  ]},
  { section: "Intelligence", items: [
    { label: "Analytics", icon: BarChart3, path: "/app/analytics" },
    { label: "Reports", icon: FileText, path: "/app/reports" },
    { label: "Social Listening", icon: Radio, path: "/app/listening" },
    { label: "Review Management", icon: Star, path: "/app/reviews" },
  ]},
  { section: "Growth", items: [
    { label: "Influencer Marketing", icon: UserPlus, path: "/app/influencers" },
    { label: "Employee Advocacy", icon: Users, path: "/app/advocacy" },
    { label: "E-Commerce", icon: ShoppingBag, path: "/app/shop" },
  ]},
  { section: "Resources", items: [
    { label: "Marketplace", icon: Store, path: "/app/marketplace" },
    { label: "Knowledge Base", icon: BookOpen, path: "/app/knowledge" },
    { label: "Settings", icon: Settings, path: "/app/settings" },
  ]},
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setEmail(window.localStorage.getItem("prachar_email") ?? "you@prachar.app");
    setReady(true);
  }, [router]);

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
          {NAV_ITEMS.map((section) => (
            <div key={section.section}>
              {!collapsed && (
                <div className="px-3 mb-1.5 label-field text-[9px]">{section.section}</div>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const active = pathname === item.path || pathname.startsWith(item.path + "/");
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 group relative",
                        active
                          ? "bg-accent/10 text-accent"
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
                      <item.icon className="w-4 h-4 shrink-0" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* AI Status */}
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
                  AI Engine Online
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-muted">3 jobs running</span>
                <span className="font-mono text-[10px] text-accent">2,847 tokens</span>
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
            <button className="relative text-text-secondary hover:text-text transition-colors">
              <Bell className="w-4 h-4" />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-accent" />
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
