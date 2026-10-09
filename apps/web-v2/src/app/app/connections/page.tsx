"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertCircle, ChevronDown, ExternalLink, Link2,
  Loader2, MoreHorizontal, RefreshCw, Search, Unlink, X,
} from "lucide-react";
import { apiDelete, apiGet, apiPost, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Connection {
  id: string;
  brand_id: string;
  channel: string;
  status: string; // pending | active | expired | revoked
  expires_at: string | null;
  created_at: string | null;
  scopes: string[] | null;
  account_label: string | null;
}

interface RegistryEntry {
  channel: string;
  label: string;
  category: "social" | "advertising" | "messaging";
  oauth_channel: string | null;
  description: string;
  configured: boolean;
}

type UiState =
  | "connected"
  | "not_connected"
  | "connecting"
  | "reconnect_required"
  | "config_required"
  | "error";

const CATEGORY_LABELS: Record<string, string> = {
  all: "All Channels",
  social: "Social Media",
  advertising: "Advertising",
  messaging: "Messaging & Publishing",
};

// Platform letter-tile styling (recognizable brand colors)
const TILE: Record<string, string> = {
  instagram: "from-fuchsia-500 to-rose-500",
  facebook: "from-blue-600 to-blue-700",
  x: "from-zinc-700 to-zinc-900",
  linkedin: "from-sky-600 to-blue-700",
  youtube: "from-red-600 to-red-700",
  tiktok: "from-zinc-800 to-zinc-950",
  pinterest: "from-rose-600 to-red-600",
  reddit: "from-orange-500 to-orange-600",
  vk: "from-blue-500 to-sky-600",
  naver: "from-green-500 to-green-600",
  meta_ads: "from-blue-500 to-indigo-600",
  google_ads: "from-blue-500 to-green-600",
  linkedin_ads: "from-sky-600 to-blue-700",
  tiktok_ads: "from-zinc-800 to-zinc-950",
  x_ads: "from-zinc-700 to-zinc-900",
  microsoft_ads: "from-cyan-600 to-blue-600",
  whatsapp: "from-emerald-500 to-green-600",
  telegram: "from-sky-500 to-blue-500",
  line: "from-green-500 to-emerald-600",
  gmb: "from-blue-500 to-emerald-500",
  gsc: "from-blue-500 to-teal-500",
};

// Ads integrations are "connected" via their organic provider's connection.
const ADS_LINKED: Record<string, string[]> = {
  meta_ads: ["meta", "facebook"],
  google_ads: ["google"],
  linkedin_ads: ["linkedin"],
  tiktok_ads: ["tiktok"],
  x_ads: ["x"],
  microsoft_ads: [],
};

function tileFor(channel: string): { letter: string; gradient: string } {
  const g = TILE[channel] ?? "from-accent to-accent-dark";
  const key = channel.replace(/_ads$/, "").replace(/^gmb$/, "G").replace(/^gsc$/, "G");
  return { letter: (key[0] ?? "?").toUpperCase(), gradient: g };
}

function connUiState(entry: RegistryEntry, conn: Connection | undefined, connectingKey: string | null): UiState {
  if (connectingKey === entry.channel) return "connecting";
  if (conn) {
    const expired = conn.expires_at && new Date(conn.expires_at).getTime() < Date.now();
    if (conn.status === "active" && !expired) return "connected";
    if (conn.status === "expired" || conn.status === "revoked" || expired) return "reconnect_required";
    if (conn.status === "pending") return "reconnect_required";
  }
  return entry.configured ? "not_connected" : "config_required";
}

const STATE_BADGE: Record<UiState, { label: string; cls: string }> = {
  connected: { label: "Connected", cls: "bg-emerald-500/15 text-emerald-400" },
  not_connected: { label: "Not connected", cls: "bg-white/[0.06] text-text-secondary" },
  connecting: { label: "Connecting…", cls: "bg-accent/15 text-accent" },
  reconnect_required: { label: "Reconnect required", cls: "bg-amber-500/15 text-amber-400" },
  config_required: { label: "Configuration required", cls: "bg-amber-500/15 text-amber-300" },
  error: { label: "Connection error", cls: "bg-danger/15 text-danger" },
};

function timeAgo(iso: string | null): string | null {
  if (!iso) return null;
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ConnectionsPage() {
  const qc = useQueryClient();
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [statusOpen, setStatusOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [manage, setManage] = useState<{ entry: RegistryEntry; conn: Connection } | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState<Connection | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const { data: registry, isLoading: regLoading } = useQuery<RegistryEntry[]>({
    queryKey: ["connections-registry"],
    queryFn: () => apiGet<RegistryEntry[]>("/connections/registry"),
    retry: 1,
  });

  const { data: connections, isLoading, error, refetch } = useQuery<Connection[]>({
    queryKey: ["connections"],
    queryFn: () => apiGet<Connection[]>("/connections"),
    retry: 1,
  });

  const connsByChannel = useMemo(() => {
    const m = new Map<string, Connection>();
    for (const c of connections ?? []) m.set(c.channel, c);
    return m;
  }, [connections]);

  /** The connection that backs a registry card (ads cards inherit their
   *  organic provider's connection). */
  function backingConn(entry: RegistryEntry): Connection | undefined {
    if (entry.category === "advertising") {
      for (const ch of ADS_LINKED[entry.channel] ?? []) {
        const c = connsByChannel.get(ch);
        if (c) return c;
      }
      return undefined;
    }
    return connsByChannel.get(entry.channel);
  }

  const handleConnect = async (entry: RegistryEntry) => {
    if (!brand?.id) { setOauthError("Please select a brand first."); return; }
    if (!entry.oauth_channel) { setOauthError(`${entry.label} credentials must be configured by the workspace admin.`); return; }
    setConnecting(entry.channel);
    setOauthError(null);
    try {
      const res = await apiPost<{ auth_url: string }>(
        `/connections/${entry.oauth_channel}/oauth?brand_id=${brand.id}`,
      );
      if (res.auth_url) window.location.href = res.auth_url;
      else throw new Error("no auth URL returned");
    } catch (err) {
      const msg = err instanceof ApiError
        ? `Could not start OAuth for ${entry.label} (HTTP ${err.status}).`
        : "Could not start OAuth. Please try again.";
      setOauthError(msg);
      setConnecting(null);
    }
  };

  const handleDisconnect = async (conn: Connection) => {
    setDisconnecting(true);
    try {
      await apiDelete(`/connections/${conn.id}`);
      setConfirmDisconnect(null);
      setManage(null);
      await refetch();
      qc.invalidateQueries({ queryKey: ["connections-registry"] });
    } catch {
      setOauthError("Disconnect failed. Please try again.");
    } finally {
      setDisconnecting(false);
    }
  };

  // ─── Filtering ──────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let list = registry ?? [];
    if (category !== "all") list = list.filter((e) => e.category === category);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((e) => e.label.toLowerCase().includes(q));
    }
    if (statusFilter !== "all") {
      list = list.filter((e) => connUiState(e, backingConn(e), connecting) === statusFilter);
    }
    return list;
  }, [registry, category, search, statusFilter, connecting, connsByChannel]); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => {
    const all = registry ?? [];
    return {
      all: all.length,
      social: all.filter((e) => e.category === "social").length,
      advertising: all.filter((e) => e.category === "advertising").length,
      messaging: all.filter((e) => e.category === "messaging").length,
    };
  }, [registry]);

  const grouped = useMemo(() => {
    if (category !== "all") return [{ cat: category, items: filtered }];
    return (["social", "advertising", "messaging"] as const)
      .map((cat) => ({ cat, items: filtered.filter((e) => e.category === cat) }))
      .filter((g) => g.items.length > 0);
  }, [filtered, category]);

  const loading = brandLoading || regLoading || isLoading;

  // ─── Card ────────────────────────────────────────────────────────────────
  const renderCard = (entry: RegistryEntry) => {
    const conn = backingConn(entry);
    const st = connUiState(entry, conn, connecting);
    const badge = STATE_BADGE[st];
    const tile = tileFor(entry.channel);

    const primary =
      st === "connected" ? { label: "Manage", fn: () => setManage({ entry, conn: conn! }) } :
      st === "reconnect_required" || st === "error" ? { label: "Reconnect", fn: () => handleConnect(entry) } :
      st === "connecting" ? { label: "Connecting…", fn: () => {} } :
      st === "config_required" ? { label: "Configure", fn: () => setOauthError(`${entry.label} needs OAuth credentials configured server-side. Contact your workspace admin.`) } :
      { label: "Connect", fn: () => handleConnect(entry) };

    return (
      <motion.div
        key={entry.channel}
        layout
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-line/10 bg-bg-card p-4 flex flex-col gap-3 hover:border-line/20 transition-colors"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn("w-9 h-9 rounded-xl bg-gradient-to-br flex items-center justify-center shrink-0 text-white font-display font-bold text-sm", tile.gradient)}>
              {tile.letter}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-text truncate">{entry.label}</div>
              <span className={cn("inline-block mt-0.5 px-2 py-0.5 rounded-full text-[10px] font-medium", badge.cls)}>
                {st === "connecting" && <Loader2 className="w-2.5 h-2.5 inline animate-spin mr-1" />}
                {badge.label}
              </span>
            </div>
          </div>
          {/* Overflow menu */}
          <div className="relative shrink-0">
            <button
              onClick={() => setMenuOpen(menuOpen === entry.channel ? null : entry.channel)}
              className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-bg-hover transition-colors"
              aria-label={`${entry.label} options`}
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            <AnimatePresence>
              {menuOpen === entry.channel && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  className="absolute right-0 top-full mt-1 z-20 min-w-[170px] rounded-xl border border-line/10 bg-bg-elevated p-1 shadow-xl"
                >
                  {conn && (
                    <button onClick={() => { setMenuOpen(null); setManage({ entry, conn }); }} className="w-full text-left px-3 py-2 rounded-lg text-xs text-text-secondary hover:bg-bg-hover hover:text-text">
                      Manage accounts
                    </button>
                  )}
                  {conn && entry.oauth_channel && (
                    <button onClick={() => { setMenuOpen(null); handleConnect(entry); }} className="w-full text-left px-3 py-2 rounded-lg text-xs text-text-secondary hover:bg-bg-hover hover:text-text">
                      Reconnect
                    </button>
                  )}
                  {conn && (
                    <button onClick={() => { setMenuOpen(null); setConfirmDisconnect(conn); }} className="w-full text-left px-3 py-2 rounded-lg text-xs text-danger hover:bg-danger/10">
                      Disconnect
                    </button>
                  )}
                  <button onClick={() => { setMenuOpen(null); setManage({ entry, conn: conn! }); }} className="w-full text-left px-3 py-2 rounded-lg text-xs text-text-secondary hover:bg-bg-hover hover:text-text">
                    View details
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <p className="text-xs text-text-secondary leading-relaxed line-clamp-2 min-h-[2rem]">
          {entry.description}
        </p>

        {conn && st === "connected" && (
          <div className="text-[11px] text-text-muted space-y-0.5">
            {conn.account_label && <div className="truncate">{conn.account_label}</div>}
            <div>Connected {timeAgo(conn.created_at) ?? ""}</div>
          </div>
        )}
        {st === "reconnect_required" && conn && (
          <p className="text-[11px] text-amber-400/90">Access token expired or revoked — reconnect to resume publishing.</p>
        )}
        {st === "config_required" && (
          <p className="text-[11px] text-amber-300/80">OAuth credentials not configured on the server yet.</p>
        )}

        <div className="mt-auto pt-1">
          <button
            onClick={primary.fn}
            disabled={st === "connecting"}
            className={cn(
              "w-full py-2 rounded-xl text-xs font-medium transition-colors",
              st === "connected"
                ? "bg-bg-hover text-text hover:bg-bg-elevated"
                : st === "config_required"
                  ? "bg-white/[0.04] text-text-muted border border-line/10"
                  : "bg-accent text-white hover:bg-accent-dark",
            )}
          >
            {st === "connecting" && <Loader2 className="w-3.5 h-3.5 inline animate-spin mr-1.5" />}
            {primary.label}
          </button>
        </div>
      </motion.div>
    );
  };

  // ─── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6" onClick={() => { setMenuOpen(null); setStatusOpen(false); }}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Channels &amp; Connections</h1>
          <p className="text-sm text-text-secondary mt-1 max-w-xl">
            Connect your social media and advertising accounts to publish content, manage campaigns, and distribute content from one place.
          </p>
        </div>
        <a
          href="/support"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-line/10 text-xs font-medium text-text-secondary hover:text-text hover:bg-bg-hover transition-colors shrink-0"
        >
          <ExternalLink className="w-3.5 h-3.5" /> View Connection Guide
        </a>
      </div>

      {oauthError && (
        <div className="flex items-center gap-2 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl px-4 py-3">
          <AlertCircle className="w-4 h-4 shrink-0" /> {oauthError}
        </div>
      )}

      {/* Category tabs + search + status */}
      <div className="flex flex-col lg:flex-row lg:items-center gap-3">
        <div className="flex gap-1 p-1 rounded-xl bg-bg-surface overflow-x-auto scrollbar-none w-fit">
          {(["all", "social", "advertising", "messaging"] as const).map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={cn(
                "px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors",
                category === c ? "bg-accent text-white" : "text-text-secondary hover:text-text",
              )}
            >
              {CATEGORY_LABELS[c]} <span className="opacity-70">({counts[c]})</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 lg:ml-auto">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              placeholder="Search platforms…"
              className="pl-9 pr-3 py-2 w-48 rounded-xl bg-bg-card border border-line/10 text-xs text-text placeholder:text-text-muted focus:outline-none focus:border-accent/40"
            />
          </div>
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setStatusOpen(!statusOpen); }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-bg-card border border-line/10 text-xs text-text-secondary hover:text-text transition-colors"
            >
              {statusFilter === "all" ? "All Status" : STATE_BADGE[statusFilter as UiState].label}
              <ChevronDown className="w-3 h-3" />
            </button>
            <AnimatePresence>
              {statusOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  className="absolute right-0 top-full mt-1 z-20 min-w-[170px] rounded-xl border border-line/10 bg-bg-elevated p-1 shadow-xl"
                >
                  {["all", "connected", "not_connected", "reconnect_required", "config_required"].map((s) => (
                    <button
                      key={s}
                      onClick={() => { setStatusFilter(s); setStatusOpen(false); }}
                      className={cn("w-full text-left px-3 py-2 rounded-lg text-xs", statusFilter === s ? "text-accent" : "text-text-secondary hover:bg-bg-hover hover:text-text")}
                    >
                      {s === "all" ? "All Status" : STATE_BADGE[s as UiState].label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-40 rounded-2xl bg-bg-card border border-line/10 animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-danger/20 bg-danger/5 p-6 text-center">
          <AlertCircle className="w-6 h-6 text-danger mx-auto mb-2" />
          <p className="text-sm text-text-secondary">Couldn&apos;t load connections.</p>
          <button onClick={() => refetch()} className="mt-3 inline-flex items-center gap-1.5 text-xs text-accent hover:underline">
            <RefreshCw className="w-3.5 h-3.5" /> Retry
          </button>
        </div>
      ) : grouped.length === 0 ? (
        <div className="rounded-2xl border border-line/10 bg-bg-card p-10 text-center">
          <Link2 className="w-6 h-6 text-text-muted mx-auto mb-2" />
          <p className="text-sm text-text-secondary">No integrations match your filters.</p>
        </div>
      ) : (
        grouped.map((g) => (
          <section key={g.cat}>
            <h2 className="text-sm font-semibold text-text mb-3">
              {CATEGORY_LABELS[g.cat]}
              <span className="ml-2 text-xs font-normal text-text-muted">({g.items.length})</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {g.items.map(renderCard)}
            </div>
          </section>
        ))
      )}

      {/* ─── Manage modal ─── */}
      <AnimatePresence>
        {manage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setManage(null)}
            className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-2xl border border-line/10 bg-bg-elevated p-6 shadow-2xl"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={cn("w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center text-white font-display font-bold", tileFor(manage.entry.channel).gradient)}>
                    {tileFor(manage.entry.channel).letter}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text">{manage.entry.label}</h3>
                    {manage.conn ? (
                      <span className={cn("text-[10px] px-2 py-0.5 rounded-full", STATE_BADGE[connUiState(manage.entry, manage.conn, connecting)].cls)}>
                        {STATE_BADGE[connUiState(manage.entry, manage.conn, connecting)].label}
                      </span>
                    ) : (
                      <span className="text-[10px] text-text-muted">Not connected</span>
                    )}
                  </div>
                </div>
                <button onClick={() => setManage(null)} className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-bg-hover" aria-label="Close">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                {manage.conn ? (
                  <>
                    {manage.conn.account_label && (
                      <div className="flex justify-between gap-4">
                        <span className="text-text-muted">Account</span>
                        <span className="text-text text-right truncate">{manage.conn.account_label}</span>
                      </div>
                    )}
                    <div className="flex justify-between gap-4">
                      <span className="text-text-muted">Connected</span>
                      <span className="text-text">{manage.conn.created_at ? new Date(manage.conn.created_at).toLocaleString() : "—"}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-text-muted">Token expiry</span>
                      <span className="text-text">{manage.conn.expires_at ? new Date(manage.conn.expires_at).toLocaleString() : "No expiry"}</span>
                    </div>
                    {manage.conn.scopes && manage.conn.scopes.length > 0 && (
                      <div>
                        <span className="text-text-muted">Permissions</span>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {manage.conn.scopes.map((s) => (
                            <span key={s} className="px-2 py-0.5 rounded-full bg-bg-hover text-[10px] text-text-secondary font-mono">{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-text-secondary">
                    {manage.entry.description}
                    {!manage.entry.configured && " Server-side OAuth credentials are not configured yet."}
                  </p>
                )}
              </div>

              <div className="flex gap-2 mt-6">
                {manage.conn && manage.entry.oauth_channel && (
                  <button
                    onClick={() => { setManage(null); handleConnect(manage.entry); }}
                    className="flex-1 py-2 rounded-xl bg-bg-hover text-text text-xs font-medium hover:bg-bg-card transition-colors"
                  >
                    Reconnect
                  </button>
                )}
                {manage.conn && (
                  <button
                    onClick={() => { setConfirmDisconnect(manage.conn); setManage(null); }}
                    className="flex-1 py-2 rounded-xl bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors"
                  >
                    Disconnect
                  </button>
                )}
                {!manage.conn && manage.entry.oauth_channel && manage.entry.configured && (
                  <button
                    onClick={() => { setManage(null); handleConnect(manage.entry); }}
                    className="flex-1 py-2 rounded-xl bg-accent text-white text-xs font-medium hover:bg-accent-dark transition-colors"
                  >
                    Connect
                  </button>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Disconnect confirm ─── */}
      <AnimatePresence>
        {confirmDisconnect && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setConfirmDisconnect(null)}
            className="fixed inset-0 z-[90] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.96 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.96 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-sm rounded-2xl border border-line/10 bg-bg-elevated p-6 shadow-2xl"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-xl bg-danger/15 flex items-center justify-center">
                  <Unlink className="w-4 h-4 text-danger" />
                </div>
                <h3 className="text-sm font-semibold text-text">Disconnect channel?</h3>
              </div>
              <p className="text-xs text-text-secondary mb-5">
                This removes the stored OAuth tokens and stops publishing on this channel. You can reconnect anytime. The provider-side grant can also be revoked in the provider&apos;s security settings.
              </p>
              <div className="flex gap-2">
                <button onClick={() => setConfirmDisconnect(null)} className="flex-1 py-2 rounded-xl bg-bg-hover text-text text-xs font-medium hover:bg-bg-card">
                  Cancel
                </button>
                <button
                  onClick={() => handleDisconnect(confirmDisconnect)}
                  disabled={disconnecting}
                  className="flex-1 py-2 rounded-xl bg-danger text-white text-xs font-medium hover:bg-danger/80 disabled:opacity-50"
                >
                  {disconnecting ? "Disconnecting…" : "Disconnect"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
