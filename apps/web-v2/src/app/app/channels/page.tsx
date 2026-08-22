"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
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
  Check,
  AlertTriangle,
  Users,
  DollarSign,
  TrendingUp,
  Zap,
  Loader2,
} from "lucide-react";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { SectionHeader } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";

/* ────────────────────────────── Types ────────────────────────────── */

interface Connection {
  id: string;
  channel: string;
  status: string;
  brand_id: string;
  created_at: string;
}

type ChannelStatus = "connected" | "disconnected" | "warning" | "error";

type Channel = {
  id: string;
  name: string;
  icon: typeof Globe;
  color: string;
  status: ChannelStatus;
  account?: string;
  lastSync?: string;
  health?: "good" | "fair" | "poor";
  aiStatus?: string;
  oauthNote?: string;
};

/* ────────────────────────────── Supported channels ────────────────────────────── */

const SUPPORTED_CHANNELS: { id: string; name: string; icon: typeof Globe; color: string; oauthNote: string }[] = [
  { id: "google", name: "Google Ads", icon: Search, color: "#3B82F6", oauthNote: "Connect via Google Ads OAuth to sync campaigns and performance." },
  { id: "youtube", name: "YouTube", icon: Youtube, color: "#EF4444", oauthNote: "Connect via Google OAuth to manage your YouTube channel." },
  { id: "instagram", name: "Instagram", icon: Instagram, color: "#E879F9", oauthNote: "Connect via Meta Business Suite to publish and track Instagram." },
  { id: "facebook", name: "Facebook", icon: Facebook, color: "#3B82F6", oauthNote: "Connect via Meta Business Suite to manage Facebook pages and ads." },
  { id: "tiktok", name: "TikTok", icon: Zap, color: "#22C55E", oauthNote: "Connect via TikTok for Business OAuth to post and track content." },
  { id: "linkedin", name: "LinkedIn", icon: Linkedin, color: "#3B82F6", oauthNote: "Connect via LinkedIn OAuth to publish and track professional content." },
  { id: "x", name: "X (Twitter)", icon: Twitter, color: "#94A3B8", oauthNote: "Connect via X API to post and monitor engagement." },
  { id: "pinterest", name: "Pinterest", icon: Rss, color: "#EF4444", oauthNote: "Connect via Pinterest Business OAuth to sync boards, pins, and ad performance." },
  { id: "whatsapp", name: "WhatsApp Business", icon: MessageCircle, color: "#22C55E", oauthNote: "Connect via Meta Business Suite to enable WhatsApp Business API messaging." },
  { id: "telegram", name: "Telegram", icon: Send, color: "#3B82F6", oauthNote: "Connect your Telegram Bot token to broadcast and track channel campaigns." },
  { id: "line", name: "LINE", icon: MessageCircle, color: "#22C55E", oauthNote: "Connect via LINE Official Account to reach Japan, Taiwan, and Thailand audiences." },
  { id: "vk", name: "VK", icon: Globe, color: "#3B82F6", oauthNote: "Connect via VK OAuth to target CIS-region audiences with native ad formats." },
  { id: "reddit", name: "Reddit", icon: Rss, color: "#EF4444", oauthNote: "Connect via Reddit Ads API to run promoted posts in niche communities." },
  { id: "naver", name: "Naver", icon: Search, color: "#22C55E", oauthNote: "Connect via Naver Search Ads to reach Korean search audiences." },
];

const CHANNEL_MAP = Object.fromEntries(SUPPORTED_CHANNELS.map((c) => [c.id, c]));

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

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function mapStatus(raw: string): ChannelStatus {
  const s = raw.toLowerCase();
  if (s === "active" || s === "connected" || s === "ok") return "connected";
  if (s === "warning" || s === "expiring") return "warning";
  if (s === "error" || s === "failed" || s === "disconnected_error") return "error";
  return "connected";
}

/* ────────────────────────────── Page ────────────────────────────── */

