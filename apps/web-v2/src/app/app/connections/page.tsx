"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertCircle,
  RefreshCw,
  Link2,
  Check,
  Loader2,
  Globe,
  Zap,
} from "lucide-react";
import { Card } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useActiveBrand } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface Connection {
  id: string;
  brand_id: string;
  channel: string;
  status: string;
  expires_at: string | null;
}

const REGIONS: { name: string; channels: string[] }[] = [
  { name: "Americas", channels: ["google", "youtube", "instagram", "facebook", "x", "linkedin", "pinterest", "snap", "reddit", "amazon"] },
  { name: "Europe", channels: ["google", "youtube", "instagram", "facebook", "x", "linkedin", "pinterest", "tiktok"] },
  { name: "India", channels: ["google", "youtube", "instagram", "facebook", "whatsapp", "telegram", "amazon"] },
  { name: "SEA", channels: ["google", "youtube", "instagram", "tiktok", "facebook", "whatsapp", "telegram", "line"] },
  { name: "MENA", channels: ["google", "youtube", "instagram", "tiktok", "snap", "whatsapp", "telegram"] },
  { name: "East Asia", channels: ["google", "youtube", "instagram", "tiktok", "line", "kakao", "naver"] },
  { name: "CIS", channels: ["vk", "telegram", "yandex", "youtube"] },
];

const CHANNEL_LABELS: Record<string, string> = {
  google: "Google",
  youtube: "YouTube",
  instagram: "Instagram",
  facebook: "Facebook",
  x: "X / Twitter",
  linkedin: "LinkedIn",
  pinterest: "Pinterest",
  snap: "Snapchat",
  reddit: "Reddit",
  amazon: "Amazon",
  tiktok: "TikTok",
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  line: "LINE",
  kakao: "Kakao",
  naver: "Naver",
  vk: "VK",
  yandex: "Yandex",
};

function channelLabel(ch: string): string {
  return CHANNEL_LABELS[ch] ?? ch.charAt(0).toUpperCase() + ch.slice(1);
}

function channelInitial(ch: string): string {
  return channelLabel(ch).charAt(0).toUpperCase();
}

