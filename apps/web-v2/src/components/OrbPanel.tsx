"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { AIOrb } from "./AIOrb";
import { useRuntimeSession, type AIEvent } from "@/lib/runtime";
import {
  type OrbState,
  ORB_STATE_LABELS,
  ORB_STATE_DESCRIPTIONS,
  orbStateFromEvent,
  isOrbActive,
} from "@/lib/orb-states";
import {
  isSpeechRecognitionAvailable,
  isSpeechSynthesisAvailable,
  speak,
  stopSpeaking,
} from "@/lib/voice";
import { ArtefactRenderer, type Artefact } from "./ArtefactRenderer";

interface OrbPanelProps {
  brandId: string | null;
  onClose: () => void;
}

interface ChatMessage {
  role: "user" | "ai";
  content: string;
  timestamp: string;
  suggestions?: string[];
  isClarifying?: boolean;
  explanation?: string;
  artefacts?: Artefact[];
}

/**
 * OrbPanel — the full PRACHAR AI conversation interface.
 *
 * Replaces the placeholder in the app layout.
 * Handles: text input, voice input, SSE event streaming, approval dialogs,
 * progress indicators, and TTS.
 */
export function OrbPanel({ brandId, onClose }: OrbPanelProps) {
  const session = useRuntimeSession();
  const [orbState, setOrbState] = useState<OrbState>("idle");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [progressSteps, setProgressSteps] = useState<{ label: string; status: "pending" | "running" | "done" | "error" }[]>([]);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasGreeted = useRef(false);

  // ─── Greet on open — the orb speaks first ────────────────────────────────
  useEffect(() => {
    if (hasGreeted.current) return;
    hasGreeted.current = true;
    const greeting = "Hi! I'm your AI marketing partner. What are we building today?";
    setMessages([{ role: "ai", content: greeting, timestamp: new Date().toISOString(), suggestions: [] }]);
    if (isSpeechSynthesisAvailable()) {
      setOrbState("speaking");
      speak(greeting, () => setOrbState("idle"));
    }
  }, []);

  // ─── Derive orb state from latest event ──────────────────────────────────

  useEffect(() => {
    if (session.events.length === 0) return;
    const latest = session.events[session.events.length - 1];
    if (!latest) return;
    const newState = (latest.orb_state as OrbState) || orbStateFromEvent(latest.type);
    setOrbState(newState);

    // Handle completion — add AI message + SPEAK
    if (latest.type === "runtime.session.completed" && latest.data?.response) {
      const response = latest.data.response;
      const isClarifying = latest.data?.clarifying === true;
      const replyText = response.reply || "Done!";
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: replyText,
          timestamp: latest.timestamp,
          suggestions: response.suggested_actions || [],
          isClarifying,
        },
      ]);

      // Always speak the response — this is a conversation orb
      if (isSpeechSynthesisAvailable()) {
        setOrbState("speaking");
        speak(replyText, () => {
          setOrbState("idle");
        });
      } else {
        setTimeout(() => setOrbState("idle"), 2000);
      }
    }

    // Handle error
    if (latest.type === "runtime.session.error") {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: latest.data?.error || "Something went wrong. Let me try again.",
          timestamp: latest.timestamp,
        },
      ]);
      setTimeout(() => setOrbState("idle"), 3000);
    }

    // Step 2: Show planner explanation before tools run
    if (latest.type === "planner.decision.created" && latest.data?.user_explanation) {
      const explanation = latest.data.user_explanation;
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "",
          timestamp: latest.timestamp,
          explanation,
        },
      ]);
    }

    // Track progress steps from tool events
    if (latest.type === "tool.started" && latest.tool) {
      setProgressSteps((prev) => [
        ...prev,
        { label: latest.tool!, status: "running" },
      ]);
    }
    if (latest.type === "tool.completed" && latest.tool) {
      setProgressSteps((prev) =>
        prev.map((s) => (s.label === latest.tool && s.status === "running" ? { ...s, status: "done" } : s))
      );
    }
    if (latest.type === "tool.error" && latest.tool) {
      setProgressSteps((prev) =>
        prev.map((s) => (s.label === latest.tool && s.status === "running" ? { ...s, status: "error" } : s))
      );
    }

    // Phase D: Handle artefact events — render rich UI components inline
    if (latest.type.startsWith("artefact.") && latest.data?.artefact) {
      const artefact = latest.data.artefact as Artefact;
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "",
          timestamp: latest.timestamp,
          artefacts: [artefact],
        },
      ]);
    }
  }, [session.events]);

  // ─── Auto-scroll ─────────────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, progressSteps]);

  // ─── Send message ────────────────────────────────────────────────────────

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;
    if (!brandId) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text, timestamp: new Date().toISOString() },
        {
          role: "ai",
          content: "I need a brand to work with. Please create a brand first from the Brands page.",
          timestamp: new Date().toISOString(),
        },
      ]);
      setInput("");
      return;
    }

    // Add user message
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, timestamp: new Date().toISOString() },
    ]);
    setInput("");
    setProgressSteps([]);
    setOrbState("understanding");

    // Invoke runtime
    await session.invoke(text, brandId, "text");
  }, [brandId, session]);

  // ─── Voice input ─────────────────────────────────────────────────────────

  const startListening = useCallback(() => {
    if (!isSpeechRecognitionAvailable()) {
      // Fallback: just focus the text input
      inputRef.current?.focus();
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsListening(true);
      setOrbState("listening");
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      // Auto-send when recognition finalizes — no wake word needed
      if (event.results[0][0].isFinal) {
        const text = transcript.trim();
        if (text) {
          recognition.stop();
          sendMessage(text);
        }
      }
    };

    recognition.onerror = () => {
      setIsListening(false);
      setOrbState("idle");
    };

    recognition.onend = () => {
      setIsListening(false);
      if (orbState === "listening") {
        setOrbState("idle");
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [sendMessage, orbState]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  // ─── Handle approval ─────────────────────────────────────────────────────

  const handleApprove = useCallback((choice: "approve" | "deny") => {
    if (session.events.length === 0) return;
    const decisionEvent = session.events.find((e) => e.decision_id);
    if (!decisionEvent?.decision_id) return;
    session.approve(decisionEvent.decision_id, choice);
  }, [session]);

  // ─── Handle cancel ───────────────────────────────────────────────────────

  const handleCancel = useCallback(() => {
    session.cancel();
    stopSpeaking();
    setOrbState("cancelled");
    setTimeout(() => setOrbState("idle"), 2000);
  }, [session]);

  // ─── Suggestion click ────────────────────────────────────────────────────

  const handleSuggestion = useCallback((suggestion: string) => {
    sendMessage(suggestion);
  }, [sendMessage]);

  // ─── Cleanup ─────────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      stopSpeaking();
      recognitionRef.current?.stop();
    };
  }, []);

  const active = isOrbActive(orbState);
  const showProgress = progressSteps.length > 0 && active;
  const showApproval = session.status === "waiting_approval" && session.approvalRequest;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="fixed bottom-20 right-4 lg:right-6 z-50 w-[440px] max-w-[calc(100vw-2rem)] glass-strong rounded-2xl border border-white/[0.08] overflow-hidden flex flex-col"
      style={{ maxHeight: "70vh" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/[0.04]">
        <div className="flex items-center gap-3">
          <AIOrb state={orbState} size={36} showWaves={active} />
          <div>
            <div className="text-sm font-semibold">PRACHAR AI</div>
            <div className="text-[10px] text-text-muted">
              {ORB_STATE_DESCRIPTIONS[orbState]}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {active && (
            <button
              onClick={handleCancel}
              className="text-[10px] px-2 py-1 rounded-lg bg-danger/10 text-danger hover:bg-danger/20 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text p-1"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Body — conversation + progress + approval */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[280px]">
        {/* Messages */}
        {messages.length === 0 && !active && (
          <div className="flex flex-col items-center justify-center py-8">
            <AIOrb state="idle" size={80} showWaves={false} />
            <p className="mt-6 text-sm text-text-secondary text-center max-w-xs">
              What are we building today?
            </p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              {["Create campaign", "How are my ads doing?", "Generate an image", "What needs attention?"].map((s) => (
                <button
                  key={s}
                  onClick={() => handleSuggestion(s)}
                  className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-text-secondary hover:text-text hover:border-white/[0.1] transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "flex",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm",
                msg.role === "user"
                  ? "bg-gradient-to-br from-accent to-orange-500 text-bg"
                  : "bg-white/[0.04] border border-white/[0.06] text-text",
                msg.isClarifying && "border-yellow-400/20 bg-yellow-400/[0.04]"
              )}
            >
              {msg.isClarifying && (
                <div className="text-[10px] text-yellow-400 mb-1 font-medium">
                  ✦ Clarifying
                </div>
              )}
              {msg.explanation && (
                <div className="text-[11px] text-text-muted mb-1.5 italic border-l-2 border-accent/30 pl-2">
                  {msg.explanation}
                </div>
              )}
              {msg.content}
              {msg.artefacts && msg.artefacts.length > 0 && (
                <div className="mt-2 space-y-2">
                  {msg.artefacts.map((artefact, j) => (
                    <ArtefactRenderer
                      key={j}
                      artefact={artefact}
                      onAction={(action) => handleSuggestion(action)}
                    />
                  ))}
                </div>
              )}
              {Array.isArray(msg.suggestions) && msg.suggestions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.suggestions.map((s, j) => (
                    <button
                      key={j}
                      onClick={() => handleSuggestion(s)}
                      className="px-2 py-1 rounded-lg bg-white/[0.06] text-[11px] text-text-secondary hover:text-text hover:bg-white/[0.1] transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {/* Progress indicator */}
        {showProgress && (
          <div className="space-y-1.5 py-2">
            {progressSteps.map((step, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div
                  className={cn(
                    "w-4 h-4 rounded-full flex items-center justify-center text-[10px]",
                    step.status === "done" && "bg-green-500/20 text-green-400",
                    step.status === "running" && "bg-accent/20 text-accent",
                    step.status === "error" && "bg-red-500/20 text-red-400",
                    step.status === "pending" && "bg-white/[0.04] text-text-muted"
                  )}
                >
                  {step.status === "done" ? "✓" : step.status === "error" ? "⚠" : step.status === "running" ? "●" : "○"}
                </div>
                <span className={cn(
                  "text-text-secondary",
                  step.status === "running" && "text-text",
                  step.status === "done" && "text-text-muted line-through"
                )}>
                  {step.label}
                </span>
                {step.status === "running" && (
                  <span className="text-text-muted animate-pulse">...</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Approval dialog */}
        <AnimatePresence>
          {showApproval && session.approvalRequest && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="rounded-xl border border-yellow-400/20 bg-yellow-400/[0.04] p-4 space-y-3"
            >
              <div className="flex items-center gap-2">
                <span className="text-yellow-400 text-lg">⚠</span>
                <span className="text-sm font-semibold text-yellow-400">Approval needed</span>
              </div>
              <p className="text-sm text-text-secondary">
                {session.approvalRequest.reason}
              </p>
              <p className="text-xs text-text-muted">
                Action: {session.approvalRequest.tool}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleApprove("approve")}
                  className="flex-1 px-3 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/30 transition-colors"
                >
                  ✓ Approve
                </button>
                <button
                  onClick={() => handleApprove("deny")}
                  className="flex-1 px-3 py-2 rounded-lg bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-colors"
                >
                  ✕ Deny
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/[0.04] flex gap-2">
        <button
          onClick={isListening ? stopListening : startListening}
          className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center transition-colors flex-shrink-0",
            isListening
              ? "bg-danger text-white animate-pulse"
              : "bg-white/[0.03] text-text-secondary hover:text-text"
          )}
          aria-label={isListening ? "Stop listening" : "Start voice input"}
        >
          🎤
        </button>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
          placeholder={isListening ? "Listening..." : "Type or speak to PRACHAR AI..."}
          disabled={active}
          className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm outline-none focus:border-accent/30 transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || active}
          className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-orange-500 text-bg flex items-center justify-center font-bold disabled:opacity-30 flex-shrink-0"
        >
          ↑
        </button>
      </div>
    </motion.div>
  );
}
