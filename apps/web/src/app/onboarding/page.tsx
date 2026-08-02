"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { apiPost } from "@/lib/api";
import { setToken, getToken } from "@/lib/auth";
import type {
  ConsultResponse,
  CampaignPreviewResponse,
  BusinessUnderstanding,
  GrowthOpportunity,
  WeekPlan,
  CampaignPreview,
} from "@/lib/consult";
import type {
  CreatorConsultResponse,
  CreatorCampaignResponse,
  CreatorProfile,
  CreatorPosition,
  CreatorWeekPlan,
} from "@/lib/creator";
import { BUSINESS_TYPES, CREATOR_TYPES } from "@/lib/creator-types";
import {
  Sparkles,
  Send,
  ArrowRight,
  Check,
  TrendingUp,
  Target,
  Clock,
  AlertCircle,
  Zap,
  Eye,
  Video,
  Image as ImageIcon,
  Lightbulb,
  Calendar,
  RefreshCw,
  Edit3,
  CheckCircle2,
  Loader2,
  Building2,
  Palette,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Phases of the conversation ────────────────────────────────────────────

type CustomerType = "business" | "creator" | null;

type Phase =
  | "auth"        // Need to sign in first
  | "type_select" // "Tell me who you are" — Business or Creator?
  | "subtype_select" // Pick specific business/creator type
  | "intro"       // PRACHAR AI's opening message
  | "listening"   // User is typing their description
  | "analysing"   // PRACHAR AI is analysing (loading)
  | "understanding" // Show understanding cards (business or creator)
  | "opportunities" // Show growth opportunities
  | "plan"        // Show 30-day plan
  | "campaign_generating" // Building campaign preview
  | "campaign"    // Show campaign preview
  | "approved"    // Campaign approved → go to dashboard
  | "error";

// ─── Chat message type ─────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

// ─── Main component ────────────────────────────────────────────────────────

export default function ConversationalOnboardingPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("type_select");
  const [customerType, setCustomerType] = useState<CustomerType>(null);
  const [subType, setSubType] = useState<string>(""); // e.g. "youtube_creator" or "restaurant"
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [consultResponse, setConsultResponse] = useState<ConsultResponse | null>(null);
  const [creatorResponse, setCreatorResponse] = useState<CreatorConsultResponse | null>(null);
  const [campaignResponse, setCampaignResponse] = useState<CampaignPreviewResponse | null>(null);
  const [creatorCampaignResponse, setCreatorCampaignResponse] = useState<CreatorCampaignResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [lastMessage, setLastMessage] = useState("");  // for retry on error
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, phase]);

  // Focus input when ready
  useEffect(() => {
    if (phase === "intro" || phase === "listening") {
      inputRef.current?.focus();
    }
  }, [phase]);

  // Check auth
  useEffect(() => {
    if (!getToken()) {
      setPhase("auth");
    }
  }, []);

  // ─── Send business description ──────────────────────────────────────────

  const sendDescription = useCallback(async () => {
    const text = input.trim();
    if (!text || text.length < 5) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLastMessage(text);  // save for retry
    setPhase("analysing");
    setErrorMsg("");

    try {
      if (customerType === "creator") {
        const res = await apiPost<CreatorConsultResponse>("/creator/consult", {
          message: text,
          creator_type: subType || "youtube_creator",
        });
        setCreatorResponse(res);
        const broMsg: ChatMessage = {
          id: `b-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, broMsg]);
        setPhase("understanding");
      } else {
        const res = await apiPost<ConsultResponse>("/consult", { message: text });
        setConsultResponse(res);
        const broMsg: ChatMessage = {
          id: `b-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, broMsg]);
        setPhase("understanding");
      }
    } catch (e) {
      console.error("Consult API error:", e);
      const status = (e as { status?: number }).status;
      let msg = customerType === "creator"
        ? "I couldn't analyse your channel right now."
        : "I couldn't analyse your business right now.";
      if (status === 401) {
        msg += " Your session may have expired — please refresh and log in again.";
      } else if (status === 500) {
        msg += " The server had a temporary issue. Please try again in a moment.";
      } else if (status === 429) {
        msg += " Rate limit reached. Please wait a minute and try again.";
      } else {
        msg += " Please check your connection and try again.";
      }
      setErrorMsg(msg);
      setPhase("error");
    }
  }, [input, customerType, subType]);

  // ─── Retry with the same message ─────────────────────────────────────
  const retryDescription = useCallback(async () => {
    if (!lastMessage) {
      setPhase("listening");
      return;
    }
    setInput(lastMessage);
    setPhase("listening");
    // Auto-retry: re-invoke sendDescription with the saved message
    const text = lastMessage;
    setLastMessage("");

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    // Remove the previous user message (duplicate) — keep only the latest
    setMessages((prev) => {
      // Drop the last user message if it's the same text (avoid duplicates on retry)
      const filtered = prev.filter(m => !(m.role === "user" && m.content === text));
      return [...filtered, userMsg];
    });
    setInput("");
    setLastMessage(text);
    setPhase("analysing");
    setErrorMsg("");

    try {
      if (customerType === "creator") {
        const res = await apiPost<CreatorConsultResponse>("/creator/consult", {
          message: text,
          creator_type: subType || "youtube_creator",
        });
        setCreatorResponse(res);
        setMessages((prev) => [...prev, {
          id: `b-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          timestamp: Date.now(),
        }]);
        setPhase("understanding");
      } else {
        const res = await apiPost<ConsultResponse>("/consult", { message: text });
        setConsultResponse(res);
        setMessages((prev) => [...prev, {
          id: `b-${Date.now()}`,
          role: "assistant",
          content: res.reply,
          timestamp: Date.now(),
        }]);
        setPhase("understanding");
      }
    } catch (e) {
      console.error("Consult API retry error:", e);
      const status = (e as { status?: number }).status;
      let msg = customerType === "creator"
        ? "I still couldn't analyse your channel."
        : "I still couldn't analyse your business.";
      if (status === 401) {
        msg += " Your session may have expired — please refresh and log in again.";
      } else if (status === 500) {
        msg += " The server is having issues. You can skip for now and try later from the dashboard.";
      } else {
        msg += " You can skip for now and try later from the dashboard.";
      }
      setErrorMsg(msg);
      setPhase("error");
    }
  }, [lastMessage, customerType, subType]);

  // ─── Generate campaign preview ──────────────────────────────────────────

  const generateCampaign = useCallback(async () => {
    const brandId = customerType === "creator"
      ? creatorResponse?.brand_id
      : consultResponse?.brand_id;
    if (!brandId) return;
    setPhase("campaign_generating");
    setErrorMsg("");

    const goal = customerType === "creator"
      ? (creatorResponse?.profile.growth_stage ? `grow from ${creatorResponse.profile.growth_stage.toLowerCase()} stage` : "grow my channel")
      : (consultResponse?.extracted.goals[0] || "grow the business");
    const budget = "₹15,000/month";

    try {
      if (customerType === "creator") {
        const res = await apiPost<CreatorCampaignResponse>("/creator/campaign", {
          brand_id: brandId,
          goal,
          budget,
        });
        setCreatorCampaignResponse(res);
        setPhase("campaign");
      } else {
        const res = await apiPost<CampaignPreviewResponse>("/consult/campaign", {
          brand_id: brandId,
          goal,
          budget,
        });
        setCampaignResponse(res);
        setPhase("campaign");
      }
    } catch (e) {
      setErrorMsg("I couldn't build the campaign right now. Please try again.");
      setPhase("understanding");
    }
  }, [consultResponse, creatorResponse, customerType]);

  // ─── Approve campaign → go to dashboard ─────────────────────────────────

  const approveCampaign = useCallback(() => {
    const brandId = customerType === "creator"
      ? creatorResponse?.brand_id
      : consultResponse?.brand_id;
    if (brandId) {
      window.localStorage.setItem("prachar_onboarded", "1");
      window.localStorage.setItem("prachar_active_brand", brandId);
      window.localStorage.setItem("prachar_customer_type", customerType ?? "business");
    }
    setPhase("approved");
    setTimeout(() => router.push("/app"), 1500);
  }, [consultResponse, creatorResponse, customerType, router]);

  // ─── Auth gate ──────────────────────────────────────────────────────────

  if (phase === "auth") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg px-4">
        <div className="glass-strong rounded-2xl p-8 max-w-md text-center">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-accent" />
          </div>
          <h1 className="font-display text-xl font-semibold text-text mb-2">
            Let's talk about you
          </h1>
          <p className="text-sm text-text-secondary mb-6">
            Sign up to start your conversation with PRACHAR AI — your AI strategist for business or creator growth.
          </p>
          <div className="flex flex-col gap-2">
            <button
              onClick={() => router.push("/register")}
              className="btn-primary w-full group"
            >
              Get started
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <button
              onClick={() => router.push("/login")}
              className="btn-secondary w-full"
            >
              I have an account
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ─── Type selection screen ("Tell me who you are") ───
  if (phase === "type_select") {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4">
        <div className="max-w-2xl w-full">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-8"
          >
            <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-7 h-7 text-accent" />
            </div>
            <h1 className="font-display text-2xl font-semibold text-text mb-2">
              Tell me who you are
            </h1>
            <p className="text-sm text-text-secondary">
              I'll tailor everything to your goals. Pick one to get started.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <TypeChoiceCard
              icon={<Building2 className="w-6 h-6 text-info" />}
              title="Business Growth"
              subtitle="Restaurants, clinics, retail, services"
              accent="info"
              onClick={() => {
                setCustomerType("business");
                setPhase("subtype_select");
              }}
            />
            <TypeChoiceCard
              icon={<Palette className="w-6 h-6 text-accent" />}
              title="Creator Growth"
              subtitle="YouTubers, podcasters, influencers"
              accent="accent"
              onClick={() => {
                setCustomerType("creator");
                setPhase("subtype_select");
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  // ─── Subtype selection (specific business or creator type) ───
  if (phase === "subtype_select") {
    const types = customerType === "creator" ? CREATOR_TYPES : BUSINESS_TYPES;
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4 py-8">
        <div className="max-w-3xl w-full">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-6"
          >
            <button
              onClick={() => setPhase("type_select")}
              className="text-xs text-text-muted hover:text-text mb-4 inline-flex items-center gap-1"
            >
              ← Back
            </button>
            <h1 className="font-display text-xl font-semibold text-text mb-1">
              {customerType === "creator" ? "What kind of creator are you?" : "What kind of business?"}
            </h1>
            <p className="text-sm text-text-secondary">
              Pick the closest match. You can change this later.
            </p>
          </motion.div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
            {types.map((t, i) => (
              <motion.button
                key={t.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => {
                  setSubType(t.id);
                  // Set the intro message based on customer type
                  const introMsg: ChatMessage = customerType === "creator"
                    ? {
                        id: "intro",
                        role: "assistant",
                        content: `Hey! I'm PRACHAR AI — your strategist for ${t.label.toLowerCase()} growth. Tell me about your channel. What's your niche, where do you post, who's your audience, and where do you want to be in 6 months? The more you share, the better I can help.`,
                        timestamp: Date.now(),
                      }
                    : {
                        id: "intro",
                        role: "assistant",
                        content: `Hey! I'm PRACHAR AI — your marketing strategist. Tell me about your ${t.label.toLowerCase()} business. What do you do, where, and who do you serve? The more you share, the better I can help.`,
                        timestamp: Date.now(),
                      };
                  setMessages([introMsg]);
                  setPhase("intro");
                }}
                className="glass hover:glass-strong rounded-xl p-4 text-center transition-all hover:scale-[1.02] hover:border-accent/30"
              >
                <div className="text-2xl mb-2">{t.emoji}</div>
                <div className="text-xs font-medium text-text leading-tight">{t.label}</div>
              </motion.button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const activeBrandId = customerType === "creator" ? creatorResponse?.brand_id : consultResponse?.brand_id;

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* ─── Header ─── */}
      <header className="border-b border-white/[0.04] px-4 lg:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-accent" />
          </div>
          <span className="font-display text-sm font-semibold text-text">PRACHAR AI</span>
          <span className="text-xs text-text-muted">
            · {customerType === "creator" ? "Your creator strategist" : "Your marketing strategist"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {phase !== "approved" && (
            <button
              onClick={() => {
                window.localStorage.setItem("prachar_onboarded", "1");
                window.localStorage.setItem("prachar_customer_type", customerType ?? "business");
                if (activeBrandId) {
                  window.localStorage.setItem("prachar_active_brand", activeBrandId);
                }
                router.push("/app");
              }}
              className="text-xs text-text-muted hover:text-text transition-colors"
            >
              Skip to dashboard →
            </button>
          )}
        </div>
      </header>

      {/* ─── Main content ─── */}
      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-4 lg:px-6">
        {/* Chat messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto py-6 space-y-4">
          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} />
          ))}

          {/* Analysing indicator */}
          {phase === "analysing" && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 text-text-secondary"
            >
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 text-accent animate-spin" />
              </div>
              <div className="space-y-1.5">
                <div className="text-sm">
                  {customerType === "creator" ? "Let me think about your channel…" : "Let me think about your business…"}
                </div>
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                      className="w-1.5 h-1.5 rounded-full bg-accent"
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Campaign generating indicator */}
          {phase === "campaign_generating" && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 text-text-secondary"
            >
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 text-accent animate-spin" />
              </div>
              <div className="space-y-1.5">
                <div className="text-sm">Building your campaign…</div>
                <div className="flex gap-1">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <motion.div
                      key={i}
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.15 }}
                      className="w-1.5 h-1.5 rounded-full bg-accent"
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Error */}
          {phase === "error" && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-danger/5 border border-danger/10">
              <AlertCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm text-danger">{errorMsg}</div>
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={retryDescription}
                    className="text-xs text-accent hover:underline"
                  >
                    Try again
                  </button>
                  <span className="text-text-muted text-xs">·</span>
                  <button
                    onClick={() => {
                      window.localStorage.setItem("prachar_onboarded", "1");
                      window.localStorage.setItem("prachar_customer_type", customerType ?? "business");
                      if (activeBrandId) {
                        window.localStorage.setItem("prachar_active_brand", activeBrandId);
                      }
                      router.push("/app");
                    }}
                    className="text-xs text-text-muted hover:text-text"
                  >
                    Skip to dashboard →
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ─── Insight cards (appear after analysis) ─── */}
        <AnimatePresence>
          {phase === "understanding" && consultResponse && customerType === "business" && (
            <InsightCards
              consultResponse={consultResponse}
              onContinue={() => setPhase("opportunities")}
            />
          )}
          {phase === "understanding" && creatorResponse && customerType === "creator" && (
            <CreatorInsightCards
              creatorResponse={creatorResponse}
              onContinue={() => setPhase("opportunities")}
            />
          )}
          {phase === "opportunities" && consultResponse && customerType === "business" && (
            <OpportunityCards
              opportunities={consultResponse.growth_opportunities}
              onContinue={() => setPhase("plan")}
              onBack={() => setPhase("understanding")}
            />
          )}
          {phase === "opportunities" && creatorResponse && customerType === "creator" && (
            <CreatorOpportunityCards
              position={creatorResponse.position}
              onContinue={() => setPhase("plan")}
              onBack={() => setPhase("understanding")}
            />
          )}
          {phase === "plan" && consultResponse && customerType === "business" && (
            <PlanTimeline
              plan={consultResponse.plan}
              onContinue={generateCampaign}
              onBack={() => setPhase("opportunities")}
            />
          )}
          {phase === "plan" && creatorResponse && customerType === "creator" && (
            <CreatorPlanTimeline
              plan={creatorResponse.plan}
              onContinue={generateCampaign}
              onBack={() => setPhase("opportunities")}
            />
          )}
          {phase === "campaign" && campaignResponse && customerType === "business" && (
            <CampaignDeck
              response={campaignResponse}
              onApprove={approveCampaign}
              onRegenerate={generateCampaign}
              onBack={() => setPhase("plan")}
            />
          )}
          {phase === "campaign" && creatorCampaignResponse && customerType === "creator" && (
            <CreatorCampaignDeck
              response={creatorCampaignResponse}
              onApprove={approveCampaign}
              onRegenerate={generateCampaign}
              onBack={() => setPhase("plan")}
            />
          )}
          {phase === "approved" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-12"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-4"
              >
                <Check className="w-8 h-8 text-success" />
              </motion.div>
              <h2 className="font-display text-xl font-semibold text-text">Campaign approved!</h2>
              <p className="text-sm text-text-secondary mt-1">Taking you to your dashboard…</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Input bar ─── */}
        {(phase === "intro" || phase === "listening") && (
          <div className="border-t border-white/[0.04] py-4">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendDescription();
                  }
                }}
                placeholder={customerType === "creator"
                  ? "Tell me about your channel… e.g. 'I make tech review videos on YouTube, 8K subscribers, post 1 video/week, want to grow to 50K.'"
                  : "Tell me about your business… e.g. 'We run a biryani restaurant in Hyderabad, 3 years old, want to grow catering.'"}
                rows={2}
                className="input-field flex-1 resize-none min-h-[60px] max-h-[120px]"
                disabled={false}
              />
              <button
                onClick={sendDescription}
                disabled={!input.trim() || input.trim().length < 5}
                className="btn-primary shrink-0 h-[60px] px-4"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-[11px] text-text-muted mt-2">
              Press Enter to send · Shift+Enter for new line
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Chat bubble ───────────────────────────────────────────────────────────

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex gap-3", isUser && "flex-row-reverse")}
    >
      <div className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
        isUser ? "bg-info/10" : "bg-accent/10",
      )}>
        {isUser ? (
          <span className="text-xs font-bold text-info">You</span>
        ) : (
          <Sparkles className="w-4 h-4 text-accent" />
        )}
      </div>
      <div className={cn(
        "rounded-2xl p-4 max-w-[80%]",
        isUser ? "bg-info/5 text-text" : "glass-strong text-text",
      )}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
    </motion.div>
  );
}

