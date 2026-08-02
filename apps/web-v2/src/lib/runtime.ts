/**
 * Runtime Event Subscriber — single SSE client for all runtime events.
 *
 * Constitution Rule 13: Streaming belongs to the Event Bus.
 * The frontend subscribes once to /runtime/stream and handles all event types.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiPost, apiGet } from "./api";

// ─── Event Types ───────────────────────────────────────────────────────────

export interface AIEvent {
  session_id: string;
  type: string;
  phase: "started" | "progress" | "completed" | "error" | "cancelled";
  timestamp: string;
  decision_id?: string;
  tool?: string;
  data?: Record<string, any>;
  orb_state?: string;
  progress?: { completed: number; total: number; label: string } | null;
}

export interface InvokeResponse {
  session_id: string;
  decision_id: string;
  stream_url: string;
  decision: Record<string, any>;
}

// ─── Hook: useRuntimeSession ───────────────────────────────────────────────

interface SessionState {
  status: "idle" | "invoking" | "streaming" | "completed" | "error" | "cancelled" | "waiting_approval";
  events: AIEvent[];
  response: Record<string, any> | null;
  progress: { completed: number; total: number; label: string } | null;
  approvalRequest: { node_id: string; tool: string; reason: string } | null;
  error: string | null;
}

const INITIAL_STATE: SessionState = {
  status: "idle",
  events: [],
  response: null,
  progress: null,
  approvalRequest: null,
  error: null,
};

export function useRuntimeSession() {
  const [state, setState] = useState<SessionState>(INITIAL_STATE);
  const eventSourceRef = useRef<EventSource | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  // ─── Invoke ──────────────────────────────────────────────────────────────

  const invoke = useCallback(async (
    message: string,
    brandId: string,
    modality: "text" | "voice" = "text",
    context: Record<string, any> = {},
  ): Promise<InvokeResponse | null> => {
    setState({ ...INITIAL_STATE, status: "invoking" });

    try {
      const res = await apiPost<InvokeResponse>("/runtime/invoke", {
        message,
        brand_id: brandId,
        modality,
        context,
      });

      sessionIdRef.current = res.session_id;
      setState((prev) => ({ ...prev, status: "streaming" }));

      // Subscribe to SSE stream
      subscribeToStream(res.session_id);

      return res;
    } catch (err: any) {
      setState({ ...INITIAL_STATE, status: "error", error: err.message || "Failed to invoke" });
      return null;
    }
  }, []);

  // ─── Subscribe to SSE ────────────────────────────────────────────────────

  const subscribeToStream = useCallback((sessionId: string) => {
    // Close any existing stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const base = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
    const token = typeof window !== "undefined" ? window.localStorage.getItem("prachar_token") : null;

    // EventSource doesn't support headers, so we pass token as query param
    // (the API should accept this as a fallback)
    const url = `${base}/runtime/stream?session_id=${sessionId}${token ? `&token=${token}` : ""}`;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (ev) => {
      try {
        const event: AIEvent = JSON.parse(ev.data);
        handleEvent(event);
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      // SSE errors can happen on close — only set error if we're still streaming
      setState((prev) => {
        if (prev.status === "streaming" || prev.status === "invoking") {
          return { ...prev, status: "error", error: "Stream connection lost" };
        }
        return prev;
      });
    };
  }, []);

  // ─── Handle Event ────────────────────────────────────────────────────────

  const handleEvent = useCallback((event: AIEvent) => {
    setState((prev) => {
      const events = [...prev.events, event];

      // Update progress
      let progress = prev.progress;
      if (event.progress) {
        progress = event.progress;
      }

      // Handle approval requests
      let approvalRequest = prev.approvalRequest;
      if (event.type === "approval.requested") {
        approvalRequest = {
          node_id: event.data?.node_id || "",
          tool: event.data?.tool || event.tool || "",
          reason: event.data?.reason || "This action requires your approval.",
        };
        return {
          ...prev,
          events,
          progress,
          approvalRequest,
          status: "waiting_approval",
        };
      }

      // Handle session completion
      if (event.type === "runtime.session.completed") {
        const response = event.data?.response || null;
        return {
          ...prev,
          events,
          progress,
          response,
          status: "completed",
        };
      }

      // Handle session error
      if (event.type === "runtime.session.error") {
        return {
          ...prev,
          events,
          progress,
          status: "error",
          error: event.data?.error || "Session failed",
        };
      }

      // Handle cancellation
      if (event.type === "runtime.session.cancelled") {
        return {
          ...prev,
          events,
          progress,
          status: "cancelled",
        };
      }

      // Handle approval granted/denied
      if (event.type === "approval.granted") {
        approvalRequest = null;
        return {
          ...prev,
          events,
          progress,
          approvalRequest,
          status: "streaming",
        };
      }
      if (event.type === "approval.denied") {
        approvalRequest = null;
        return {
          ...prev,
          events,
          progress,
          approvalRequest,
          status: "completed",
        };
      }

      return { ...prev, events, progress };
    });
  }, []);

  // ─── Approve ─────────────────────────────────────────────────────────────

  const approve = useCallback(async (decisionId: string, choice: "approve" | "deny") => {
    try {
      await apiPost("/runtime/approve", {
        decision_id: decisionId,
        choice,
      });
      setState((prev) => ({
        ...prev,
        approvalRequest: null,
        status: choice === "approve" ? "streaming" : "completed",
      }));
    } catch (err: any) {
      setState((prev) => ({ ...prev, error: err.message }));
    }
  }, []);

  // ─── Cancel ──────────────────────────────────────────────────────────────

  const cancel = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;
    try {
      await apiPost("/runtime/cancel", { session_id: sessionId });
      setState((prev) => ({ ...prev, status: "cancelled" }));
    } catch (err: any) {
      setState((prev) => ({ ...prev, error: err.message }));
    }
  }, []);

  // ─── Reset ───────────────────────────────────────────────────────────────

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    sessionIdRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  // ─── Cleanup on unmount ──────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    invoke,
    approve,
    cancel,
    reset,
    sessionId: sessionIdRef.current,
  };
}

// ─── Dashboard Overview Hook ───────────────────────────────────────────────

export function useDashboardOverview(brandId: string | null) {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!brandId) return;
    try {
      setLoading(true);
      const res = await apiGet<DashboardOverview>(`/dashboard/overview?brand_id=${brandId}`);
      setData(res);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export interface DashboardOverview {
  greeting: {
    text: string;
    action_buttons: { label: string; intent?: string; href?: string }[];
    memory_reference: string;
  };
  performance: {
    kpis: { label: string; value: number | string; trend: string; trend_up: boolean }[];
  };
  campaigns: {
    active: { id: string; name: string; goal: string; status: string }[];
    pending: { id: string; name: string; status: string }[];
  };
  notifications: {
    items: any[];
    count: number;
  };
  tasks: {
    ai_team: { agent: string; status: string; detail: string; icon: string }[];
  };
  memory: {
    recent_learnings: string[];
    total_campaigns: number;
    average_roi: string;
  };
  orb: {
    state: string;
    suggestions: string[];
  };
  activity: {
    items: {
      id: string;
      entry_type: string;
      actor: string;
      title: string;
      summary: string | null;
      created_at: string;
    }[];
  };
}

// ─── Timeline Hook ─────────────────────────────────────────────────────────

export function useTimeline(brandId: string | null, limit = 50) {
  const [items, setItems] = useState<TimelineEntry[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (cursor?: string) => {
    if (!brandId) return;
    try {
      setLoading(true);
      let path = `/timeline?brand_id=${brandId}&limit=${limit}`;
      if (cursor) path += `&cursor=${cursor}`;
      const res = await apiGet<{ items: TimelineEntry[]; next_cursor: string | null }>(path);
      if (cursor) {
        setItems((prev) => [...prev, ...res.items]);
      } else {
        setItems(res.items);
      }
      setNextCursor(res.next_cursor);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [brandId, limit]);

  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  return { items, nextCursor, loading, error, loadMore: () => fetchPage(nextCursor || undefined), refetch: () => fetchPage() };
}

// ─── Replay a timeline entry ─────────────────────────────────────────────────

export async function replayTimelineEntry(entryId: string, inputOverrides?: Record<string, any>): Promise<{ session_id: string; status: string }> {
  return apiPost(`/timeline/${entryId}/replay`, { input_overrides: inputOverrides ?? {} });
}

export interface TimelineEntry {
  id: string;
  brand_id: string | null;
  session_id: string | null;
  decision_id: string | null;
  entry_type: string;
  actor: string;
  title: string;
  summary: string | null;
  detail: Record<string, any>;
  replayable: boolean;
  replay_inputs: Record<string, any> | null;
  created_at: string;
}
