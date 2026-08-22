"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CurvOrb } from "@/components/CurvOrb";
import { ArtefactRenderer, type Artefact } from "@/components/ArtefactRenderer";
import { useActiveBrand } from "@/lib/hooks";
import { useRuntimeSession, type AIEvent } from "@/lib/runtime";
import {
  type OrbState,
  ORB_STATE_DESCRIPTIONS,
  orbStateFromEvent,
  isOrbActive,
} from "@/lib/orb-states";
import {
  isSpeechRecognitionAvailable,
  isSpeechSynthesisAvailable,
  speak,
  stopSpeaking,
  unlockSpeechSynthesis,
} from "@/lib/voice";
import { cn } from "@/lib/utils";
import {
  ArrowUp,
  Image as ImageIcon,
  Video,
  Paperclip,
  Mic,
  X,
  Sparkles,
  Plus,
} from "lucide-react";

// ─── Suggestion chips ───────────────────────────────────────────────────────
const SUGGESTIONS = [
  "Create Instagram campaign",
  "Make a 30s video ad",
  "Design a poster",
  "Promote this reel",
];

// ─── Time-based greeting ────────────────────────────────────────────────────
function getTimeGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 21) return "Good evening";
  return "Good night";
}

// ─── Extract a display name from email or brand ─────────────────────────────
function getDisplayName(email: string | null, brandName: string | null): string {
  if (email) {
    const localPart = email.split("@")[0] ?? "";
    const name = localPart
      .split(/[.\-_]/)
      .filter(Boolean)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())
      .join(" ");
    if (name && name.length > 0 && !/^\d+$/.test(name)) {
      return name;
    }
  }
  if (brandName) {
    const BAD_PATTERN = /\(not specified\)|\(unknown\)|^test\s/i;
    if (!BAD_PATTERN.test(brandName)) {
      return brandName;
    }
  }
  return "there";
}

interface AttachedFile {
  name: string;
  type: string;
  size: number;
  url: string;
}

interface ChatMessage {
  role: "user" | "ai";
  content: string;
  timestamp: string;
  attachments?: AttachedFile[];
  suggestions?: string[];
  isClarifying?: boolean;
  explanation?: string;
  artefacts?: Artefact[];
}

