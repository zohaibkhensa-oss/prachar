"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Megaphone, Sparkles, CircleCheckBig, TrendingUp,
  Video, Share2, Calendar, Settings, Menu,
  LogOut, Plus, MessageSquare, PanelLeftClose, PanelLeftOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getToken, clearToken } from "@/lib/auth";
import { apiGet } from "@/lib/api";
import { useRouter } from "next/navigation";
import { CurvMark } from "./CurvMark";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const WORKSPACE_NAV: NavItem[] = [
  { label: "Campaigns", href: "/app/campaigns", icon: Megaphone },
  { label: "Creative Studio", href: "/app/creative-studio", icon: Sparkles },
  { label: "AI Video", href: "/app/video", icon: Video },
  { label: "Review", href: "/app/review", icon: CircleCheckBig },
  { label: "Performance", href: "/app/performance", icon: TrendingUp },
  { label: "Connections", href: "/app/connections", icon: Share2 },
  { label: "Calendar", href: "/app/calendar", icon: Calendar },
];

const SYSTEM_NAV: NavItem[] = [
  { label: "Settings", href: "/app/settings", icon: Settings },
];

interface ChatSession {
  session_id: string;
  title: string;
  preview: string;
  timestamp: string;
  created_at: string;
}

function groupByDate(sessions: ChatSession[]): { label: string; items: ChatSession[] }[] {
  const groups: Record<string, ChatSession[]> = {};
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  for (const s of sessions) {
    const date = new Date(s.timestamp || s.created_at);
    const label =
      date >= today ? "Today"
      : date >= yesterday ? "Yesterday"
      : date >= weekAgo ? "Previous 7 days"
      : "Older";
    (groups[label] ??= []).push(s);
  }
  return ["Today", "Yesterday", "Previous 7 days", "Older"]
    .filter((l) => groups[l])
    .map((l) => ({ label: l, items: groups[l]! }));
}

/**
 * Gemini-style sidebar — expanded by default (264px), collapsible to a
 * 72px rail. Owns: New chat, recent conversations, workspace nav, theme
 * toggle, account.
 */
