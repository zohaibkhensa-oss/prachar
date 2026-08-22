"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Share2,
  Youtube,
  Instagram,
  Facebook,
  Linkedin,
  Twitter,
  MessageCircle,
  Send,
  Rss,
  Globe,
  Search,
  MoreVertical,
  RefreshCw,
  Pause,
  Unlink,
  Eye,
  Check,
  AlertTriangle,
  Users,
  DollarSign,
  TrendingUp,
  Zap,
  Plus,
} from "lucide-react";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/* ────────────────────────────── Types & mock data ────────────────────────────── */

type ChannelStatus = "connected" | "disconnected" | "warning" | "error";

type Channel = {
  id: string;
  name: string;
  icon: typeof Globe;
  color: string;
  status: ChannelStatus;
  account?: string;
  spend30d?: number;
  reach?: number;
  followers?: number;
  lastSync?: string;
  campaigns?: number;
  health?: "good" | "fair" | "poor";
  aiStatus?: string;
  oauthNote?: string;
};

const CHANNELS: Channel[] = [
  {
    id: "google",
    name: "Google Ads",
    icon: Search,
    color: "#3B82F6",
    status: "connected",
    account: "aurora@curv.app",
    spend30d: 184200,
    reach: 1240000,
    followers: 0,
    lastSync: "2 min ago",
    campaigns: 14,
    health: "good",
    aiStatus: "Optimizing 3 campaigns",
  },
  {
    id: "youtube",
    name: "YouTube",
    icon: Youtube,
    color: "#EF4444",
    status: "connected",
    account: "Aurora Skincare",
    spend30d: 92800,
    reach: 890000,
    followers: 124300,
    lastSync: "5 min ago",
    campaigns: 8,
    health: "good",
    aiStatus: "2 variants in review",
  },
  {
    id: "instagram",
    name: "Instagram",
    icon: Instagram,
    color: "#FFD400",
    status: "connected",
    account: "@aurora.skincare",
    spend30d: 64500,
    reach: 720000,
    followers: 89200,
    lastSync: "1 min ago",
    campaigns: 11,
    health: "good",
    aiStatus: "Auto-posting enabled",
  },
  {
    id: "facebook",
    name: "Facebook",
    icon: Facebook,
    color: "#3B82F6",
    status: "warning",
    account: "Aurora Skincare Official",
    spend30d: 41200,
    reach: 510000,
    followers: 67800,
    lastSync: "34 min ago",
    campaigns: 6,
    health: "fair",
    aiStatus: "Token expires in 3 days",
  },
  {
    id: "tiktok",
    name: "TikTok",
    icon: Zap,
    color: "#22C55E",
    status: "connected",
    account: "@aurora.glow",
    spend30d: 38900,
    reach: 1100000,
    followers: 234500,
    lastSync: "8 min ago",
    campaigns: 9,
    health: "good",
    aiStatus: "Trending sound detected",
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    icon: Linkedin,
    color: "#3B82F6",
    status: "connected",
    account: "Aurora Skincare Pvt Ltd",
    spend30d: 22400,
    reach: 180000,
    followers: 12400,
    lastSync: "12 min ago",
    campaigns: 4,
    health: "good",
    aiStatus: "B2B audience matched",
  },
  {
    id: "x",
    name: "X (Twitter)",
    icon: Twitter,
    color: "#94A3B8",
    status: "error",
    account: "@aurora_skin",
    spend30d: 8200,
    reach: 92000,
    followers: 18900,
    lastSync: "2 hr ago",
    campaigns: 3,
    health: "poor",
    aiStatus: "API rate limit exceeded",
  },
  {
    id: "pinterest",
    name: "Pinterest",
    icon: Rss,
    color: "#EF4444",
    status: "disconnected",
    oauthNote: "Connect via Pinterest Business OAuth to sync boards, pins, and ad performance.",
  },
  {
    id: "whatsapp",
    name: "WhatsApp Business",
    icon: MessageCircle,
    color: "#22C55E",
    status: "disconnected",
    oauthNote: "Connect via Meta Business Suite to enable WhatsApp Business API messaging.",
  },
  {
    id: "telegram",
    name: "Telegram",
    icon: Send,
    color: "#3B82F6",
    status: "disconnected",
    oauthNote: "Connect your Telegram Bot token to broadcast and track channel campaigns.",
  },
  {
    id: "line",
    name: "LINE",
    icon: MessageCircle,
    color: "#22C55E",
    status: "disconnected",
    oauthNote: "Connect via LINE Official Account to reach Japan, Taiwan, and Thailand audiences.",
  },
  {
    id: "vk",
    name: "VK",
    icon: Globe,
    color: "#3B82F6",
    status: "disconnected",
    oauthNote: "Connect via VK OAuth to target CIS-region audiences with native ad formats.",
  },
  {
    id: "reddit",
    name: "Reddit",
    icon: Rss,
    color: "#EF4444",
    status: "disconnected",
    oauthNote: "Connect via Reddit Ads API to run promoted posts in niche communities.",
  },
  {
    id: "naver",
    name: "Naver",
    icon: Search,
    color: "#22C55E",
    status: "disconnected",
    oauthNote: "Connect via Naver Search Ads to reach Korean search audiences.",
  },
];

