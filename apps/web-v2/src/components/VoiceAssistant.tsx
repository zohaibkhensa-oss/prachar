"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { X, Send, Mic, Volume2, Sparkles, Brain, Zap } from "lucide-react";
import { speak as sharedSpeak, stopSpeaking, unlockSpeechSynthesis, isSpeechSynthesisAvailable } from "@/lib/voice";

// ─── CURV AI Knowledge Base ─────────────────────────────────────────────────

interface KBEntry {
  keywords: string[];
  response: string;
  action?: string;
  navigate?: string;
}

const KNOWLEDGE_BASE: KBEntry[] = [
  {
    keywords: ["what is curv ai", "about curv ai", "tell me about", "what does curv ai do", "overview", "what is prachar", "about prachar", "what does prachar do"],
    response: "CURV AI is an AI-driven global advertising operating system. You upload your brand once, and CURV AI runs an autonomous weekly loop — measuring, diagnosing, generating content, publishing, optimizing budgets, and reporting across 16+ platforms worldwide. Think of it as having a full ad agency running 24/7, powered by AI, at SMB pricing.",
  },
  {
    keywords: ["mission control", "dashboard", "home", "main page", "overview page"],
    response: "Mission Control is your command center. It shows AI status (what the AI is currently doing), key metrics like spend and conversions, your visibility score, campaign health, a live timeline of all AI activity, today's wins, AI recommendations, and quick actions. Everything updates in real-time.",
    navigate: "/app",
  },
  {
    keywords: ["brand", "add brand", "create brand", "new brand", "brands page"],
    response: "The Brands page shows all your brands as rich 3D cards with visibility scores, connected platforms, campaign counts, and AI-generated insights. Click 'Add Brand' to create a new one. Each brand gets its own workspace with detailed analytics, competitor monitoring, and health tracking.",
    navigate: "/app/brands",
  },
  {
    keywords: ["campaign", "campaign studio", "kanban", "new campaign", "create campaign", "ad campaign"],
    response: "Campaign Studio is where you manage all your ad campaigns. It has a Kanban board with columns for Draft, In Review, Active, and Completed. You can drag campaigns between stages. The AI Campaign Builder on the right helps you create new campaigns — just describe your goal and it generates the campaign structure with audience targeting and budget recommendations.",
    navigate: "/app/campaigns",
  },
  {
    keywords: ["creative", "creative ai", "generate ad", "ad copy", "headline", "generate creative", "make ad"],
    response: "Creative AI is one of CURV AI's most powerful features. You describe what you want in the prompt box, select a brand and channel, and the AI generates multiple ad variants — headlines, copy, and visual descriptions. Each variant gets a confidence score and predicted CTR. You can approve, reject, or edit any variant. The system also evolves creatives automatically — winners get mutated children, losers get retired.",
    navigate: "/app/creative",
  },
  {
    keywords: ["channel", "channels", "connect", "platform", "google", "meta", "instagram", "facebook", "tiktok", "youtube", "linkedin", "twitter", "x", "pinterest", "whatsapp", "telegram"],
    response: "The Channels page shows all 16+ available platforms as professional integration cards. Connected channels show account details, spend, reach, followers, campaign count, health status, and AI status. Disconnected channels have a Connect button that initiates the OAuth flow. Available channels include Google, YouTube, Instagram, Facebook, TikTok, LinkedIn, X, Pinterest, WhatsApp, Telegram, LINE, VK, Reddit, and Naver.",
    navigate: "/app/channels",
  },
  {
    keywords: ["analytics", "data", "metrics", "performance", "roas", "cpa", "ctr", "chart", "graph", "heatmap"],
    response: "Analytics provides world-class data visualization. You'll see performance rings for organic, paid, social, and AI citation scores. There are trend charts showing spend vs conversions over time, channel performance comparisons, a 7-by-24 heatmap showing when your audience is most active, and channel breakdown bars. You can switch between 7-day, 30-day, and 90-day views.",
    navigate: "/app/analytics",
  },
  {
    keywords: ["report", "reports", "pdf", "export", "weekly report", "funnel"],
    response: "Reports generates beautiful interactive reports with performance funnels, ROAS by channel, growth charts, and geographic performance. Each week, the AI automatically generates a summary of what happened. You can export any report as a PDF. Reports are also generated automatically at the end of each weekly loop cycle.",
    navigate: "/app/reports",
  },
  {
    keywords: ["audience", "targeting", "audience builder", "demographics", "interests", "geo", "lookalike"],
    response: "The Audience Builder lets you define exactly who you want to reach. You can select geographic regions, age ranges, gender, interests, search intents, and languages. The AI suggests audience refinements and shows estimated reach. Once you're happy with an audience, you can save it and push it directly to a campaign.",
    navigate: "/app/audience",
  },
  {
    keywords: ["visibility score", "score", "visibility", "what is score", "how is score calculated"],
    response: "The Visibility Score is a 0-100 composite metric that measures how visible your brand is across all channels. It's calculated as a weighted average of 5 dimensions: Organic Rank Index (35%), Social Reach Index (25%), AI Citation Rate (15%), Paid Efficiency (15%), and Momentum (10%). The score updates every week after the loop completes.",
  },
  {
    keywords: ["weekly loop", "autonomous loop", "ai loop", "what does the loop do", "automation", "automatic"],
    response: "The Weekly Loop is CURV AI's core engine. Every week, for each brand, it runs a 7-step chain: 1) Measure — pull metrics from all connected channels. 2) Diagnose — AI analyzes gaps and computes your visibility score. 3) Regenerate — AI creates new content for each channel and locale. 4) Policy Check — claims gate and channel-specific rules. 5) Publish — push content to channels (Reddit requires human approval). 6) Budget Realloc — softmax reallocation with 20% safety clamps. 7) Report — generate PDF and schedule next loop.",
  },
  {
    keywords: ["budget", "spend", "money", "cost", "allocator", "reallocate", "cap", "spend cap"],
    response: "CURV AI has multiple money safety features. The budget allocator uses softmax reallocation — it shifts budget toward better-performing networks with a 20% daily clamp to prevent wild swings. Spend caps are checked before every budget or bid call. There's also idempotency keys to prevent duplicate charges, and a dry-run mode that's on by default for the first 7 days.",
  },
  {
    keywords: ["ai", "artificial intelligence", "how does ai work", "ai engine", "model", "gpt", "claude", "anthropic", "openai"],
    response: "CURV AI uses a provider-abstraction layer called the AI Gateway. It primarily uses Anthropic Claude (Haiku for small tasks, Sonnet for medium, Opus for complex) with OpenAI GPT-4o as fallback. The gateway handles tiering (picking the right model for each task), caching (skip if same prompt was asked before), budgeting (per-tenant token limits), and JSON schema enforcement for structured outputs.",
  },
  {
    keywords: ["claims gate", "policy", "compliance", "blocked", "rejected", "guaranteed"],
    response: "The claims gate is CURV AI's compliance engine. It automatically strips or blocks claims like 'guaranteed number one', 'guaranteed results', medical claims, and financial promises. Every piece of generated content passes through the claims gate before publishing. This protects your brand from policy violations on ad platforms.",
  },
  {
    keywords: ["attribution", "pixel", "tracking", "conversion", "gclid", "fbclid", "first party"],
    response: "CURV AI includes a first-party attribution pixel. You install a JavaScript snippet on your website. It captures UTMs and click IDs like gclid for Google, fbclid for Meta, and ttclid for TikTok. When a conversion happens, it uses position-based attribution — 40% to first touch, 40% to last touch, and 20% spread across middle touches. You'll see both network-reported and pixel-verified CPA.",
  },
  {
    keywords: ["creative evolution", "evolution", "a/b test", "variant", "winner", "loser"],
    response: "Creative evolution is automatic. Every 7 days, the system classifies your creatives into winners, losers, and neutral based on CTR. Winners are those above median plus one standard deviation. Losers are below median minus one standard deviation. Losers get paused. Winners get 3 mutated children generated by the AI — same value proposition but different hooks. The full lineage is logged for audit.",
  },
  {
    keywords: ["marketplace", "install", "addon", "add-on", "plugin", "extension"],
    response: "The Marketplace is where you can install additional integrations and tools. Available add-ons include TikTok Ads Pro, GPT-4o Creative Engine, WhatsApp Business API, Heatmap Analytics, Auto A/B Testing, Competitor Spy, Voice Ad Generator, and Influencer Matcher. Some are free, some are paid.",
    navigate: "/app/marketplace",
  },
  {
    keywords: ["knowledge", "help", "documentation", "docs", "learn", "guide", "tutorial"],
    response: "The Knowledge Base has getting started guides, best practices, API reference, and tutorials. Featured guides include 'Getting Started with AI Advertising', 'Understanding Visibility Score', and 'Mastering the Weekly Loop'. You can also ask me anything right here!",
    navigate: "/app/knowledge",
  },
  {
    keywords: ["settings", "profile", "organization", "api token", "billing", "notifications", "account"],
    response: "Settings has 6 sections: Profile (your name, email, role), Organization (team members, plan), API Access (create tokens for programmatic access), Billing (usage, invoices, payment methods), Notifications (toggle alerts), and Appearance (theme preferences).",
    navigate: "/app/settings",
  },
  {
    keywords: ["locale", "region", "language", "multi-region", "country", "geo targeting", "international"],
    response: "CURV AI supports 14 locales including English (US, GB, IN, AU), Hindi, Arabic, Spanish, Portuguese, Indonesian, Japanese, Korean, German, French, and Russian. Each locale has its own cultural register, posting times, hashtag style, and recommended channels. The region router automatically picks the right channels — for example, India gets WhatsApp and Instagram, Korea gets Kakao and Naver, Japan gets LINE.",
  },
  {
    keywords: ["reddit", "human approval", "approve", "manual review"],
    response: "Reddit is special — CURV AI never auto-publishes to Reddit. All Reddit content goes to a human approval queue. The policy gate always returns 'needs human approval' for Reddit. This is because Reddit has strict anti-promotion rules and values authentic engagement. You'll need to manually approve each post before it goes live.",
  },
  {
    keywords: ["login", "sign in", "credentials", "password", "demo", "access", "how to login"],
    response: "You can log in with your email and password. For demo access, use demo@curv.app with password prachar123. If you don't have an account, click Register to create one — it's free for 14 days, no credit card required.",
    navigate: "/login",
  },
  {
    keywords: ["price", "pricing", "plan", "cost", "how much", "subscription", "tier"],
    response: "CURV AI has 3 plans. Starter is 499 rupees per month — 1 brand, 3 channels, weekly loop. Growth is 2,999 rupees — 5 brands, all channels, paid plus organic, audits and reports. Agency is 9,999 rupees — unlimited brands, multi-tenant, API access, and white-label PDF reports.",
  },
  {
    keywords: ["hello", "hi", "hey", "greetings", "good morning", "good evening", "namaste"],
    response: "Hello! I'm CURV AI's assistant. I know everything about the platform — features, channels, campaigns, creative AI, analytics, the weekly loop, and more. What would you like to know? You can type or speak to me.",
  },
  {
    keywords: ["thank", "thanks", "thank you", "great", "awesome", "nice", "cool"],
    response: "You're welcome! I'm always here if you need help. Just click the orb or press the mic button to talk to me.",
  },
  {
    keywords: ["command palette", "search", "shortcut", "cmd k", "control k", "quick navigation"],
    response: "Press Command K or Control K on your keyboard to open the Command Palette. It lets you jump to any page instantly — Mission Control, Brands, Campaigns, Creative AI, Channels, Analytics, Reports, and more. Just type and hit enter.",
  },
];