export function Sidebar({ mobileOpen, onMobileClose }: { mobileOpen?: boolean; onMobileClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [email, setEmail] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem("prachar_email");
    if (stored) setEmail(stored);
    const savedCollapsed = localStorage.getItem("curv_sidebar_collapsed");
    if (savedCollapsed === "1") setCollapsed(true);
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiGet<{ sessions: ChatSession[] }>("/runtime/sessions?limit=25");
      setSessions(data.sessions || []);
    } catch {
      /* supplementary nav — silent */
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    const refresh = () => fetchSessions();
    window.addEventListener("curv:sessions-changed", refresh);
    return () => window.removeEventListener("curv:sessions-changed", refresh);
  }, [fetchSessions]);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      localStorage.setItem("curv_sidebar_collapsed", c ? "0" : "1");
      return !c;
    });
  };

  // Close mobile drawer on route change
  useEffect(() => {
    if (onMobileClose) onMobileClose();
  }, [pathname, onMobileClose]);

  const handleNewChat = () => {
    window.dispatchEvent(new CustomEvent("curv:new-chat"));
    if (pathname !== "/app") router.push("/app");
    if (onMobileClose) onMobileClose();
  };

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  const grouped = groupByDate(sessions);

  const navLink = (item: NavItem) => {
    const active = pathname === item.href || pathname.startsWith(item.href + "/");
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        title={collapsed ? item.label : undefined}
        className={cn(
          "flex items-center gap-3 rounded-full px-3.5 py-2 text-sm transition-colors",
          active
            ? "bg-bg-hover text-text font-medium"
            : "text-text-secondary hover:bg-bg-hover hover:text-text",
          collapsed && "justify-center px-0",
        )}
      >
        <Icon className="w-[18px] h-[18px] shrink-0" />
        {!collapsed && <span className="truncate">{item.label}</span>}
      </Link>
    );
  };

  const sidebarContent = (
    <>
      {/* Header: menu + wordmark */}
      <div className="flex items-center gap-1 px-3 h-14 shrink-0">
        <button
          onClick={toggleCollapsed}
          className="hidden lg:flex p-2 rounded-full text-text-secondary hover:text-text hover:bg-bg-hover transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
        </button>
        <button
          onClick={onMobileClose}
          className="lg:hidden p-2 rounded-full text-text-secondary hover:text-text hover:bg-bg-hover transition-colors"
          aria-label="Close menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        {!collapsed && (
          <Link href="/app" className="flex items-center gap-2 overflow-hidden">
            <CurvMark size={26} variant="mark" />
            <span
              className="font-display text-sm font-bold"
              style={{
                background: "linear-gradient(135deg, #8B5CF6, #EC4899, #F97316)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              CURV AI
            </span>
          </Link>
        )}
      </div>

      {/* New chat */}
      <div className={cn("px-3 pt-1 pb-2 shrink-0", collapsed && "px-2")}>
        <button
          onClick={handleNewChat}
          title={collapsed ? "New chat" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-full bg-bg-card hover:bg-bg-hover text-text text-sm font-medium transition-colors",
            collapsed ? "justify-center w-12 h-12 mx-auto" : "px-4 py-3 w-full",
          )}
        >
          <Plus className="w-5 h-5 shrink-0" />
          {!collapsed && "New chat"}
        </button>
      </div>

      {/* Scrollable middle: recents + workspace nav */}
      <div className="flex-1 overflow-y-auto scrollbar-none px-3 pb-2">
        {/* Recent conversations (expanded only) */}
        {!collapsed && grouped.length > 0 && (
          <div className="pt-2">
            <div className="px-3.5 pb-1 text-[11px] font-medium text-text-muted">Recent</div>
            {grouped.slice(0, 2).map((group) => (
              <div key={group.label} className="mb-1">
                {group.items.slice(0, 5).map((s) => (
                  <button
                    key={s.session_id}
                    onClick={() => {
                      router.push(`/app?session=${s.session_id}` as never);
                      if (onMobileClose) onMobileClose();
                    }}
                    title={s.title || "Conversation"}
                    className="w-full flex items-center gap-3 text-left px-3.5 py-2 rounded-full text-[13px] text-text-secondary hover:bg-bg-hover hover:text-text transition-colors truncate"
                  >
                    <MessageSquare className="w-4 h-4 shrink-0 opacity-50" />
                    <span className="truncate">{s.title || "New conversation"}</span>
                  </button>
                ))}
              </div>
            ))}
            <Link
              href="/app/chat-history"
              className="block px-3.5 py-1.5 text-[11px] text-text-muted hover:text-text transition-colors"
            >
              All conversations →
            </Link>
          </div>
        )}

        {/* Workspace nav */}
        <div className="pt-3">
          {!collapsed && (
            <div className="px-3.5 pb-1 text-[11px] font-medium text-text-muted">Workspace</div>
          )}
          <div className="space-y-0.5">{WORKSPACE_NAV.map(navLink)}</div>
        </div>

        <div className="pt-3">
          <div className="space-y-0.5">{SYSTEM_NAV.map(navLink)}</div>
        </div>
      </div>

      {/* Bottom: account */}
      <div className={cn("p-3 border-t border-line/5 flex items-center gap-1 shrink-0", collapsed && "flex-col")}>
        {!collapsed && <div className="flex-1 min-w-0 px-1 text-[11px] text-text-muted truncate">{email}</div>}
        <button
          onClick={handleLogout}
          title="Log out"
          className="p-2 rounded-lg text-text-secondary hover:text-danger hover:bg-bg-hover transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden lg:flex sticky top-0 z-30 h-screen bg-bg-surface flex-col transition-all duration-300 ease-out-quart shrink-0",
          collapsed ? "w-[72px]" : "w-[264px]",
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
              className="lg:hidden fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="lg:hidden fixed top-0 left-0 z-[70] h-screen w-[280px] max-w-[85vw] bg-bg-surface flex flex-col overflow-y-auto"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
