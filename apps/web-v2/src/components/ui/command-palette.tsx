"use client";

import { Command } from "cmdk";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Building2,
  Megaphone,
  Sparkles,
  Share2,
  BarChart3,
  FileText,
  Store,
  BookOpen,
  Settings,
  Users,
  Search,
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

const COMMANDS = [
  { id: "dashboard", label: "Mission Control", icon: LayoutDashboard, path: "/app" },
  { id: "brands", label: "Brands", icon: Building2, path: "/app/brands" },
  { id: "campaigns", label: "Campaign Studio", icon: Megaphone, path: "/app/campaigns" },
  { id: "creative", label: "Creative AI", icon: Sparkles, path: "/app/creative" },
  { id: "video", label: "AI Video Studio", icon: Video, path: "/app/video" },
  { id: "images", label: "AI Image Studio", icon: ImageIcon, path: "/app/images" },
  { id: "design", label: "Design Studio", icon: Palette, path: "/app/design" },
  { id: "channels", label: "Channels", icon: Share2, path: "/app/channels" },
  { id: "calendar", label: "Content Calendar", icon: CalIcon, path: "/app/calendar" },
  { id: "bio", label: "Link-in-Bio", icon: LinkIcon, path: "/app/bio" },
  { id: "analytics", label: "Analytics", icon: BarChart3, path: "/app/analytics" },
  { id: "reports", label: "Reports", icon: FileText, path: "/app/reports" },
  { id: "listening", label: "Social Listening", icon: Radio, path: "/app/listening" },
  { id: "reviews", label: "Review Management", icon: Star, path: "/app/reviews" },
  { id: "influencers", label: "Influencer Marketing", icon: UserPlus, path: "/app/influencers" },
  { id: "advocacy", label: "Employee Advocacy", icon: Users, path: "/app/advocacy" },
  { id: "shop", label: "E-Commerce", icon: ShoppingBag, path: "/app/shop" },
  { id: "audience", label: "Audience Builder", icon: Users, path: "/app/audience" },
  { id: "marketplace", label: "Marketplace", icon: Store, path: "/app/marketplace" },
  { id: "knowledge", label: "Knowledge Base", icon: BookOpen, path: "/app/knowledge" },
  { id: "settings", label: "Settings", icon: Settings, path: "/app/settings" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  function runCommand(path: string) {
    router.push(path);
    setOpen(false);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh] px-4"
          onClick={() => setOpen(false)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-lg glass-strong rounded-2xl shadow-3d-xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <Command className="p-2">
              <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/[0.06]">
                <Search className="w-4 h-4 text-text-muted" />
                <Command.Input
                  placeholder="Search or jump to..."
                  className="flex-1 bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
                  autoFocus
                />
                <kbd className="font-mono text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-white/[0.04]">
                  ESC
                </kbd>
              </div>
              <Command.List className="max-h-[400px] overflow-auto p-2">
                <Command.Empty className="py-8 text-center text-sm text-text-muted">
                  No results found.
                </Command.Empty>
                <Command.Group heading="Navigate" className="text-text-muted">
                  {COMMANDS.map((cmd) => (
                    <Command.Item
                      key={cmd.id}
                      value={cmd.label}
                      onSelect={() => runCommand(cmd.path)}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text cursor-pointer aria-selected:bg-white/[0.04] aria-selected:text-text transition-colors"
                    >
                      <cmd.icon className="w-4 h-4 text-text-secondary" />
                      {cmd.label}
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