// ─── Insight cards: Business Understanding ─────────────────────────────────

function InsightCards({
  consultResponse,
  onContinue,
}: {
  consultResponse: ConsultResponse;
  onContinue: () => void;
}) {
  const b = consultResponse.business;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        Here's what I see
      </div>

      {/* Summary */}
      {b.summary && (
        <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
          <p className="text-sm text-text leading-relaxed">{b.summary}</p>
        </div>
      )}

      {/* Strengths + Weaknesses */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {b.strengths.length > 0 && (
          <InsightCard title="Your strengths" items={b.strengths} accent="success" icon={<CheckCircle2 className="w-4 h-4" />} />
        )}
        {b.weaknesses.length > 0 && (
          <InsightCard title="Where you can improve" items={b.weaknesses} accent="warning" icon={<AlertCircle className="w-4 h-4" />} />
        )}
      </div>

      {/* Customers + Competitors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {b.likely_customers.length > 0 && (
          <InsightCard title="Your likely customers" items={b.likely_customers} accent="info" icon={<Target className="w-4 h-4" />} />
        )}
        {b.likely_competitors.length > 0 && (
          <InsightCard title="Your competitors" items={b.likely_competitors} accent="danger" icon={<TrendingUp className="w-4 h-4" />} />
        )}
      </div>

      {/* Marketing maturity */}
      {b.marketing_maturity && (
        <div className="glass rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
            <Zap className="w-5 h-5 text-accent" />
          </div>
          <div>
            <div className="label-field">Marketing maturity</div>
            <div className="text-sm text-text mt-0.5">{b.marketing_maturity}</div>
          </div>
        </div>
      )}

      {/* Continue */}
      <div className="flex justify-end pt-2">
        <button onClick={onContinue} className="btn-primary group">
          See growth opportunities
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function InsightCard({
  title,
  items,
  accent,
  icon,
}: {
  title: string;
  items: string[];
  accent: "success" | "warning" | "info" | "danger";
  icon: React.ReactNode;
}) {
  const accentColor: Record<string, string> = {
    success: "text-success",
    warning: "text-warning",
    info: "text-info",
    danger: "text-danger",
  };
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className={accentColor[accent]}>{icon}</span>
        <span className="label-field">{title}</span>
      </div>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <div className={cn("w-1.5 h-1.5 rounded-full mt-2 shrink-0", (accentColor[accent] ?? "text-text-muted").replace("text-", "bg-"))} />
            <span className="text-sm text-text-secondary">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Growth opportunity cards ──────────────────────────────────────────────

function OpportunityCards({
  opportunities,
  onContinue,
  onBack,
}: {
  opportunities: GrowthOpportunity[];
  onContinue: () => void;
  onBack: () => void;
}) {
  const impactColor: Record<string, string> = {
    High: "badge-success",
    Medium: "badge-warning",
    Low: "badge-neutral",
  };
  const difficultyColor: Record<string, string> = {
    Easy: "badge-success",
    Medium: "badge-warning",
    Hard: "badge-danger",
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Lightbulb className="w-3.5 h-3.5 text-accent" />
        Top 5 growth opportunities
      </div>

      <div className="space-y-3">
        {opportunities.map((op, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="glass-strong rounded-xl p-4"
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 font-mono text-xs text-accent">
                  {i + 1}
                </div>
                <h3 className="font-display text-sm font-semibold text-text">{op.title}</h3>
              </div>
            </div>
            <p className="text-sm text-text-secondary ml-11 mb-3">{op.description}</p>
            <div className="flex flex-wrap gap-2 ml-11">
              <span className={cn("badge", impactColor[op.business_impact] ?? "badge-neutral")}>
                Impact: {op.business_impact}
              </span>
              <span className={cn("badge", difficultyColor[op.difficulty] ?? "badge-neutral")}>
                {op.difficulty}
              </span>
              <span className="badge badge-neutral flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {op.timeframe}
              </span>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary">← Back</button>
        <button onClick={onContinue} className="btn-primary group">
          See 30-day plan
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

// ─── 30-day plan timeline ──────────────────────────────────────────────────

function PlanTimeline({
  plan,
  onContinue,
  onBack,
}: {
  plan: WeekPlan[];
  onContinue: () => void;
  onBack: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Calendar className="w-3.5 h-3.5 text-accent" />
        Your 30-day marketing plan
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-accent/20" />

        <div className="space-y-4">
          {plan.map((week, i) => (
            <motion.div
              key={week.week}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="relative pl-12"
            >
              {/* Week dot */}
              <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-accent/10 border-2 border-accent/30 flex items-center justify-center font-mono text-xs text-accent">
                W{week.week}
              </div>

              <div className="glass-strong rounded-xl p-4">
                <h3 className="font-display text-sm font-semibold text-text mb-3">{week.theme}</h3>

                {week.objectives.length > 0 && (
                  <PlanSection label="Objectives" items={week.objectives} />
                )}
                {week.content.length > 0 && (
                  <PlanSection label="Content" items={week.content} />
                )}
                {week.offers.length > 0 && (
                  <PlanSection label="Offers" items={week.offers} />
                )}
                {week.channels.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {week.channels.map((ch, j) => (
                      <span key={j} className="badge badge-neutral text-[10px]">{ch}</span>
                    ))}
                  </div>
                )}
                {week.kpis.length > 0 && (
                  <PlanSection label="Track" items={week.kpis} accent="text-success" />
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary">← Back</button>
        <button onClick={onContinue} className="btn-primary group">
          <Zap className="w-4 h-4" />
          Build my campaign
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function PlanSection({
  label,
  items,
  accent = "text-text-secondary",
}: {
  label: string;
  items: string[];
  accent?: string;
}) {
  return (
    <div className="mt-3">
      <div className="label-field mb-1.5">{label}</div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <div className="w-1 h-1 rounded-full bg-text-muted mt-2 shrink-0" />
            <span className={cn("text-xs", accent)}>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Campaign preview deck ─────────────────────────────────────────────────

function CampaignDeck({
  response,
  onApprove,
  onRegenerate,
  onBack,
}: {
  response: CampaignPreviewResponse;
  onApprove: () => void;
  onRegenerate: () => void;
  onBack: () => void;
}) {
  const p = response.preview;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      {/* PRACHAR AI's pitch */}
      {response.reply && (
        <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <p className="text-sm text-text leading-relaxed">{response.reply}</p>
          </div>
        </div>
      )}

      {/* Campaign title */}
      <div className="glass-strong rounded-2xl p-6 text-center relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-accent/10 rounded-full blur-3xl" />
        <div className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 mb-3">
            <span className="font-mono text-[10px] text-accent uppercase tracking-wider">Campaign preview</span>
          </div>
          <h2 className="font-display text-2xl font-semibold text-text">{p.title}</h2>
          {p.confidence > 0 && (
            <div className="mt-2 inline-flex items-center gap-1.5 text-xs text-text-muted">
              <div className="w-1.5 h-1.5 rounded-full bg-success" />
              {Math.round(p.confidence)}% confidence this will work
            </div>
          )}
        </div>
      </div>

      {/* Why this campaign */}
      {p.why_this_campaign && (
        <Section title="Why this campaign" icon={<Lightbulb className="w-4 h-4 text-accent" />}>
          <p className="text-sm text-text-secondary leading-relaxed">{p.why_this_campaign}</p>
          {p.expected_benefit && (
            <p className="text-sm text-success mt-3 pt-3 border-t border-white/[0.04]">
              Expected: {p.expected_benefit}
            </p>
          )}
        </Section>
      )}

      {/* Creative concepts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {p.hero_image_concept && (
          <CreativeCard
            icon={<ImageIcon className="w-4 h-4 text-info" />}
            title="Hero image"
            description={p.hero_image_concept}
          />
        )}
        {p.video_concept && (
          <CreativeCard
            icon={<Video className="w-4 h-4 text-danger" />}
            title="Video concept"
            description={p.video_concept}
          />
        )}
      </div>

      {/* Post ideas */}
      {p.post_ideas.length > 0 && (
        <Section title="Post ideas" icon={<Sparkles className="w-4 h-4 text-accent" />}>
          <div className="space-y-2">
            {p.post_ideas.map((idea, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02]">
                <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center shrink-0 font-mono text-xs text-accent">
                  {i + 1}
                </div>
                <span className="text-sm text-text-secondary">{idea}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Estimates */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {p.estimated_reach && (
          <EstimateCard icon={<Eye className="w-4 h-4 text-info" />} label="Estimated reach" value={p.estimated_reach} />
        )}
        {p.expected_enquiries && (
          <EstimateCard icon={<Target className="w-4 h-4 text-success" />} label="Expected enquiries" value={p.expected_enquiries} />
        )}
        {p.budget_estimate && (
          <EstimateCard icon={<TrendingUp className="w-4 h-4 text-accent" />} label="Budget" value={p.budget_estimate} />
        )}
      </div>

      {/* Risks */}
      {p.risks.length > 0 && (
        <Section title="Things to watch" icon={<AlertCircle className="w-4 h-4 text-warning" />}>
          <ul className="space-y-2">
            {p.risks.map((risk, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2 shrink-0" />
                <span className="text-sm text-text-secondary">{risk}</span>
              </li>
            ))}
          </ul>
          {p.alternative && (
            <p className="text-xs text-text-muted mt-3 pt-3 border-t border-white/[0.04]">
              <span className="text-text font-medium">Backup plan:</span> {p.alternative}
            </p>
          )}
        </Section>
      )}

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-2 sticky bottom-4 z-10">
        <button onClick={onApprove} className="btn-primary flex-1 group text-base">
          <Check className="w-5 h-5" />
          Approve & launch
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
        <button onClick={onRegenerate} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Regenerate
        </button>
        <button onClick={onBack} className="btn-secondary">
          <Edit3 className="w-4 h-4" />
          Back
        </button>
      </div>
    </motion.div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="font-display text-sm font-semibold text-text">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function CreativeCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="label-field">{title}</span>
      </div>
      <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
    </div>
  );
}

function EstimateCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="label-field">{label}</span>
      </div>
      <div className="text-sm text-text font-medium">{value}</div>
    </div>
  );
}

// ─── Type choice card (Business vs Creator) ────────────────────────────────

function TypeChoiceCard({
  icon,
  title,
  subtitle,
  accent,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  accent: "info" | "accent";
  onClick: () => void;
}) {
  const ring: Record<string, string> = {
    info: "hover:border-info/40 hover:bg-info/[0.04]",
    accent: "hover:border-accent/40 hover:bg-accent/[0.04]",
  };
  return (
    <motion.button
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      onClick={onClick}
      className={cn(
        "glass-strong rounded-2xl p-6 text-left transition-all border border-white/[0.04]",
        ring[accent],
      )}
    >
      <div className="w-12 h-12 rounded-xl bg-white/[0.04] flex items-center justify-center mb-4">
        {icon}
      </div>
      <h3 className="font-display text-lg font-semibold text-text mb-1">{title}</h3>
      <p className="text-sm text-text-secondary">{subtitle}</p>
      <div className="mt-4 inline-flex items-center gap-1 text-xs text-accent">
        Continue
        <ArrowRight className="w-3.5 h-3.5" />
      </div>
    </motion.button>
  );
}

// ─── Creator insight cards ─────────────────────────────────────────────────

function CreatorInsightCards({
  creatorResponse,
  onContinue,
}: {
  creatorResponse: CreatorConsultResponse;
  onContinue: () => void;
}) {
  const p = creatorResponse.profile;
  const pos = creatorResponse.position;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        Here's what I see
      </div>

      {/* Profile summary */}
      <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          {p.niche && <ProfileField label="Niche" value={p.niche} />}
          {p.platforms.length > 0 && <ProfileField label="Platforms" value={p.platforms.join(", ")} />}
          {p.upload_frequency && <ProfileField label="Upload frequency" value={p.upload_frequency} />}
          {p.audience_size && <ProfileField label="Audience size" value={p.audience_size} />}
          {p.growth_stage && <ProfileField label="Growth stage" value={p.growth_stage} />}
          {p.monetisation && <ProfileField label="Monetisation" value={p.monetisation} />}
        </div>
        {p.content_pillars.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/[0.04]">
            <div className="label-field mb-2">Content pillars</div>
            <div className="flex flex-wrap gap-1.5">
              {p.content_pillars.map((pillar, i) => (
                <span key={i} className="badge badge-neutral">{pillar}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Strengths + Weaknesses */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {pos.strengths.length > 0 && (
          <InsightCard title="Your strengths" items={pos.strengths} accent="success" icon={<CheckCircle2 className="w-4 h-4" />} />
        )}
        {pos.weaknesses.length > 0 && (
          <InsightCard title="Where you can improve" items={pos.weaknesses} accent="warning" icon={<AlertCircle className="w-4 h-4" />} />
        )}
      </div>

      {/* Competitors */}
      {p.competitors.length > 0 && (
        <InsightCard title="Similar creators in your niche" items={p.competitors} accent="info" icon={<TrendingUp className="w-4 h-4" />} />
      )}

      {/* Continue */}
      <div className="flex justify-end pt-2">
        <button onClick={onContinue} className="btn-primary group">
          See growth opportunities
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label-field">{label}</div>
      <div className="text-text mt-0.5">{value}</div>
    </div>
  );
}

// ─── Creator opportunity cards ─────────────────────────────────────────────

function CreatorOpportunityCards({
  position,
  onContinue,
  onBack,
}: {
  position: CreatorPosition;
  onContinue: () => void;
  onBack: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Lightbulb className="w-3.5 h-3.5 text-accent" />
        Growth opportunities
      </div>

      {position.growth_opportunities.length > 0 && (
        <div className="space-y-3">
          <div className="label-field">Ways to grow your channel</div>
          {position.growth_opportunities.map((op, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="glass-strong rounded-xl p-4"
            >
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 font-mono text-xs text-accent">
                  {i + 1}
                </div>
                <p className="text-sm text-text-secondary">{op}</p>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {position.content_gaps.length > 0 && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className="w-4 h-4 text-warning" />
            <span className="label-field">Content you're missing</span>
          </div>
          <ul className="space-y-2">
            {position.content_gaps.map((gap, i) => (
              <li key={i} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2 shrink-0" />
                <span className="text-sm text-text-secondary">{gap}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {position.monetisation_opportunities.length > 0 && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-success" />
            <span className="label-field">Ways to earn more</span>
          </div>
          <ul className="space-y-2">
            {position.monetisation_opportunities.map((opp, i) => (
              <li key={i} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-success mt-2 shrink-0" />
                <span className="text-sm text-text-secondary">{opp}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary">← Back</button>
        <button onClick={onContinue} className="btn-primary group">
          See 30-day plan
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

// ─── Creator plan timeline ─────────────────────────────────────────────────

function CreatorPlanTimeline({
  plan,
  onContinue,
  onBack,
}: {
  plan: CreatorWeekPlan[];
  onContinue: () => void;
  onBack: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono">
        <Calendar className="w-3.5 h-3.5 text-accent" />
        Your 30-day growth plan
      </div>

      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-accent/20" />
        <div className="space-y-4">
          {plan.map((week, i) => (
            <motion.div
              key={week.week}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="relative pl-12"
            >
              <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-accent/10 border-2 border-accent/30 flex items-center justify-center font-mono text-xs text-accent">
                W{week.week}
              </div>
              <div className="glass-strong rounded-xl p-4">
                <h3 className="font-display text-sm font-semibold text-text mb-3">{week.theme}</h3>
                {week.videos.length > 0 && <CreatorPlanSection label="Videos" items={week.videos} icon={<Video className="w-3 h-3" />} />}
                {week.shorts.length > 0 && <CreatorPlanSection label="Shorts & Reels" items={week.shorts} icon={<Zap className="w-3 h-3" />} />}
                {week.community_posts.length > 0 && <CreatorPlanSection label="Community posts" items={week.community_posts} icon={<Sparkles className="w-3 h-3" />} />}
                {week.collaborations.length > 0 && <CreatorPlanSection label="Collaborations" items={week.collaborations} icon={<Target className="w-3 h-3" />} />}
                {week.seo.length > 0 && <CreatorPlanSection label="SEO" items={week.seo} icon={<TrendingUp className="w-3 h-3" />} />}
                {week.newsletter && (
                  <div className="mt-3">
                    <div className="label-field mb-1">Newsletter</div>
                    <p className="text-xs text-text-secondary">{week.newsletter}</p>
                  </div>
                )}
                {week.live_sessions && (
                  <div className="mt-3">
                    <div className="label-field mb-1">Live session</div>
                    <p className="text-xs text-text-secondary">{week.live_sessions}</p>
                  </div>
                )}
                {week.kpis.length > 0 && <CreatorPlanSection label="Track" items={week.kpis} icon={<CheckCircle2 className="w-3 h-3" />} accent="text-success" />}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button onClick={onBack} className="btn-secondary">← Back</button>
        <button onClick={onContinue} className="btn-primary group">
          <Zap className="w-4 h-4" />
          Build my campaign
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}

function CreatorPlanSection({
  label,
  items,
  icon,
  accent = "text-text-secondary",
}: {
  label: string;
  items: string[];
  icon: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="mt-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-text-muted">{icon}</span>
        <span className="label-field">{label}</span>
      </div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <div className="w-1 h-1 rounded-full bg-text-muted mt-2 shrink-0" />
            <span className={cn("text-xs", accent)}>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Creator campaign deck ─────────────────────────────────────────────────

function CreatorCampaignDeck({
  response,
  onApprove,
  onRegenerate,
  onBack,
}: {
  response: CreatorCampaignResponse;
  onApprove: () => void;
  onRegenerate: () => void;
  onBack: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="space-y-4 pb-4"
    >
      {response.reply && (
        <div className="glass-strong rounded-2xl p-5 border-l-2 border-l-accent/50">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <p className="text-sm text-text leading-relaxed">{response.reply}</p>
          </div>
        </div>
      )}

      <div className="glass-strong rounded-2xl p-6 text-center relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-accent/10 rounded-full blur-3xl" />
        <div className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 mb-3">
            <span className="font-mono text-[10px] text-accent uppercase tracking-wider">Content campaign</span>
          </div>
          <h2 className="font-display text-2xl font-semibold text-text">{response.title}</h2>
          {response.confidence > 0 && (
            <div className="mt-2 inline-flex items-center gap-1.5 text-xs text-text-muted">
              <div className="w-1.5 h-1.5 rounded-full bg-success" />
              {Math.round(response.confidence)}% confidence this will work
            </div>
          )}
        </div>
      </div>

      {response.publishing_schedule && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="w-4 h-4 text-accent" />
            <span className="label-field">Publishing schedule</span>
          </div>
          <p className="text-sm text-text-secondary">{response.publishing_schedule}</p>
        </div>
      )}

      {response.expected_growth && (
        <div className="glass rounded-xl p-4 border-l-2 border-l-success/50">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-success" />
            <span className="label-field">Expected in 30 days</span>
          </div>
          <p className="text-sm text-success">{response.expected_growth}</p>
        </div>
      )}

      {response.content_plan.length > 0 && (
        <div className="space-y-3">
          <div className="label-field">Weekly breakdown</div>
          {response.content_plan.map((week) => (
            <div key={week.week} className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center font-mono text-xs text-accent">
                  W{week.week}
                </div>
                <h4 className="font-display text-sm font-semibold text-text">{week.theme}</h4>
              </div>
              {week.videos.length > 0 && (
                <div className="text-xs text-text-secondary mb-2">
                  <span className="text-text font-medium">Videos:</span> {week.videos.join(" · ")}
                </div>
              )}
              {week.shorts.length > 0 && (
                <div className="text-xs text-text-secondary mb-2">
                  <span className="text-text font-medium">Shorts:</span> {week.shorts.join(" · ")}
                </div>
              )}
              {week.kpis.length > 0 && (
                <div className="text-xs text-success mt-2 pt-2 border-t border-white/[0.04]">
                  <span className="font-medium">Track:</span> {week.kpis.join(" · ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2 sticky bottom-4 z-10">
        <button onClick={onApprove} className="btn-primary flex-1 group text-base">
          <Check className="w-5 h-5" />
          Approve & start
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
        <button onClick={onRegenerate} className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Regenerate
        </button>
        <button onClick={onBack} className="btn-secondary">
          <Edit3 className="w-4 h-4" />
          Back
        </button>
      </div>
    </motion.div>
  );
}