export default function ConnectionsPage() {
  const qc = useQueryClient();
  const { brand, isLoading: brandLoading } = useActiveBrand();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);

  const { data: connections, isLoading, error, refetch } = useQuery<Connection[]>({
    queryKey: ["connections"],
    queryFn: () => apiGet<Connection[]>("/connections"),
    retry: 1,
  });

  const connected = new Map(connections?.map((c) => [c.channel, c]) ?? []);

  const handleConnect = async (channel: string) => {
    if (!brand?.id) {
      setOauthError("Please select a brand first.");
      return;
    }
    setConnecting(channel);
    setOauthError(null);
    try {
      const res = await apiPost<{ auth_url: string; channel: string }>(
        `/connections/${channel}/oauth?brand_id=${brand.id}`,
      );
      if (res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `Could not start OAuth for ${channelLabel(channel)} (${err.status}). Please try again.`
          : `Could not connect ${channelLabel(channel)}. Please try again.`;
      setOauthError(msg);
    } finally {
      setConnecting(null);
    }
  };

  const loading = brandLoading || isLoading;

  // Flatten all channels to count connected vs available
  const allChannels = new Set(REGIONS.flatMap((r) => r.channels));
  const connectedCount = connections?.filter((c) => c.status === "connected" || c.status === "active").length ?? 0;

  return (
    <div className="p-4 lg:p-8 max-w-[1600px] mx-auto animate-fade-in pb-32">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide text-text mb-1">
            Connections
          </h1>
          <p className="text-sm text-text-secondary">
            Connect your social and advertising accounts to publish content and
            run campaigns.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={loading}
            className="btn-ghost flex items-center gap-2"
            aria-label="Refresh connections"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Summary stats */}
      {!loading && !error && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          <div className="card-3d rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-success/10 flex items-center justify-center">
                <Check className="w-4 h-4 text-success" />
              </div>
              <p className="label-field">Connected</p>
            </div>
            <p className="font-display text-2xl font-semibold text-text">
              {connectedCount}
            </p>
          </div>
          <div className="card-3d rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-white/[0.04] flex items-center justify-center">
                <Link2 className="w-4 h-4 text-text-secondary" />
              </div>
              <p className="label-field">Available</p>
            </div>
            <p className="font-display text-2xl font-semibold text-text">
              {allChannels.size}
            </p>
          </div>
          <div className="card-3d rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
                <Globe className="w-4 h-4 text-accent" />
              </div>
              <p className="label-field">Regions</p>
            </div>
            <p className="font-display text-2xl font-semibold text-text">
              {REGIONS.length}
            </p>
          </div>
        </div>
      )}

      {oauthError && (
        <div className="mb-6 rounded-lg bg-danger/10 border border-danger/20 px-4 py-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-danger shrink-0" />
          <p className="text-sm text-danger">{oauthError}</p>
        </div>
      )}

      {loading && (
        <div className="space-y-8">
          {[0, 1, 2].map((r) => (
            <div key={r}>
              <Skeleton className="h-8 w-48 mb-4 rounded-lg" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-32 rounded-xl" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && error && (
        <Card className="text-center py-16" hover={false}>
          <div className="w-14 h-14 rounded-2xl bg-danger/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7 text-danger" />
          </div>
          <h3 className="font-display text-lg font-medium text-text mb-2">
            Couldn&apos;t load connections
          </h3>
          <p className="text-sm text-text-secondary mb-6">
            Something went wrong fetching your connections. Please try again.
          </p>
          <button
            onClick={() => refetch()}
            className="btn-primary inline-flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" /> Try Again
          </button>
        </Card>
      )}

      {!loading && !error && connectedCount === 0 && (
        <Card className="text-center py-16 mb-8" hover={false}>
          <motion.div
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5 glow-ring"
          >
            <Zap className="w-8 h-8 text-accent" />
          </motion.div>
          <h3 className="font-display text-xl font-medium text-text mb-2">
            No connections yet
          </h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto mb-6 leading-relaxed">
            Connect your social media and ad accounts below to start publishing
            content and running campaigns automatically.
          </p>
        </Card>
      )}

      {!loading && !error && (
        <div className="space-y-8">
          {REGIONS.map((region, ri) => (
            <motion.div
              key={region.name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: ri * 0.06 }}
            >
              <SectionHeader
                title={region.name}
                subtitle={`${region.channels.length} platform${region.channels.length === 1 ? "" : "s"}`}
                icon={<Globe className="w-4 h-4" />}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {region.channels.map((ch, ci) => {
                  const conn = connected.get(ch);
                  const isOn =
                    conn?.status === "connected" || conn?.status === "active";
                  const isConnecting = connecting === ch;
                  return (
                    <motion.div
                      key={ch}
                      initial={{ opacity: 0, scale: 0.97 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: ri * 0.06 + ci * 0.03 }}
                    >
                      <Card hover className="group">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-10 h-10 rounded-lg flex items-center justify-center font-display text-base font-semibold transition-colors",
                              isOn
                                ? "bg-success/10 text-success"
                                : "bg-white/[0.04] text-text-secondary group-hover:text-accent",
                            )}>
                              {channelInitial(ch)}
                            </div>
                            <div>
                              <p className="font-display text-sm font-medium text-text">
                                {channelLabel(ch)}
                              </p>
                              <p className="text-[10px] text-text-muted font-mono uppercase tracking-wider">
                                {ch}
                              </p>
                            </div>
                          </div>
                          <span
                            className={cn(
                              "badge text-[10px]",
                              isOn ? "badge-success" : "badge-neutral",
                            )}
                          >
                            {isOn ? "connected" : "off"}
                          </span>
                        </div>
                        <button
                          onClick={() => handleConnect(ch)}
                          disabled={isConnecting}
                          className={cn(
                            "w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all",
                            isOn
                              ? "btn-secondary"
                              : "btn-primary",
                            isConnecting && "opacity-60 cursor-wait",
                          )}
                        >
                          {isConnecting ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Connecting...
                            </>
                          ) : isOn ? (
                            <>
                              <RefreshCw className="w-4 h-4" />
                              Reconnect
                            </>
                          ) : (
                            <>
                              <Link2 className="w-4 h-4" />
                              Connect
                            </>
                          )}
                        </button>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
