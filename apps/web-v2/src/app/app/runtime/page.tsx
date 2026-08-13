"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { apiGet } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

interface SessionSummary {
  session_id: string;
  decision_id: string;
  goal: string;
  status: string;
  intent: string;
  mode: string;
  started_at: number;
  completed: boolean;
  tenant_id: string | null;
  brand_id: string | null;
  metrics: Record<string, any> | null;
  warnings: string[];
  error: string | null;
  node_count: number;
  completed_nodes: number;
}

interface SessionDetail {
  session_id: string;
  decision: Record<string, any>;
  graph: Record<string, any>;
  metrics: Record<string, any> | null;
  execution_result: Record<string, any> | null;
  response: Record<string, any>;
  started_at: number;
  completed: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "text-amber-400",
  approved: "text-blue-400",
  executing: "text-accent",
  completed: "text-green-400",
  completed_with_warnings: "text-amber-400",
  cancelled: "text-text-muted",
  failed: "text-red-400",
};

export default function RuntimeDashboardPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"sessions" | "detail" | "tools">("sessions");
  const [tools, setTools] = useState<any[]>([]);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiGet<{ sessions: SessionSummary[] }>("/admin/runtime/sessions");
      setSessions(res.sessions || []);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (sessionId: string) => {
    try {
      const res = await apiGet<SessionDetail>(`/admin/runtime/sessions/${sessionId}`);
      setSelected(res);
      setView("detail");
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const fetchTools = useCallback(async () => {
    try {
      const res = await apiGet<{ tools: any[]; count: number }>("/admin/runtime/tools");
      setTools(res.tools || []);
      setView("tools");
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000);
    return () => clearInterval(interval);
  }, [fetchSessions]);

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold">Runtime Certification Dashboard</h1>
            <p className="text-sm text-text-secondary mt-1">
              Internal debug tool. Every session: Decision → Graph → Events → Timeline → Metrics.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setView("sessions")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                view === "sessions" ? "bg-accent/20 text-accent" : "bg-white/[0.03] text-text-secondary"
              }`}
            >
              Sessions ({sessions.length})
            </button>
            <button
              onClick={fetchTools}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                view === "tools" ? "bg-accent/20 text-accent" : "bg-white/[0.03] text-text-secondary"
              }`}
            >
              Tools
            </button>
            <button
              onClick={fetchSessions}
              className="px-3 py-1.5 rounded-lg text-xs bg-white/[0.03] text-text-secondary hover:text-text"
            >
              ↻ Refresh
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="glass rounded-xl p-4 mb-4 border border-red-400/20">
          <p className="text-sm text-red-400">{error}</p>
          <p className="text-xs text-text-muted mt-1">
            Make sure the API is running and you're logged in.
          </p>
        </div>
      )}

      {/* Sessions List */}
      {view === "sessions" && (
        <div className="space-y-2">
          {loading ? (
            [1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
          ) : sessions.length === 0 ? (
            <div className="glass rounded-xl p-8 text-center">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-sm text-text-secondary">No runtime sessions yet.</p>
              <p className="text-xs text-text-muted mt-1">
                Invoke PRACHAR AI to create a session.
              </p>
            </div>
          ) : (
            sessions.map((s) => (
              <motion.div
                key={s.session_id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                onClick={() => fetchDetail(s.session_id)}
                className="glass rounded-xl p-4 cursor-pointer hover:border-white/[0.1] transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${STATUS_COLORS[s.status] || "text-text"}`}>
                        ● {s.status}
                      </span>
                      <span className="text-sm font-medium truncate">{s.goal}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[10px] text-text-muted">
                      <span>intent: {s.intent}</span>
                      <span>mode: {s.mode}</span>
                      <span>nodes: {s.completed_nodes}/{s.node_count}</span>
                      {s.metrics && (
                        <span>
                          {(s.metrics.timings?.total_duration_ms / 1000).toFixed(1)}s ·
                          ${s.metrics.costs?.total_usd?.toFixed(4)}
                        </span>
                      )}
                    </div>
                    {s.warnings.length > 0 && (
                      <div className="mt-1 text-[10px] text-amber-400">
                        ⚠ {s.warnings.length} warning(s)
                      </div>
                    )}
                    {s.error && (
                      <div className="mt-1 text-[10px] text-red-400 truncate">✕ {s.error}</div>
                    )}
                  </div>
                  <div className="text-[10px] text-text-muted flex-shrink-0 ml-2">
                    {new Date(s.started_at * 1000).toLocaleTimeString()}
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      )}

      {/* Session Detail */}
      {view === "detail" && selected && (
        <div>
          <button
            onClick={() => setView("sessions")}
            className="mb-4 text-xs text-text-secondary hover:text-text"
          >
            ← Back to sessions
          </button>

          <div className="space-y-4">
            {/* Decision Contract */}
            <Section title="Decision Contract">
              <KeyValue data={selected.decision} />
            </Section>

            {/* Execution Graph */}
            <Section title="Execution Graph">
              <GraphView graph={selected.graph} />
            </Section>

            {/* Metrics */}
            {selected.metrics && (
              <Section title="Metrics (V6)">
                <MetricsView metrics={selected.metrics} />
              </Section>
            )}

            {/* Execution Result */}
            {selected.execution_result && (
              <Section title="Execution Result">
                <NodeResultsView result={selected.execution_result} />
              </Section>
            )}

            {/* Response */}
            {selected.response && Object.keys(selected.response).length > 0 && (
              <Section title="Composed Response">
                <KeyValue data={selected.response} />
              </Section>
            )}
          </div>
        </div>
      )}

      {/* Tools */}
      {view === "tools" && (
        <div>
          <button
            onClick={() => setView("sessions")}
            className="mb-4 text-xs text-text-secondary hover:text-text"
          >
            ← Back to sessions
          </button>
          <div className="space-y-2">
            {tools.map((t) => (
              <div key={t.name} className="glass rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-semibold">{t.name}</span>
                    {t.deprecated && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
                        DEPRECATED
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-text-muted">v{t.version}</span>
                </div>
                <p className="text-xs text-text-secondary mt-1">{t.description}</p>
                <div className="flex flex-wrap gap-3 mt-2 text-[10px] text-text-muted">
                  <span>cost: ${t.estimated_cost_usd}</span>
                  <span>timeout: {t.hard_timeout_ms / 1000}s</span>
                  <span>retry: {t.supports_retry ? "yes" : "no"}</span>
                  <span>side: {t.side_effects}</span>
                  {t.successor && <span className="text-amber-400">→ {t.successor}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-xl p-4">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}

function KeyValue({ data }: { data: Record<string, any> }) {
  return (
    <div className="space-y-1.5">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex gap-3 text-xs">
          <span className="text-text-muted w-40 flex-shrink-0">{key}</span>
          <span className="text-text break-all">
            {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function GraphView({ graph }: { graph: Record<string, any> }) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  return (
    <div>
      <div className="text-xs text-text-muted mb-2">{nodes.length} nodes, {edges.length} edges</div>
      <div className="space-y-1.5">
        {nodes.map((n: any, i: number) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span className="font-mono text-text">{n.tool}</span>
            {n.needs_approval && (
              <span className="text-[9px] px-1 rounded bg-amber-400/20 text-amber-400">APPROVAL</span>
            )}
            <span className="text-text-muted text-[10px]">({n.id})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricsView({ metrics }: { metrics: Record<string, any> }) {
  const timings = metrics.timings || {};
  const tools = metrics.tools || {};
  const costs = metrics.costs || {};
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <MetricCard label="Total Duration" value={`${(timings.total_duration_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="Planning Time" value={`${(timings.planning_time_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="Execution Time" value={`${(timings.execution_time_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="Tool Time" value={`${(timings.tool_time_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="LLM Time" value={`${(timings.llm_time_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="Waiting Time" value={`${(timings.waiting_time_ms / 1000).toFixed(2)}s`} />
      <MetricCard label="Total Cost" value={`$${costs.total_usd?.toFixed(6)}`} />
      <MetricCard label="Total Tokens" value={String(costs.total_tokens || 0)} />
      <MetricCard label="Tools Total" value={String(tools.total || 0)} />
      <MetricCard label="Tools Success" value={String(tools.successful || 0)} />
      <MetricCard label="Tools Failed" value={String(tools.failed || 0)} />
      <MetricCard label="Tools Retried" value={String(tools.retried || 0)} />
      <MetricCard label="Outcome" value={metrics.outcome || "—"} />
      <MetricCard label="Context Assembly" value={`${timings.context_assembly_ms || 0}ms`} />
      <MetricCard label="Intent Classification" value={`${timings.intent_classification_ms || 0}ms`} />
      <MetricCard label="Response Composition" value={`${timings.response_composition_ms || 0}ms`} />
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/[0.02] rounded-lg p-3">
      <div className="text-[10px] text-text-muted uppercase tracking-wider">{label}</div>
      <div className="text-sm font-mono font-semibold mt-1">{value}</div>
    </div>
  );
}

function NodeResultsView({ result }: { result: Record<string, any> }) {
  const nodeResults = result.node_results || {};
  return (
    <div className="space-y-1.5">
      <div className="flex gap-4 text-xs mb-2">
        <span className={result.success ? "text-green-400" : "text-red-400"}>
          {result.success ? "✓ Success" : "✕ Failed"}
        </span>
        {result.cancelled && <span className="text-text-muted">Cancelled</span>}
        {result.has_warnings && <span className="text-amber-400">⚠ Warnings</span>}
        <span className="text-text-muted">{(result.total_duration_ms / 1000).toFixed(2)}s</span>
        <span className="text-text-muted">${result.total_cost_usd?.toFixed(6)}</span>
      </div>
      {result.warnings?.map((w: string, i: number) => (
        <div key={i} className="text-xs text-amber-400 bg-amber-400/[0.04] rounded p-2">
          ⚠ {w}
        </div>
      ))}
      <div className="space-y-1">
        {Object.entries(nodeResults).map(([nid, nr]: [string, any]) => (
          <div key={nid} className="flex items-center gap-3 text-xs bg-white/[0.02] rounded p-2">
            <span className={nr.success ? "text-green-400" : nr.cancelled ? "text-text-muted" : "text-red-400"}>
              {nr.success ? "✓" : nr.cancelled ? "○" : "✕"}
            </span>
            <span className="font-mono">{nr.tool}</span>
            <span className="text-text-muted">{nr.duration_ms}ms</span>
            <span className="text-text-muted">${nr.cost_usd?.toFixed(6)}</span>
            {nr.retries > 0 && <span className="text-amber-400">↻{nr.retries}</span>}
            {nr.timed_out && <span className="text-red-400">TIMEOUT</span>}
            {nr.error && <span className="text-red-400 truncate">{nr.error}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
