"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check, Circle, Loader2, Plug, RefreshCw, Trash2, X, ExternalLink,
  Activity, Database, Zap, Shield, AlertCircle,
} from "lucide-react";
import { useState } from "react";

interface Integration {
  name: string;
  display_name: string;
  category: string;
  icon: string;
  description: string;
  capabilities: string[];
  auth_type: string;
  scopes: string[];
  docs_url: string;
  setup_guide: string;
  connected: boolean;
  connection_id: string | null;
  status: string | null;
  last_sync: string | null;
  last_error: string | null;
}

const categoryColors: Record<string, string> = {
  analytics: "text-blue-400 bg-blue-500/10",
  cms: "text-purple-400 bg-purple-500/10",
  ecommerce: "text-green-400 bg-green-500/10",
  crm: "text-amber-400 bg-amber-500/10",
  email: "text-pink-400 bg-pink-500/10",
  ads: "text-amber-400 bg-amber-500/10",
};

const capabilityIcons: Record<string, typeof Activity> = {
  AUTHENTICATE: Shield,
  READ_METRICS: Activity,
  PUBLISH: Zap,
  SYNC_ASSETS: Database,
  WRITE_BACK: RefreshCw,
  ATTRIBUTION: Activity,
  MANAGE_MEDIA: Database,
  SEO_MANAGEMENT: Zap,
};

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [showConnectModal, setShowConnectModal] = useState<Integration | null>(null);
  const [connectForm, setConnectForm] = useState<Record<string, string>>({});

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: async () => {
      const res = await fetch("/api/integrations", {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!res.ok) throw new Error("Failed to fetch integrations");
      return res.json() as Promise<Integration[]>;
    },
  });

  const syncMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`/api/integrations/${name}/sync`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!res.ok) throw new Error("Sync failed");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`/api/integrations/${name}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!res.ok) throw new Error("Disconnect failed");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
  });

  const connectMutation = useMutation({
    mutationFn: async (integration: Integration) => {
      const body: Record<string, string> = {};
      if (integration.auth_type === "app_password") {
        body.site_url = connectForm.site_url || "";
        body.username = connectForm.username || "";
        body.app_password = connectForm.app_password || "";
      } else if (integration.auth_type === "oauth") {
        body.code = connectForm.code || "";
        body.redirect_uri = window.location.origin + "/integrations/callback";
      }
      const res = await fetch(`/api/integrations/${integration.name}/connect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Connection failed");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setShowConnectModal(null);
      setConnectForm({});
    },
  });

  const connected = integrations.filter((i) => i.connected);
  const available = integrations.filter((i) => !i.connected);

  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
              <Plug className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold">Integration Centre</h1>
              <p className="text-sm text-text-muted">
                Connect your marketing tools — {connected.length} active, {available.length} available
              </p>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
          </div>
        ) : (
          <>
            {/* Connected Integrations */}
            {connected.length > 0 && (
              <div className="mb-8">
                <h2 className="font-display text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
                  Connected ({connected.length})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {connected.map((integration) => (
                    <IntegrationCard
                      key={integration.name}
                      integration={integration}
                      onSync={() => syncMutation.mutate(integration.name)}
                      onDisconnect={() => disconnectMutation.mutate(integration.name)}
                      syncing={syncMutation.isPending && syncMutation.variables === integration.name}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Available Integrations */}
            <div>
              <h2 className="font-display text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
                Available ({available.length})
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {available.map((integration) => (
                  <IntegrationCard
                    key={integration.name}
                    integration={integration}
                    onConnect={() => {
                      setShowConnectModal(integration);
                      setConnectForm({});
                    }}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Connect Modal */}
      <AnimatePresence>
        {showConnectModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setShowConnectModal(null)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 10 }}
              className="glass rounded-2xl p-6 max-w-md w-full mx-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{showConnectModal.icon}</span>
                  <div>
                    <h3 className="font-display font-semibold">{showConnectModal.display_name}</h3>
                    <p className="text-xs text-text-muted capitalize">{showConnectModal.category}</p>
                  </div>
                </div>
                <button onClick={() => setShowConnectModal(null)} className="text-text-muted hover:text-text">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <p className="text-sm text-text-secondary mb-4">{showConnectModal.description}</p>

              {/* Setup guide */}
              <div className="glass rounded-lg p-3 mb-4">
                <p className="text-xs text-text-muted mb-1">Setup Guide:</p>
                <p className="text-xs text-text-secondary">{showConnectModal.setup_guide}</p>
              </div>

              {/* Auth form based on auth_type */}
              {showConnectModal.auth_type === "app_password" && (
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Site URL (https://yoursite.com)"
                    value={connectForm.site_url || ""}
                    onChange={(e) => setConnectForm({ ...connectForm, site_url: e.target.value })}
                    className="input-field"
                  />
                  <input
                    type="text"
                    placeholder="Username"
                    value={connectForm.username || ""}
                    onChange={(e) => setConnectForm({ ...connectForm, username: e.target.value })}
                    className="input-field"
                  />
                  <input
                    type="password"
                    placeholder="Application Password"
                    value={connectForm.app_password || ""}
                    onChange={(e) => setConnectForm({ ...connectForm, app_password: e.target.value })}
                    className="input-field"
                  />
                </div>
              )}

              {showConnectModal.auth_type === "oauth" && (
                <div className="space-y-3">
                  <p className="text-xs text-text-secondary">
                    You'll be redirected to {showConnectModal.display_name} to authorize PRACHAR.
                  </p>
                  <input
                    type="text"
                    placeholder="OAuth code (paste after redirect)"
                    value={connectForm.code || ""}
                    onChange={(e) => setConnectForm({ ...connectForm, code: e.target.value })}
                    className="input-field"
                  />
                </div>
              )}

              {showConnectModal.auth_type === "api_key" && (
                <div className="space-y-3">
                  <input
                    type="password"
                    placeholder="API Key"
                    value={connectForm.api_key || ""}
                    onChange={(e) => setConnectForm({ ...connectForm, api_key: e.target.value })}
                    className="input-field"
                  />
                </div>
              )}

              {/* Capabilities */}
              <div className="flex flex-wrap gap-1.5 mt-4 mb-4">
                {showConnectModal.capabilities.map((cap) => {
                  const Icon = capabilityIcons[cap] || Circle;
                  return (
                    <span key={cap} className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.04] text-text-muted flex items-center gap-1">
                      <Icon className="w-3 h-3" />
                      {cap.replace(/_/g, " ").toLowerCase()}
                    </span>
                  );
                })}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 mt-6">
                <button
                  onClick={() => connectMutation.mutate(showConnectModal)}
                  disabled={connectMutation.isPending}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {connectMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plug className="w-4 h-4" />
                  )}
                  Connect
                </button>
                {showConnectModal.docs_url && (
                  <a
                    href={showConnectModal.docs_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-2 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text transition-colors text-xs flex items-center gap-1"
                  >
                    Docs <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              {connectMutation.isError && (
                <div className="mt-3 p-2 rounded-lg bg-red-500/10 text-red-400 text-xs flex items-center gap-2">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {connectMutation.error?.message || "Connection failed"}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function IntegrationCard({
  integration,
  onConnect,
  onSync,
  onDisconnect,
  syncing,
}: {
  integration: Integration;
  onConnect?: () => void;
  onSync?: () => void;
  onDisconnect?: () => void;
  syncing?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass rounded-xl p-4 transition-all ${
        integration.connected ? "border-l-2 border-l-green-500/30" : ""
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{integration.icon}</span>
          <div>
            <h3 className="font-display font-semibold text-sm">{integration.display_name}</h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded capitalize ${categoryColors[integration.category] || "bg-white/[0.04] text-text-muted"}`}>
              {integration.category}
            </span>
          </div>
        </div>
        {integration.connected ? (
          <span className="flex items-center gap-1 text-[10px] text-green-400">
            <Check className="w-3 h-3" /> Connected
          </span>
        ) : (
          <span className="flex items-center gap-1 text-[10px] text-text-muted">
            <Circle className="w-3 h-3" /> Not connected
          </span>
        )}
      </div>

      <p className="text-xs text-text-secondary mb-3 line-clamp-2">{integration.description}</p>

      {/* Capabilities */}
      <div className="flex flex-wrap gap-1 mb-3">
        {integration.capabilities.slice(0, 4).map((cap) => (
          <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04] text-text-muted">
            {cap.replace(/_/g, " ").toLowerCase()}
          </span>
        ))}
        {integration.capabilities.length > 4 && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04] text-text-muted">
            +{integration.capabilities.length - 4} more
          </span>
        )}
      </div>

      {/* Status info for connected integrations */}
      {integration.connected && (
        <div className="text-[10px] text-text-muted space-y-0.5 mb-3">
          {integration.last_sync && (
            <div>Last sync: {new Date(integration.last_sync).toLocaleDateString()}</div>
          )}
          {integration.last_error && (
            <div className="text-red-400">Error: {integration.last_error}</div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        {integration.connected ? (
          <>
            <button
              onClick={onSync}
              disabled={syncing}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08] transition-colors text-xs disabled:opacity-50"
            >
              {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Sync
            </button>
            <button
              onClick={onDisconnect}
              className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors text-xs flex items-center gap-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </>
        ) : (
          <button
            onClick={onConnect}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors text-xs font-medium"
          >
            <Plug className="w-3.5 h-3.5" />
            Connect
          </button>
        )}
      </div>
    </motion.div>
  );
}