const SUGGESTED_QUESTIONS = [
  "What is CURV AI?",
  "How does the weekly loop work?",
  "What is a good ROAS?",
  "How do I improve my CTR?",
  "What's the difference between CBO and ABO?",
  "How does creative AI work?",
  "What is attribution modeling?",
  "How do I target lookalike audiences?",
];

// ─── Matching engine ────────────────────────────────────────────────────────

function findAnswer(query: string): KBEntry | null {
  const lower = query.toLowerCase();
  let best: { entry: KBEntry; score: number } | null = null;
  for (const entry of KNOWLEDGE_BASE) {
    let score = 0;
    for (const kw of entry.keywords) {
      if (lower.includes(kw)) {
        score += kw.split(" ").length * 2 + (lower.startsWith(kw) ? 3 : 0);
      }
    }
    if (score > 0 && (!best || score > best.score)) {
      best = { entry, score };
    }
  }
  return best?.entry ?? null;
}

const FALLBACK = "I'm not sure about that yet, but I'm always learning. Try asking me about brands, campaigns, creative AI, channels, analytics, the weekly loop, visibility scores, budget optimization, or any CURV AI feature. You can also say 'take me to' followed by a page name to navigate.";

// ─── Speech types ───────────────────────────────────────────────────────────

type SpeechRecognitionType = typeof window extends { SpeechRecognition: infer T } ? T : any;