const FILTERS = [
  { id: "all", label: "All" },
  { id: "connected", label: "Connected" },
  { id: "attention", label: "Needs Attention" },
  { id: "available", label: "Available" },
];

const HEALTH_DOT = {
  good: "bg-success shadow-glow-green",
  fair: "bg-accent",
  poor: "bg-danger shadow-glow-red",
};

const STATUS_BADGE: Record<ChannelStatus, { label: string; cls: string }> = {
  connected: { label: "Connected", cls: "badge-success" },
  disconnected: { label: "Not Connected", cls: "badge-neutral" },
  warning: { label: "Action Needed", cls: "badge-warning" },
  error: { label: "Error", cls: "badge-danger" },
};

function fmtINR(n: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
function fmtCompact(n: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/* ────────────────────────────── Page ────────────────────────────── */

export default function ChannelsPage() {
  const [filter, setFilter] = useState("all");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const connected = CHANNELS.filter((c) => c.status === "connected");
  const totalReach = connected.reduce((s, c) => s + (c.reach ?? 0), 0);
  const totalFollowers = connected.reduce((s, c) => s + (c.followers ?? 0), 0);
  const totalSpend = connected.reduce((s, c) => s + (c.spend30d ?? 0), 0);

  const filtered = CHANNELS.filter((c) => {
    if (filter === "all") return true;
    if (filter === "connected") return c.status === "connected";
    if (filter === "attention") return c.status === "warning" || c.status === "error";
    if (filter === "available") return c.status === "disconnected";
    return true;
  });

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-text flex items-center gap-3">
            <Share2 className="w-7 h-7 text-accent" />
            Channels
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Manage every advertising channel from one command center.
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Add Channel
        </button>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Metric label="Connected" value={connected.length} suffix={` / ${CHANNELS.length}`} icon={<Share2 className="w-4 h-4" />} accent="success" />
        <Metric label="Total Reach" value={totalReach} format="compact" icon={<Users className="w-4 h-4" />} accent="info" />
        <Metric label="Total Followers" value={totalFollowers} format="compact" icon={<TrendingUp className="w-4 h-4" />} accent="accent" />
        <Metric label="Spend (30d)" value={totalSpend} format="currency" icon={<DollarSign className="w-4 h-4" />} accent="default" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              "px-3.5 py-1.5 rounded-full text-xs font-medium transition-all",
              filter === f.id
                ? "bg-accent text-white"
                : "bg-white/[0.04] text-text-secondary hover:text-text",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Channel grid */}
      <motion.div layout className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        <AnimatePresence mode="popLayout">
          {filtered.map((c, i) => (
            <motion.div
              key={c.id}
              layout
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ delay: i * 0.04, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            >
              <Card3D className="h-full" glow={c.status === "connected"}>
                {/* Top: icon + name + status */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${c.color}15` }}
                    >
                      <c.icon className="w-5 h-5" style={{ color: c.color }} />
                    </div>
                    <div>
                      <div className="font-display text-base font-semibold text-text">{c.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {c.status === "connected" && c.health && (
                          <span className={cn("w-1.5 h-1.5 rounded-full", HEALTH_DOT[c.health])} />
                        )}
                        <span className={cn("badge text-[10px]", STATUS_BADGE[c.status].cls)}>
                          {STATUS_BADGE[c.status].label}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="relative">
                    <button
                      onClick={() => setMenuOpen(menuOpen === c.id ? null : c.id)}
                      className="w-8 h-8 rounded-lg hover:bg-white/[0.06] flex items-center justify-center text-text-muted transition-colors"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    <AnimatePresence>
                      {menuOpen === c.id && (
                        <motion.div
                          initial={{ opacity: 0, y: -4, scale: 0.96 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -4, scale: 0.96 }}
                          className="absolute right-0 top-9 z-20 glass-strong rounded-lg p-1.5 w-44 shadow-3d"
                        >
                          {c.status === "connected" ? (
                            <>
                              <MenuItem icon={<RefreshCw className="w-3.5 h-3.5" />} label="Sync Now" />
                              <MenuItem icon={<Pause className="w-3.5 h-3.5" />} label="Pause" />
                              <MenuItem icon={<Eye className="w-3.5 h-3.5" />} label="View Campaigns" />
                              <div className="h-px bg-white/[0.06] my-1" />
                              <MenuItem icon={<Unlink className="w-3.5 h-3.5" />} label="Disconnect" danger />
                            </>
                          ) : (
                            <MenuItem icon={<Share2 className="w-3.5 h-3.5" />} label="Connect" />
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {c.status === "connected" || c.status === "warning" || c.status === "error" ? (
                  <>
                    {/* Account */}
                    <div className="mb-3">
                      <span className="label-field">Account</span>
                      <div className="text-sm text-text font-medium truncate">{c.account}</div>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-3 gap-3 mb-3 py-3 border-y border-white/[0.04]">
                      <Stat label="Spend 30d" value={fmtINR(c.spend30d ?? 0)} />
                      <Stat label="Reach" value={fmtCompact(c.reach ?? 0)} />
                      <Stat label="Followers" value={c.followers ? fmtCompact(c.followers) : "—"} />
                    </div>

                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <Stat label="Campaigns" value={String(c.campaigns ?? 0)} />
                      <Stat label="Last Sync" value={c.lastSync ?? "—"} />
                    </div>

                    {/* AI status */}
                    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-white/[0.03]">
                      {c.status === "error" ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-danger shrink-0" />
                      ) : c.status === "warning" ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-accent shrink-0" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0 animate-pulse" />
                      )}
                      <span className="text-xs text-text-secondary truncate">{c.aiStatus}</span>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Disconnected state */}
                    <p className="text-xs text-text-secondary leading-relaxed mb-4 min-h-[60px]">
                      {c.oauthNote}
                    </p>
                    <button className="btn-secondary w-full flex items-center justify-center gap-2">
                      <Share2 className="w-4 h-4" /> Connect
                    </button>
                  </>
                )}
              </Card3D>
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Needs attention section */}
      <div className="mt-10">
        <SectionHeader
          title="Needs Attention"
          subtitle="Channels requiring manual intervention"
          icon={<AlertTriangle className="w-4 h-4 text-accent" />}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CHANNELS.filter((c) => c.status === "warning" || c.status === "error").map((c) => (
            <Card key={c.id} className="border-l-2 border-l-accent/40">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-4 h-4 text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-display text-sm font-medium text-text">{c.name}</div>
                  <p className="text-xs text-text-secondary mt-1">{c.aiStatus}</p>
                  <div className="flex gap-2 mt-3">
                    <button className="btn-primary text-xs px-3 py-1.5">Resolve</button>
                    <button className="btn-ghost text-xs px-3 py-1.5">Dismiss</button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
          {CHANNELS.filter((c) => c.status === "warning" || c.status === "error").length === 0 && (
            <Card className="flex items-center gap-3">
              <Check className="w-5 h-5 text-success" />
              <span className="text-sm text-text-secondary">All channels are healthy.</span>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="label-field text-[9px]">{label}</span>
      <span className="font-mono text-xs font-medium text-text truncate">{value}</span>
    </div>
  );
}

function MenuItem({ icon, label, danger }: { icon: React.ReactNode; label: string; danger?: boolean }) {
  return (
    <button
      className={cn(
        "w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-xs transition-colors text-left",
        danger
          ? "text-danger hover:bg-danger/10"
          : "text-text-secondary hover:text-text hover:bg-white/[0.06]",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