export default function DashboardPage() {
  const { brand } = useActiveBrand();
  const session = useRuntimeSession();

  // ─── Conversation state ───────────────────────────────────────────────────
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState("");
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [orbState, setOrbState] = useState<OrbState>("idle");
  const [isListening, setIsListening] = useState(false);
  const [progressSteps, setProgressSteps] = useState<
    { label: string; status: "pending" | "running" | "done" | "error" }[]
  >([]);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  const email = typeof window !== "undefined" ? localStorage.getItem("prachar_email") : null;
  const displayName = getDisplayName(email, brand?.name ?? null);
  const greeting = getTimeGreeting();

  // Conversation mode = at least one message has been sent
  const inConversation = messages.length > 0;
  const active = isOrbActive(orbState);
  const showProgress = progressSteps.length > 0 && active;
  const showApproval = session.status === "waiting_approval" && session.approvalRequest;

  // ─── Watch for invoke errors ──────────────────────────────────────────────
  useEffect(() => {
    if (session.status === "error" && session.error) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "ai" && last.content?.includes("couldn't connect")) return prev;
        return [
          ...prev,
          {
            role: "ai",
            content: "I couldn't connect to my AI brain right now. Please try again in a moment.",
            timestamp: new Date().toISOString(),
          },
        ];
      });
      setOrbState("idle");
    }
  }, [session.status, session.error]);

  // ─── Derive orb state from latest event + handle completion ───────────────
  useEffect(() => {
    if (session.events.length === 0) return;
    const latest = session.events[session.events.length - 1];
    if (!latest) return;
    const newState = (latest.orb_state as OrbState) || orbStateFromEvent(latest.type);
    setOrbState(newState);

    // Handle completion — add AI message
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

      if (isSpeechSynthesisAvailable()) {
        setOrbState("speaking");
        speak(replyText, () => setOrbState("idle"));
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

    // Planner explanation
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

    // Track progress steps
    if (latest.type === "tool.started" && latest.tool) {
      setProgressSteps((prev) => [
        ...prev,
        { label: latest.tool!, status: "running" },
      ]);
    }
    if (latest.type === "tool.completed" && latest.tool) {
      setProgressSteps((prev) =>
        prev.map((s) => (s.label === latest.tool && s.status === "running" ? { ...s, status: "done" } : s)),
      );
    }
    if (latest.type === "tool.error" && latest.tool) {
      setProgressSteps((prev) =>
        prev.map((s) => (s.label === latest.tool && s.status === "running" ? { ...s, status: "error" } : s)),
      );
    }

    // Artefact events
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

  // ─── Auto-scroll to bottom on new messages / progress ─────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, progressSteps]);

  // ─── Send message — uses the same runtime pipeline as OrbPanel ────────────
  const sendMessage = useCallback(async (text: string, atts?: AttachedFile[]) => {
    if (!text.trim() && (!atts || atts.length === 0)) return;
    unlockSpeechSynthesis();

    if (!brand?.id) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text, timestamp: new Date().toISOString(), attachments: atts },
        {
          role: "ai",
          content: "I need a brand to work with. Please create a brand first from the Brands page.",
          timestamp: new Date().toISOString(),
        },
      ]);
      return;
    }

    // Add user message
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, timestamp: new Date().toISOString(), attachments: atts },
    ]);
    setProgressSteps([]);
    setOrbState("understanding");

    try {
      await session.invoke(text, brand.id, "text");
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "I couldn't connect to my AI brain right now. Please try again in a moment.",
          timestamp: new Date().toISOString(),
        },
      ]);
      setOrbState("idle");
    }
  }, [brand?.id, session]);

  // ─── Submit prompt → inline conversation (NOT floating panel) ─────────────
  const handleSubmit = useCallback(() => {
    const text = prompt.trim();
    if (!text && attachments.length === 0) return;

    // Capture attachments to pass to message
    const attsCopy = [...attachments];
    sendMessage(text, attsCopy);

    // Reset input
    setPrompt("");
    setAttachments([]);
    if (inputRef.current) inputRef.current.style.height = "auto";
  }, [prompt, attachments, sendMessage]);

  // ─── Handle Enter to submit (Shift+Enter for newline) ─────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  // ─── Auto-resize textarea ─────────────────────────────────────────────────
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPrompt(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, []);

  // ─── File attachment handlers ─────────────────────────────────────────────
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>, category: string) => {
    const files = e.target.files;
    if (!files) return;
    const newAttachments: AttachedFile[] = Array.from(files).map((file) => ({
      name: file.name,
      type: category,
      size: file.size,
      url: URL.createObjectURL(file),
    }));
    setAttachments((prev) => [...prev, ...newAttachments]);
    e.target.value = "";
  }, []);

  const removeAttachment = useCallback((index: number) => {
    setAttachments((prev) => {
      const att = prev[index];
      if (att?.url) URL.revokeObjectURL(att.url);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  // ─── Voice input ──────────────────────────────────────────────────────────
  const startListening = useCallback(() => {
    const SpeechRecognition =
      (typeof window !== "undefined" && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)) || null;

    if (!SpeechRecognition) {
      inputRef.current?.focus();
      return;
    }

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
      setPrompt(transcript);
      if (event.results[0][0].isFinal) {
        const text = transcript.trim();
        if (text) {
          recognition.stop();
        }
      }
    };

    recognition.onerror = () => {
      setIsListening(false);
      setOrbState("idle");
    };

    recognition.onend = () => {
      setIsListening(false);
      if (orbState === "listening") setOrbState("idle");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [orbState]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
    setOrbState("idle");
  }, []);

  // ─── Handle approval ──────────────────────────────────────────────────────
  const handleApprove = useCallback((choice: "approve" | "deny") => {
    if (session.events.length === 0) return;
    const decisionEvent = session.events.find((e) => e.decision_id);
    if (!decisionEvent?.decision_id) return;
    session.approve(decisionEvent.decision_id, choice);
  }, [session]);

  // ─── Handle cancel ────────────────────────────────────────────────────────
  const handleCancel = useCallback(() => {
    session.cancel();
    stopSpeaking();
    setOrbState("cancelled");
    setTimeout(() => setOrbState("idle"), 2000);
  }, [session]);

  // ─── Suggestion chip click ────────────────────────────────────────────────
  const handleSuggestion = useCallback((suggestion: string) => {
    // In conversation mode, suggestions from AI responses should send immediately
    // On landing, suggestion chips populate the prompt for user to review
    if (inConversation) {
      sendMessage(suggestion);
    } else {
      setPrompt(suggestion);
      inputRef.current?.focus();
      requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.setSelectionRange(suggestion.length, suggestion.length);
        }
      });
    }
  }, [inConversation, sendMessage]);

  // ─── Orb click → focus inline prompt ──────────────────────────────────────
  const handleOrbClick = useCallback(() => {
    inputRef.current?.focus();
  }, []);

  // ─── Start new conversation (back to landing) ─────────────────────────────
  const handleNewChat = useCallback(() => {
    session.reset();
    setMessages([]);
    setProgressSteps([]);
    setPrompt("");
    setAttachments([]);
    setOrbState("idle");
    stopSpeaking();
  }, [session]);

  // ─── Cleanup ──────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopSpeaking();
      recognitionRef.current?.stop();
      attachments.forEach((a) => a.url && URL.revokeObjectURL(a.url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ═══════════════════════════════════════════════════════════════════════════
  // LANDING STATE — Orb hero, greeting, central copy, prompt, suggestion chips
  // ═══════════════════════════════════════════════════════════════════════════
  if (!inConversation) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex flex-col items-center justify-start px-4 py-8 lg:py-12">
        {/* ═══ Greeting ═══ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-2xl text-center"
        >
          <h1 className="font-display text-2xl lg:text-3xl font-semibold text-text">
            {greeting}, {displayName}{" "}
            <span className="inline-block animate-[wave_2s_ease-in-out_infinite] origin-[70%_70%]">
              👋
            </span>
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            What are we creating today?
          </p>
        </motion.div>

        {/* ═══ Orb — the hero ═══ */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 lg:mt-10"
        >
          <motion.button
            onClick={handleOrbClick}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="relative cursor-pointer"
            aria-label="Chat with CURV AI — click to focus the prompt"
          >
            <CurvOrb state={orbState} size={120} showWaves={orbState === "listening"} />
            <motion.div
              className="absolute inset-0 rounded-full pointer-events-none"
              animate={{
                boxShadow: [
                  "0 0 0 0px rgba(236,72,153,0.25)",
                  "0 0 0 16px rgba(139,92,246,0)",
                ],
              }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut" }}
            />
          </motion.button>
        </motion.div>

        {/* ═══ Central copy ═══ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="mt-8 text-center"
        >
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight leading-tight">
            Ask <span className="text-gradient-accent">CURV AI</span> anything
          </h2>
          <p className="mt-3 text-sm sm:text-base text-text-secondary max-w-lg mx-auto">
            Create campaigns, ads, videos, images or get insights — all in one place.
          </p>
        </motion.div>

        {/* ═══ Gemini-style multimodal input ═══ */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="mt-8 w-full max-w-2xl"
        >
          <PromptInput
            inputRef={inputRef}
            imageInputRef={imageInputRef}
            videoInputRef={videoInputRef}
            fileInputRef={fileInputRef}
            prompt={prompt}
            attachments={attachments}
            isListening={isListening}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSubmit={handleSubmit}
            onFileSelect={handleFileSelect}
            onRemoveAttachment={removeAttachment}
            onStartListening={startListening}
            onStopListening={stopListening}
          />
        </motion.div>

        {/* ═══ Suggestion chips ═══ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
          className="mt-6 flex flex-wrap gap-2 justify-center max-w-2xl"
        >
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSuggestion(suggestion)}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 min-h-[40px] rounded-full bg-white/[0.03] border border-white/[0.06] text-xs sm:text-sm text-text-secondary hover:bg-white/[0.06] hover:text-text hover:border-accent/20 transition-all cursor-pointer"
            >
              <Sparkles className="w-3 h-3 text-accent/60" />
              {suggestion}
            </button>
          ))}
        </motion.div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CONVERSATION STATE — inline Gemini-style chat
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* ─── Conversation header — small orb identity indicator ─── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.04]">
        <div className="flex items-center gap-3">
          <CurvOrb state={orbState} size={32} showWaves={active} />
          <div>
            <div className="text-sm font-semibold text-text">CURV AI</div>
            <div className="text-[10px] text-text-muted">
              {ORB_STATE_DESCRIPTIONS[orbState]}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {active && (
            <button
              onClick={handleCancel}
              className="text-[10px] px-2 py-1 rounded-lg bg-danger/10 text-danger hover:bg-danger/20 transition-colors min-h-[28px]"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleNewChat}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-text-secondary hover:text-text hover:bg-white/[0.06] transition-all min-h-[32px]"
            aria-label="Start new conversation"
            title="New chat"
          >
            <Plus className="w-3.5 h-3.5" />
            New chat
          </button>
        </div>
      </div>

      {/* ─── Messages — scrollable conversation area ─── */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-4">
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                  msg.role === "user"
                    ? "bg-gradient-to-br from-accent to-accent-dark text-white"
                    : "bg-white/[0.04] border border-white/[0.06] text-text",
                  msg.isClarifying && "border-amber-400/20 bg-amber-400/[0.04]",
                )}
              >
                {/* User attachments */}
                {msg.role === "user" && msg.attachments && msg.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {msg.attachments.map((att, j) => (
                      <div
                        key={j}
                        className="flex items-center gap-2 rounded-lg bg-bg/20 px-2 py-1"
                      >
                        {att.type === "image" ? (
                          <img
                            src={att.url}
                            alt={att.name}
                            className="w-8 h-8 rounded object-cover"
                          />
                        ) : (
                          <div className="w-8 h-8 rounded bg-bg/20 flex items-center justify-center">
                            {att.type === "video" ? (
                              <Video className="w-4 h-4" />
                            ) : (
                              <Paperclip className="w-4 h-4" />
                            )}
                          </div>
                        )}
                        <span className="text-xs max-w-[100px] truncate">{att.name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* AI clarifying badge */}
                {msg.isClarifying && (
                  <div className="text-[10px] text-amber-400 mb-1 font-medium">
                    ✦ Clarifying
                  </div>
                )}

                {/* AI planner explanation */}
                {msg.explanation && (
                  <div className="text-[11px] text-text-muted mb-1.5 italic border-l-2 border-accent/30 pl-2">
                    {msg.explanation}
                  </div>
                )}

                {/* Message content */}
                {msg.content && <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>}

                {/* Artefacts */}
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

                {/* AI suggestions */}
                {Array.isArray(msg.suggestions) && msg.suggestions.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {msg.suggestions.map((s, j) => (
                      <button
                        key={j}
                        onClick={() => handleSuggestion(s)}
                        className="px-2.5 py-1 rounded-lg bg-white/[0.06] text-[11px] text-text-secondary hover:text-text hover:bg-white/[0.1] transition-all min-h-[28px]"
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
                      step.status === "pending" && "bg-white/[0.04] text-text-muted",
                    )}
                  >
                    {step.status === "done" ? "✓" : step.status === "error" ? "⚠" : step.status === "running" ? "●" : "○"}
                  </div>
                  <span className={cn(
                    "text-text-secondary",
                    step.status === "running" && "text-text",
                    step.status === "done" && "text-text-muted line-through",
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
                className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4 space-y-3 max-w-2xl"
              >
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-lg">⚠</span>
                  <span className="text-sm font-semibold text-amber-400">Approval needed</span>
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
                    className="flex-1 px-3 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/30 transition-colors min-h-[40px]"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => handleApprove("deny")}
                    className="flex-1 px-3 py-2 rounded-lg bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-colors min-h-[40px]"
                  >
                    ✕ Deny
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ─── Sticky multimodal input at bottom ─── */}
      <div className="px-4 py-3 border-t border-white/[0.04]">
        <div className="max-w-2xl mx-auto">
          <PromptInput
            inputRef={inputRef}
            imageInputRef={imageInputRef}
            videoInputRef={videoInputRef}
            fileInputRef={fileInputRef}
            prompt={prompt}
            attachments={attachments}
            isListening={isListening}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSubmit={handleSubmit}
            onFileSelect={handleFileSelect}
            onRemoveAttachment={removeAttachment}
            onStartListening={startListening}
            onStopListening={stopListening}
          />
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// PromptInput — shared multimodal input component (used in both states)
// ═════════════════════════════════════════════════════════════════════════════
interface PromptInputProps {
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  imageInputRef: React.RefObject<HTMLInputElement | null>;
  videoInputRef: React.RefObject<HTMLInputElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  prompt: string;
  attachments: AttachedFile[];
  isListening: boolean;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>, category: string) => void;
  onRemoveAttachment: (index: number) => void;
  onStartListening: () => void;
  onStopListening: () => void;
}

function PromptInput({
  inputRef,
  imageInputRef,
  videoInputRef,
  fileInputRef,
  prompt,
  attachments,
  isListening,
  onInputChange,
  onKeyDown,
  onSubmit,
  onFileSelect,
  onRemoveAttachment,
  onStartListening,
  onStopListening,
}: PromptInputProps) {
  return (
    <div>
      <div
        className="group relative rounded-3xl border border-white/[0.08] bg-bg-card/80 backdrop-blur-xl transition-all duration-300 focus-within:border-accent/30 focus-within:shadow-glow"
        style={{ boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}
      >
        {/* Attachment previews */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 p-3 pb-0">
            {attachments.map((file, i) => (
              <div
                key={i}
                className="relative flex items-center gap-2 rounded-xl bg-white/[0.04] border border-white/[0.06] px-3 py-2 pr-8"
              >
                {file.type === "image" ? (
                  <img
                    src={file.url}
                    alt={file.name}
                    className="w-8 h-8 rounded-lg object-cover"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                    {file.type === "video" ? (
                      <Video className="w-4 h-4 text-accent" />
                    ) : (
                      <Paperclip className="w-4 h-4 text-accent" />
                    )}
                  </div>
                )}
                <span className="text-xs text-text-secondary max-w-[120px] truncate">
                  {file.name}
                </span>
                <button
                  onClick={() => onRemoveAttachment(i)}
                  className="absolute right-1.5 top-1.5 w-5 h-5 rounded-full bg-white/[0.06] hover:bg-white/[0.12] flex items-center justify-center transition-colors"
                  aria-label={`Remove ${file.name}`}
                >
                  <X className="w-3 h-3 text-text-secondary" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Text input area */}
        <textarea
          ref={inputRef}
          value={prompt}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder="Ask CURV AI anything…"
          rows={1}
          aria-label="Ask CURV AI anything"
          className="w-full bg-transparent text-text placeholder:text-text-muted text-sm sm:text-base px-5 pt-4 pb-2 resize-none outline-none max-h-[200px]"
          style={{ minHeight: "24px" }}
        />

        {/* Bottom controls bar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          {/* Left: attachment buttons */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => imageInputRef.current?.click()}
              className="w-9 h-9 rounded-xl hover:bg-white/[0.06] flex items-center justify-center transition-colors text-text-secondary hover:text-text"
              aria-label="Attach image"
              title="Image"
            >
              <ImageIcon className="w-[18px] h-[18px]" />
            </button>
            <button
              onClick={() => videoInputRef.current?.click()}
              className="w-9 h-9 rounded-xl hover:bg-white/[0.06] flex items-center justify-center transition-colors text-text-secondary hover:text-text"
              aria-label="Attach video"
              title="Video"
            >
              <Video className="w-[18px] h-[18px]" />
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-9 h-9 rounded-xl hover:bg-white/[0.06] flex items-center justify-center transition-colors text-text-secondary hover:text-text"
              aria-label="Attach file"
              title="File / Attach"
            >
              <Paperclip className="w-[18px] h-[18px]" />
            </button>
          </div>

          {/* Right: mic + send */}
          <div className="flex items-center gap-2">
            <button
              onClick={isListening ? onStopListening : onStartListening}
              className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                isListening
                  ? "bg-accent/20 text-accent animate-pulse"
                  : "hover:bg-white/[0.06] text-text-secondary hover:text-text"
              }`}
              aria-label={isListening ? "Stop listening" : "Start voice input"}
              title={isListening ? "Stop listening" : "Microphone"}
            >
              <Mic className="w-[18px] h-[18px]" />
            </button>
            <button
              onClick={onSubmit}
              disabled={!prompt.trim() && attachments.length === 0}
              className={`w-9 h-9 rounded-full flex items-center justify-center transition-all ${
                prompt.trim() || attachments.length > 0
                  ? "bg-gradient-to-br from-accent to-accent-dark text-white hover:scale-105 shadow-glow"
                  : "bg-white/[0.04] text-text-muted cursor-not-allowed"
              }`}
              aria-label="Send message"
              title="Send"
            >
              <ArrowUp className="w-[18px] h-[18px]" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Hidden file inputs */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => onFileSelect(e, "image")}
        aria-hidden="true"
      />
      <input
        ref={videoInputRef}
        type="file"
        accept="video/*"
        multiple
        className="hidden"
        onChange={(e) => onFileSelect(e, "video")}
        aria-hidden="true"
      />
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => onFileSelect(e, "file")}
        aria-hidden="true"
      />
    </div>
  );
}