// ─── Component ──────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "assistant";
  text: string;
  timestamp: number;
}

export function VoiceAssistant() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hi! I'm CURV AI. I know everything about the platform. Ask me anything — type or speak. Try: 'What is the weekly loop?' or 'Take me to campaigns'", timestamp: Date.now() },
  ]);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [orbPulse, setOrbPulse] = useState(false);
  const [wakeActive, setWakeActive] = useState(false);
  const [wakeDetected, setWakeDetected] = useState(false);

  const recognitionRef = useRef<any>(null);
  const wakeRecognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wakeEnabledRef = useRef(false);
  const activeListeningRef = useRef(false);

  // ─── Init speech synthesis ───
  useEffect(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  // ─── Scroll to bottom ───
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ─── Orb idle pulse ───
  useEffect(() => {
    const interval = setInterval(() => {
      setOrbPulse((v) => !v);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // ─── Speak function (uses shared voice.ts with iOS Safari fixes) ───
  const speak = useCallback((text: string) => {
    if (!isSpeechSynthesisAvailable()) return;
    setSpeaking(true);
    sharedSpeak(text, () => setSpeaking(false));
  }, []);

  // ─── Process query (LLM-powered with local fallback) ───
  const processQuery = useCallback(async (query: string) => {
    if (!query.trim()) return;

    const userMsg: Message = { role: "user", text: query, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setThinking(true);

    // Check for navigation commands first ("take me to X", "go to X")
    const navMatch = query.toLowerCase().match(/(?:take me to|go to|open|show me|navigate to)\s+(.+)/);
    const navTargets: Record<string, string> = {
      "dashboard": "/app", "mission control": "/app", "home": "/app",
      "brand": "/app/brands", "brands": "/app/brands",
      "campaign": "/app/campaigns", "campaigns": "/app/campaigns", "campaign studio": "/app/campaigns",
      "creative": "/app/creative", "creative ai": "/app/creative",
      "channel": "/app/channels", "channels": "/app/channels",
      "analytic": "/app/analytics", "analytics": "/app/analytics",
      "report": "/app/reports", "reports": "/app/reports",
      "audience": "/app/audience",
      "marketplace": "/app/marketplace",
      "knowledge": "/app/knowledge", "knowledge base": "/app/knowledge",
      "setting": "/app/settings", "settings": "/app/settings",
    };

    if (navMatch) {
      const target = (navMatch[1] ?? "").trim().toLowerCase();
      for (const [key, path] of Object.entries(navTargets)) {
        if (target.includes(key)) {
          const response = `Taking you to ${target}...`;
          const aiMsg: Message = { role: "assistant", text: response, timestamp: Date.now() };
          setMessages((prev) => [...prev, aiMsg]);
          setThinking(false);
          speak(response);
          setTimeout(() => router.push(path), 500);
          return;
        }
      }
    }

    // Try the backend LLM API first
    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem("prachar_token") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

      // Build conversation history (last 10 messages)
      const conversationMessages = [
        ...messages.slice(-10).map((m) => ({ role: m.role, content: m.text })),
        { role: "user" as const, content: query },
      ];

      // Get current page context
      const context = typeof window !== "undefined" ? window.location.pathname : undefined;

      const res = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ messages: conversationMessages, context }),
        signal: AbortSignal.timeout(15000),
      });

      if (res.ok) {
        const data = await res.json() as { reply: string };
        const response = data.reply || FALLBACK;
        const aiMsg: Message = { role: "assistant", text: response, timestamp: Date.now() };
        setMessages((prev) => [...prev, aiMsg]);
        setThinking(false);
        speak(response);
        return;
      }
    } catch {
      // API failed — fall through to local KB
    }

    // Fallback: local knowledge base (works offline / no API key)
    setTimeout(() => {
      const entry = findAnswer(query);
      const response = entry?.response ?? FALLBACK;

      const aiMsg: Message = { role: "assistant", text: response, timestamp: Date.now() };
      setMessages((prev) => [...prev, aiMsg]);
      setThinking(false);
      speak(response);

      // Navigate if needed
      if (entry?.navigate) {
        setTimeout(() => router.push(entry.navigate!), 500);
      }
    }, 400 + Math.random() * 300);
  }, [router, speak, messages]);

  // ─── Voice recognition ───
  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;

    // Unlock speech synthesis on iOS Safari (this is a user gesture)
    unlockSpeechSynthesis();

    // Stop any speaking
    stopSpeaking();
    setSpeaking(false);

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      // Fallback: just focus the input
      inputRef.current?.focus();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    let finalTranscript = "";

    recognition.onstart = () => {
      setListening(true);
    };

    recognition.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interim += transcript;
        }
      }
      setInput(finalTranscript || interim);
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
      if (finalTranscript.trim()) {
        processQuery(finalTranscript.trim());
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
  }, [processQuery]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const stopSpeaking = useCallback(() => {
    synthRef.current?.cancel();
    setSpeaking(false);
  }, []);

  // ─── Wake word detection ("Hey CURV") ───
  // Runs a continuous background SpeechRecognition that listens for the wake word.
  // When "hey curv" is detected, it opens the assistant and starts active listening.
  const startWakeWordDetection = useCallback(() => {
    if (typeof window === "undefined") return;
    if (wakeEnabledRef.current) return; // already running

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    wakeEnabledRef.current = true;
    setWakeActive(true);

    const wakeRecognition = new SpeechRecognition();
    wakeRecognition.continuous = true;
    wakeRecognition.interimResults = true;
    wakeRecognition.lang = "en-US";

    let lastRestart = 0;

    wakeRecognition.onresult = (event: any) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript.toLowerCase();
      }

      // Check for wake word
      const wakeWords = ["hey curv", "hey curv ai", "hay curv", "a curv", "hey curv a i", "hey curve", "hey kurv"];
      const detected = wakeWords.some((w) => transcript.includes(w));

      if (detected && !activeListeningRef.current && !open) {
        // Wake word detected!
        setWakeDetected(true);
        activeListeningRef.current = true;

        // Stop wake listener temporarily
        try { wakeRecognition.stop(); } catch {}

        // Open the assistant
        setOpen(true);

        // Acknowledge with voice
        const greetings = [
          "Hi! I'm CURV AI. What do you need?",
          "Hey! What's up? Ask me anything.",
          "I'm listening. What do you want to know?",
          "Yes! I'm ready. What can I help you with?",
        ];
        const greeting = greetings[Math.floor(Math.random() * greetings.length)] ?? "Hi! I'm CURV AI. What do you need?";

        const aiMsg: Message = { role: "assistant", text: greeting, timestamp: Date.now() };
        setMessages((prev) => [...prev, aiMsg]);
        speak(greeting);

        // After greeting finishes, start active listening for the question
        setTimeout(() => {
          activeListeningRef.current = false;
          setWakeDetected(false);
          startListening();
        }, 2500);
      }
    };

    wakeRecognition.onerror = (event: any) => {
      // Auto-restart on errors (except not-allowed which means mic permission denied)
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        wakeEnabledRef.current = false;
        setWakeActive(false);
        return;
      }
      // Restart after a short delay
      setTimeout(() => {
        if (wakeEnabledRef.current) {
          try { wakeRecognition.start(); } catch {}
        }
      }, 500);
    };

    wakeRecognition.onend = () => {
      // Auto-restart if still enabled (continuous listening)
      const now = Date.now();
      if (wakeEnabledRef.current && now - lastRestart > 200) {
        lastRestart = now;
        setTimeout(() => {
          if (wakeEnabledRef.current) {
            try { wakeRecognition.start(); } catch {}
          }
        }, 200);
      }
    };

    try {
      wakeRecognition.start();
      wakeRecognitionRef.current = wakeRecognition;
    } catch {}
  }, [open, speak, startListening]);

  const stopWakeWordDetection = useCallback(() => {
    wakeEnabledRef.current = false;
    setWakeActive(false);
    try { wakeRecognitionRef.current?.stop(); } catch {}
    wakeRecognitionRef.current = null;
  }, []);

  // ─── Start wake word detection on mount ───
  useEffect(() => {
    // Delay slightly to avoid permission prompt on page load
    const timer = setTimeout(() => {
      startWakeWordDetection();
    }, 1500);
    return () => {
      clearTimeout(timer);
      stopWakeWordDetection();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Restart wake detection when panel closes ───
  useEffect(() => {
    if (!open && !listening && !speaking) {
      // Panel closed and not actively listening/speaking — resume wake detection
      const timer = setTimeout(() => {
        if (!wakeEnabledRef.current) {
          startWakeWordDetection();
        }
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [open, listening, speaking, startWakeWordDetection]);

  // ─── Cleanup ───
  useEffect(() => {
    return () => {
      synthRef.current?.cancel();
      recognitionRef.current?.stop();
      stopWakeWordDetection();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      {/* ─── Floating Orb ─── */}
      <AnimatePresence>
        {!open && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            onClick={() => setOpen(true)}
            className="fixed bottom-6 right-6 z-[90] group"
            aria-label="Open CURV AI Assistant"
          >
            {/* Glow rings */}
            <motion.div
              animate={{ scale: [1, 1.4], opacity: [0.4, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
              className="absolute inset-0 rounded-full bg-accent/30"
            />
            <motion.div
              animate={{ scale: [1, 1.7], opacity: [0.2, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: 0.3 }}
              className="absolute inset-0 rounded-full bg-accent/20"
            />

            {/* Orb */}
            <motion.div
              animate={{
                scale: orbPulse ? 1.05 : 1,
                boxShadow: orbPulse
                  ? "0 0 30px rgba(139,92,246,0.3), 0 0 60px rgba(139,92,246,0.1)"
                  : "0 0 20px rgba(139,92,246,0.15)",
              }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              className={cn(
                "relative w-14 h-14 rounded-full bg-gradient-to-br from-accent via-accent-dark to-accent-dark flex items-center justify-center shadow-3d-lg group-hover:scale-110 transition-transform",
                wakeDetected && "ring-4 ring-accent/40",
              )}
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                className="absolute inset-1 rounded-full border border-white/20"
              />
              <Brain className="w-6 h-6 text-bg relative z-10" />
            </motion.div>

            {/* Wake word indicator */}
            {wakeActive && !wakeDetected && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: [0.4, 0.8, 0.4] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-success border-2 border-bg"
              />
            )}

            {/* Wake detected flash */}
            {wakeDetected && (
              <motion.div
                initial={{ scale: 0, opacity: 1 }}
                animate={{ scale: [0, 2], opacity: [1, 0] }}
                transition={{ duration: 0.8 }}
                className="absolute inset-0 rounded-full bg-accent"
              />
            )}

            {/* Tooltip */}
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              whileHover={{ opacity: 1, x: 0 }}
              className="absolute right-full mr-3 top-1/2 -translate-y-1/2 glass-strong rounded-lg px-3 py-2 whitespace-nowrap pointer-events-none"
            >
              <span className="font-mono text-xs text-text">
                {wakeActive ? "Say \"Hey CURV\" or click" : "Ask CURV AI"}
              </span>
            </motion.div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* ─── Chat Panel ─── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="fixed bottom-6 right-6 z-[90] w-[calc(100vw-3rem)] max-w-[420px] h-[600px] max-h-[calc(100vh-3rem)] flex flex-col glass-strong rounded-2xl shadow-3d-xl overflow-hidden"
          >
            {/* ─── Header ─── */}
            <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <motion.div
                    animate={{
                      boxShadow: speaking
                        ? ["0 0 10px rgba(139,92,246,0.3)", "0 0 25px rgba(139,92,246,0.5)", "0 0 10px rgba(139,92,246,0.3)"]
                        : "0 0 10px rgba(139,92,246,0.15)",
                    }}
                    transition={{ duration: 0.5, repeat: speaking ? Infinity : 0 }}
                    className="w-10 h-10 rounded-full bg-gradient-to-br from-accent via-accent-dark to-accent-dark flex items-center justify-center"
                  >
                    <Brain className="w-5 h-5 text-bg" />
                  </motion.div>
                  {/* Status dot */}
                  <div className={cn(
                    "absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-bg-surface",
                    speaking ? "bg-info" : listening ? "bg-danger" : thinking ? "bg-warning" : "bg-success",
                  )} />
                </div>
                <div>
                  <div className="font-display text-sm font-semibold text-text">CURV AI</div>
                  <div className="font-mono text-[10px] text-text-muted">
                    {speaking ? "Speaking..." : listening ? "Listening..." : thinking ? "Thinking..." : wakeActive ? 'Say "Hey CURV"' : "Ready to help"}
                  </div>
                </div>
              </div>
              <button
                onClick={() => { stopSpeaking(); stopListening(); setOpen(false); }}
                className="text-text-muted hover:text-text transition-colors p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* ─── Voice Waveform / Status ─── */}
            {(listening || speaking) && (
              <div className="px-4 py-3 bg-white/[0.02] border-b border-white/[0.04] flex items-center justify-center gap-1">
                {Array.from({ length: 24 }).map((_, i) => (
                  <motion.div
                    key={i}
                    animate={{
                      height: listening
                        ? [4, Math.random() * 24 + 8, 4]
                        : [4, Math.random() * 16 + 4, 4],
                    }}
                    transition={{
                      duration: 0.4 + Math.random() * 0.3,
                      repeat: Infinity,
                      delay: i * 0.03,
                      ease: "easeInOut",
                    }}
                    className={cn(
                      "w-1 rounded-full",
                      listening ? "bg-danger" : "bg-info",
                    )}
                  />
                ))}
              </div>
            )}

            {/* ─── Messages ─── */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-none">
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={cn(
                    "flex gap-2.5",
                    msg.role === "user" ? "flex-row-reverse" : "flex-row",
                  )}
                >
                  {/* Avatar */}
                  <div className={cn(
                    "shrink-0 w-7 h-7 rounded-full flex items-center justify-center",
                    msg.role === "assistant"
                      ? "bg-gradient-to-br from-accent to-accent-dark"
                      : "bg-bg-elevated",
                  )}>
                    {msg.role === "assistant" ? (
                      <Brain className="w-3.5 h-3.5 text-bg" />
                    ) : (
                      <span className="font-mono text-[10px] text-text-secondary">You</span>
                    )}
                  </div>

                  {/* Bubble */}
                  <div className={cn(
                    "rounded-xl px-3.5 py-2.5 max-w-[80%]",
                    msg.role === "assistant"
                      ? "bg-white/[0.04] border border-white/[0.06]"
                      : "bg-accent/10 border border-accent/15",
                  )}>
                    <p className={cn(
                      "text-sm leading-relaxed",
                      msg.role === "assistant" ? "text-text-secondary" : "text-text",
                    )}>
                      {msg.text}
                    </p>
                  </div>
                </motion.div>
              ))}

              {/* Thinking indicator */}
              {thinking && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-2.5"
                >
                  <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center">
                    <Brain className="w-3.5 h-3.5 text-bg" />
                  </div>
                  <div className="rounded-xl px-4 py-3 bg-white/[0.04] border border-white/[0.06]">
                    <span className="ai-dots">
                      <span /> <span /> <span />
                    </span>
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* ─── Suggested questions (only when few messages) ─── */}
            {messages.length <= 2 && !thinking && (
              <div className="px-4 pb-2 flex flex-wrap gap-1.5">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => processQuery(q)}
                    className="px-2.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.06] text-[11px] text-text-secondary hover:text-text hover:bg-white/[0.06] transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* ─── Input bar ─── */}
            <div className="p-3 border-t border-white/[0.06]">
              <div className="flex items-center gap-2">
                {/* Mic button */}
                <button
                  onClick={listening ? stopListening : startListening}
                  className={cn(
                    "shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all",
                    listening
                      ? "bg-danger text-white shadow-glow-red"
                      : "bg-white/[0.04] text-text-secondary hover:text-text hover:bg-white/[0.08]",
                  )}
                  aria-label={listening ? "Stop listening" : "Start voice input"}
                >
                  <motion.div
                    animate={listening ? { scale: [1, 1.15, 1] } : {}}
                    transition={{ duration: 0.8, repeat: listening ? Infinity : 0 }}
                  >
                    <Mic className="w-4 h-4" />
                  </motion.div>
                </button>

                {/* Text input */}
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      stopSpeaking();
                      processQuery(input);
                    }
                  }}
                  placeholder={listening ? "Listening..." : "Ask anything about CURV AI..."}
                  className="flex-1 input-field py-2 text-sm"
                  disabled={listening}
                />

                {/* Speak/Stop button */}
                {speaking ? (
                  <button
                    onClick={stopSpeaking}
                    className="shrink-0 w-10 h-10 rounded-full bg-info/20 text-info flex items-center justify-center hover:bg-info/30 transition-all"
                    aria-label="Stop speaking"
                  >
                    <Volume2 className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      if (input.trim()) {
                        processQuery(input);
                      }
                    }}
                    className="shrink-0 w-10 h-10 rounded-full bg-accent/10 text-accent flex items-center justify-center hover:bg-accent/20 transition-all"
                    aria-label="Send"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Voice support note */}
              <div className="flex items-center justify-center gap-1.5 mt-2">
                <Sparkles className="w-3 h-3 text-accent/40" />
                <span className="font-mono text-[9px] text-text-muted">
                  Voice powered · Say "Hey CURV" to summon · Click mic to speak
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