export default function ChannelsPage() {
  const [filter, setFilter] = useState("all");
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectingChannel, setConnectingChannel] = useState<string | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const { brand } = useActiveBrand();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const qs = brand?.id ? `?brand_id=${encodeURIComponent(brand.id)}` : "";
    apiGet<Connection[]>(`/connections${qs}`)
      .then((data) => {
        if (cancelled) return;
        setConnections(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof ApiError ? err.message : "Failed to load channels";
        setError(msg);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [brand?.id]);

  // Initiate OAuth flow for a channel — calls the backend which returns the
  // provider's auth URL, then redirects the browser there.
  async function handleConnect(channel: string) {
    if (!brand) return;
    setConnectingChannel(channel);
    setConnectError(null);
    try {
      const res = await apiPost<{ auth_url: string; channel: string }>(
        `/connections/${channel}/oauth?brand_id=${encodeURIComponent(brand.id)}`,
      );
      if (res.auth_url) {
        window.location.href = res.auth_url;
      } else {
        setConnectError("No auth URL returned. Please try again.");
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to start OAuth. Please try again.";
      setConnectError(msg);
    } finally {
      setConnectingChannel(null);
    }
  }

  // Build the channel list from real connections + available (not-connected) channels
  const channels: Channel[] = (() => {
    // Treat null (loading/error) as empty — still show available channels
    const connList = connections ?? [];
    const connectedList: Channel[] = connList.map((conn) => {
      const meta = CHANNEL_MAP[conn.channel];
      const status = mapStatus(conn.status);
      return {
        id: conn.id,
        name: meta?.name ?? conn.channel,
        icon: meta?.icon ?? Globe,
        color: meta?.color ?? "#94A3B8",
        status,
        account: conn.channel,
        lastSync: timeAgo(conn.created_at),
        health: status === "error" ? "poor" : status === "warning" ? "fair" : "good",
        aiStatus:
          status === "error"
            ? "Connection error — please reconnect"
            : status === "warning"
              ? "Token may expire soon"
              : "Syncing normally",
      };
    });
    const connectedIds = new Set(connList.map((c) => c.channel));
    const availableList: Channel[] = SUPPORTED_CHANNELS.filter(
      (s) => !connectedIds.has(s.id),
    ).map((s) => ({
      id: s.id,
      name: s.name,
      icon: s.icon,
      color: s.color,
      status: "disconnected",
      oauthNote: s.oauthNote,
    }));
    return [...connectedList, ...availableList];
  })();

  const connected = channels.filter((c) => c.status === "connected");
  const attention = channels.filter((c) => c.status === "warning" || c.status === "error");
  const available = channels.filter((c) => c.status === "disconnected");

  const filtered = channels.filter((c) => {
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
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Metric label="Connected" value={connected.length} suffix={` / ${SUPPORTED_CHANNELS.length}`} icon={<Share2 className="w-4 h-4" />} accent="success" />
        <Metric label="Needs Attention" value={attention.length} icon={<AlertTriangle className="w-4 h-4" />} accent="accent" />
        <Metric label="Available" value={available.length} icon={<Globe className="w-4 h-4" />} accent="info" />
        <Metric label="Total Channels" value={SUPPORTED_CHANNELS.length} icon={<TrendingUp className="w-4 h-4" />} accent="default" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto scrollbar-none">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              "px-3.5 py-2 min-h-[36px] rounded-full text-xs font-medium transition-all whitespace-nowrap",
              filter === f.id
                ? "bg-accent text-white"
                : "bg-white/[0.04] text-text-secondary hover:text-text",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Connect error banner */}
      {connectError && (
        <div className="mb-6 rounded-xl border border-danger/30 bg-danger/[0.06] p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-danger shrink-0" />
          <span className="text-sm text-text-secondary flex-1">{connectError}</span>
          <button
            onClick={() => setConnectError(null)}
            className="text-xs text-text-muted hover:text-text transition"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Body: loading / error / empty / grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.06] bg-glass p-5 animate-pulse">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-11 h-11 rounded-xl bg-white/[0.06]" />
                <div className="flex-1">
                  <div className="h-4 w-32 rounded bg-white/[0.06] mb-2" />
                  <div className="h-3 w-20 rounded bg-white/[0.04]" />
                </div>
              </div>
              <div className="h-3 w-full rounded bg-white/[0.04] mb-2" />
              <div className="h-3 w-2/3 rounded bg-white/[0.04] mb-4" />
              <div className="grid grid-cols-3 gap-3">
                <div className="h-10 rounded bg-white/[0.04]" />
                <div className="h-10 rounded bg-white/[0.04]" />
                <div className="h-10 rounded bg-white/[0.04]" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <Card3D className="text-center py-16">
          <AlertTriangle className="w-8 h-8 text-danger mx-auto mb-3" />
          <p className="text-text font-medium mb-1">Couldn&apos;t load your channels.</p>
          <p className="text-sm text-text-secondary">Please try again.</p>
        </Card3D>
      ) : channels.length === 0 ? (
        <Card3D className="text-center py-16">
          <Share2 className="w-8 h-8 text-text-secondary mx-auto mb-3" />
          <p className="text-text font-medium mb-1">No channels connected yet.</p>
          <p className="text-sm text-text-secondary mb-4">
            Go to Integrations to connect your first channel.
          </p>
          <Link
            href="/app/integrations"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 transition"
          >
            Go to Integrations
          </Link>
        </Card3D>
      ) : filtered.length === 0 ? (
        <Card3D className="text-center py-16">
          <Check className="w-8 h-8 text-success mx-auto mb-3" />
          <p className="text-text font-medium mb-1">Nothing here right now.</p>
          <p className="text-sm text-text-secondary">Try a different filter.</p>
        </Card3D>
      ) : (
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
                  </div>

                  {c.status === "connected" || c.status === "warning" || c.status === "error" ? (
                    <>
                      {/* Account */}
                      <div className="mb-3">
                        <span className="label-field">Account</span>
                        <div className="text-sm text-text font-medium truncate">{c.account}</div>
                      </div>

                      {/* Last sync */}
                      <div className="grid grid-cols-2 gap-3 mb-3 py-3 border-y border-white/[0.04]">
                        <Stat label="Last Sync" value={c.lastSync ?? "—"} />
                        <Stat label="Status" value={STATUS_BADGE[c.status].label} />
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
                      <button
                        onClick={() => handleConnect(c.id)}
                        disabled={connectingChannel === c.id}
                        className={cn(
                          "inline-flex items-center gap-2 px-3 py-2 min-h-[36px] rounded-lg text-xs font-medium transition",
                          connectingChannel === c.id
                            ? "bg-white/[0.04] text-text-muted cursor-wait"
                            : "bg-white/[0.06] text-text hover:bg-accent hover:text-bg",
                        )}
                      >
                        {connectingChannel === c.id ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Connecting…
                          </>
                        ) : (
                          <>
                            <Zap className="w-3.5 h-3.5" />
                            Connect
                          </>
                        )}
                      </button>
                    </>
                  )}
                </Card3D>
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Needs attention section */}
      {!loading && !error && (
        <div className="mt-10">
          <SectionHeader
            title="Needs Attention"
            subtitle="Channels requiring manual intervention"
            icon={<AlertTriangle className="w-4 h-4 text-accent" />}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {attention.map((c) => (
              <Card key={c.id} className="border-l-2 border-l-accent/40">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                    <AlertTriangle className="w-4 h-4 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-display text-sm font-medium text-text">{c.name}</div>
                    <p className="text-xs text-text-secondary mt-1">{c.aiStatus}</p>
                  </div>
                </div>
              </Card>
            ))}
            {attention.length === 0 && (
              <Card className="flex items-center gap-3">
                <Check className="w-5 h-5 text-success" />
                <span className="text-sm text-text-secondary">All channels are healthy.</span>
              </Card>
            )}
          </div>
        </div>
      )}
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
