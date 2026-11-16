"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Logo } from "@/components/Logo";
import { InteractiveCurv3DOrb } from "@/components/InteractiveCurv3DOrb";
import { VoiceAssistant } from "@/components/VoiceAssistant";
import {
  ArrowRight,
  Brain,
  Megaphone,
  Share2,
  BarChart3,
  Sparkles,
  Zap,
  CheckCircle2,
  Menu,
  X,
  Palette,
  MessageCircle,
  Video,
  ShieldCheck,
  TrendingUp,
  Layers,
  Send,
  Eye,
  Target,
  Sliders,
  Play,
  RotateCcw,
  Check,
} from "lucide-react";

const NAV_LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "AI Team", href: "#ai-team" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "Workflow", href: "#workflow" },
  { label: "Demo", href: "#demo" },
  { label: "Pricing", href: "#pricing" },
  { label: "About", href: "#about" },
];

const STATS = [
  {
    value: "16+",
    label: "Connected Channels",
    desc: "Google, Meta, YouTube, TikTok, LinkedIn, X, Pinterest & WhatsApp",
  },
  {
    value: "10",
    label: "Ad Networks",
    desc: "Autonomous campaign creation across Google Ads, Meta Ads & more",
  },
  {
    value: "14",
    label: "Global Locales",
    desc: "Multi-language regional routing, Hinglish, Arabic, Spanish & Asian packs",
  },
  {
    value: "24/7",
    label: "AI Active",
    desc: "Autonomous weekly loops, real-time inquiry response & spend watchdogs",
  },
];

const TEAM = [
  {
    id: "aria",
    name: "Aria",
    title: "Chief Marketing Strategist",
    color: "#8B5CF6",
    badge: "Strategy & Growth",
    avatarBg: "rgba(139, 92, 246, 0.15)",
    tagline: "Plans your marketing week and runs every campaign at peak hours.",
    bio: "Aria analyzes your brand, competitors, and trending audience queries across Google and social channels. She drafts your weekly content calendar, scaffolds Google and Meta ad campaigns, and autonomously reallocates spend toward your winning channels.",
    deliverables: [
      "Weekly Multi-Channel Content Calendar",
      "Google & Meta Campaign Scaffolding",
      "Softmax Budget Allocator with ±20% Guardrails",
      "Google Search Console Impression Spike Response",
    ],
    sampleAction: "Synthesized 7 peak-hour posts + 2 Meta ad variations for approval.",
  },
  {
    id: "nova",
    name: "Nova",
    title: "Creative Director & Studio Head",
    color: "#EC4899",
    badge: "Creative Studio & Video",
    avatarBg: "rgba(236, 72, 153, 0.15)",
    tagline: "Turns one raw product snap into finished carousels, reels, and video.",
    bio: "Nova is your 24/7 creative powerhouse. Powered by Wan 3.0 video generation and high-converting creative models, she transforms raw product photos into branded 1080×1080 carousels, video reels with typography, and high-CTR ad assets matching your brand guidelines.",
    deliverables: [
      "Wan 3.0 Canonical Video Generation",
      "Branded 5-Slide Instagram & LinkedIn Carousels",
      "High-CTR Creative Evolution & Winner Mutation",
      "Automated Product Watermarks & Aspect-Ratio Adaptation",
    ],
    sampleAction: "Rendered 5-slide product carousel + 1080p 5s reel with brand watermark.",
  },
  {
    id: "kian",
    name: "Kian",
    title: "Leads & Customer Closer",
    color: "#34D399",
    badge: "Lead Recovery & Sales",
    avatarBg: "rgba(52, 211, 153, 0.15)",
    tagline: "Never lets an inquiry on WhatsApp or Instagram go cold.",
    bio: "Kian monitors inbound inquiries across WhatsApp Business and Instagram DMs. He instantly crafts polite, high-converting response drafts in your brand tone and proactively alerts you with 1-tap follow-up nudges for unconfirmed leads before 24 hours elapse.",
    deliverables: [
      "Instant WhatsApp & Instagram Inquiry Drafts",
      "24-Hour Warm Lead Follow-Up Nudges",
      "Automated Order Confirmation & Catalog Sharing",
      "Attributed Conversions Tracking (Under 1-min response)",
    ],
    sampleAction: "Identified 4 unconfirmed inquiries · Drafted courteous 15% discount follow-up.",
  },
];

const CAPABILITIES = [
  {
    id: "strategy",
    title: "Marketing Intelligence & Strategy",
    subtitle: "A 9-Director Agency Council analyzing your brand every week.",
    icon: Brain,
    color: "#8B5CF6",
    tag: "Campaign Brain",
    description:
      "CURV AI doesn't just generate text — it runs an internal executive council. Our Strategy, Media, Budget, and Audience engines cross-reference competitor footprints and customer intent to architect complete campaigns before producing a single creative.",
    previewType: "strategy",
    metric: "9 Autonomous Engines",
    metricLabel: "Active analysis",
  },
  {
    id: "creative",
    title: "Creative Studio & Wan 3.0 Video",
    subtitle: "From one product photo to finished multi-format assets.",
    icon: Palette,
    color: "#EC4899",
    tag: "Studio",
    description:
      "Upload a single product image. Nova generates a complete creative package: high-fidelity 1080×1080 carousels, vertical video reels powered by Wan 3.0, and compelling ad variants with proven visual hierarchy.",
    previewType: "creative",
    metric: "Wan 3.0",
    metricLabel: "Default video model",
  },
  {
    id: "publishing",
    title: "Multi-Channel Social Distribution",
    subtitle: "One brand brief, published to every platform at peak hours.",
    icon: Share2,
    color: "#38BDF8",
    tag: "Distribution",
    description:
      "Schedule and publish directly across Instagram, Facebook, YouTube, TikTok, LinkedIn, and X. CURV automatically adapts captions, character limits, tags, and aspect ratios per network to maximize algorithm distribution.",
    previewType: "publishing",
    metric: "16+ Channels",
    metricLabel: "Direct API publishing",
  },
  {
    id: "ads",
    title: "Autonomous Ad Management",
    subtitle: "Targeted campaigns with strict spend caps and no guesswork.",
    icon: Megaphone,
    color: "#F59E0B",
    tag: "Paid Growth",
    description:
      "Scaffold Google RSA and Meta CBO campaigns in under 30 seconds. CURV AI monitors daily spend caps, enforces mandatory dry-run testing for the first seven days, and autonomously pauses underperforming ad sets.",
    previewType: "ads",
    metric: "10 Networks",
    metricLabel: "Spend-cap guarded",
  },
  {
    id: "leads",
    title: "Instant Lead Recovery (Kian)",
    subtitle: "Convert WhatsApp & Instagram DM inquiries into confirmed sales.",
    icon: MessageCircle,
    color: "#34D399",
    tag: "Leads & Sales",
    description:
      "Small businesses lose over 60% of potential orders due to slow follow-ups. Kian drafts personalized replies within 48 seconds and prepares morning action cards so you can confirm orders in one tap.",
    previewType: "leads",
    metric: "< 48s",
    metricLabel: "Average draft speed",
  },
  {
    id: "insights",
    title: "Closed-Loop Commercial Attribution",
    subtitle: "Real revenue, ROAS, and conversions — zero black boxes.",
    icon: BarChart3,
    color: "#A78BFA",
    tag: "Attribution",
    description:
      "Track every rupee or dollar generated. Our first-party attribution pixel and per-channel breakdown connect organic social reach, ad clicks, and WhatsApp orders to actual business revenue.",
    previewType: "insights",
    metric: "Position-Based",
    metricLabel: "40/20/40 Attribution",
  },
];

const WORKFLOW_STEPS = [
  {
    number: "01",
    title: "Brand Brief & Intake",
    actor: "You",
    desc: "Upload your logo, website URL, or drop a single product photo. No complex 15-field onboarding forms.",
    color: "#8B5CF6",
  },
  {
    number: "02",
    title: "Autonomous Strategy",
    actor: "Aria",
    desc: "Aria analyzes audience intent, competitor angles, and peak posting windows to plan your week.",
    color: "#8B5CF6",
  },
  {
    number: "03",
    title: "Creative Production",
    actor: "Nova",
    desc: "Nova renders branded carousel slides, reel copy, and Wan 3.0 video clips ready for distribution.",
    color: "#EC4899",
  },
  {
    number: "04",
    title: "Human 1-Tap Approval",
    actor: "You",
    desc: "Mandatory gatekeeper: Nothing is published without your tap. Review the prepared cards in under 30 seconds.",
    color: "#F59E0B",
    isCheckpoint: true,
  },
  {
    number: "05",
    title: "Multi-Platform Publishing",
    actor: "Platform",
    desc: "Approved assets dispatch at precise peak hours across Meta, YouTube, LinkedIn, TikTok, and X.",
    color: "#38BDF8",
  },
  {
    number: "06",
    title: "Lead Recovery & Follow-Up",
    actor: "Kian",
    desc: "Kian catches customer queries on WhatsApp and Instagram, drafting instant replies to close the deal.",
    color: "#34D399",
  },
  {
    number: "07",
    title: "Attribution & Growth Loop",
    actor: "Engine",
    desc: "Real revenue and ROAS feedback into Business Memory, teaching your AI team what converts best.",
    color: "#A78BFA",
  },
];

const TIERS = [
  {
    name: "Starter",
    price: "₹999",
    period: "/mo",
    desc: "Essential marketing automation for solo founders and local businesses.",
    features: [
      "1 brand workspace",
      "2 AI videos / month (Wan 3.0)",
      "10 AI creative images / month",
      "Weekly autonomous planning loop",
      "Social posting (IG, FB, YouTube)",
      "Aria strategic marketing assistant",
      "Standard email support",
    ],
    cta: "Start Creating",
    href: "/register",
    featured: false,
  },
  {
    name: "Growth",
    price: "₹2,999",
    period: "/mo",
    desc: "Complete autonomous marketing, video studio, and paid ad management.",
    features: [
      "1 brand workspace",
      "8 AI videos / month (Wan 3.0)",
      "40 AI creative images / month",
      "Google Ads + Meta Ads management",
      "Kian Lead Recovery (WhatsApp & DMs)",
      "Nova Creative Studio & carousels",
      "Closed-loop attribution & ROAS tracker",
      "Peak-hour autonomous scheduling",
      "Priority customer support",
    ],
    cta: "Start Creating",
    href: "/register",
    featured: true,
    badge: "Most Popular",
  },
  {
    name: "Agency",
    price: "₹9,999",
    period: "/mo",
    desc: "Multi-brand intelligence and white-label execution for growing agencies.",
    features: [
      "5 brand workspaces included",
      "50 AI videos / month",
      "500 AI creative images / month",
      "Full API access + tokens",
      "White-label client PDF reports",
      "Multi-brand executive council summary",
      "Custom domain & client portal",
      "Dedicated account strategist",
    ],
    cta: "Talk to Sales",
    href: "/register",
    featured: false,
  },
];

const EASE = [0.16, 1, 0.3, 1] as const;

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeCapability, setActiveCapability] = useState("strategy");
  const [activeTeamMember, setActiveTeamMember] = useState("aria");

  const currentCap = CAPABILITIES.find((c) => c.id === activeCapability) ?? CAPABILITIES[0]!;
  const currentMember = TEAM.find((t) => t.id === activeTeamMember) ?? TEAM[0]!;

  return (
    <div className="min-h-screen bg-bg text-text selection:bg-[#8B5CF6]/30 selection:text-white">
      <VoiceAssistant />

      {/* ─── 1. Header Navigation ─── */}
      <nav className="sticky top-0 z-50 border-b border-white/[0.06] bg-bg/75 backdrop-blur-xl">
        <div className="container flex items-center justify-between py-3.5">
          <Link href="/" aria-label="CURV AI home" className="flex items-center gap-2">
            <Logo size="sm" />
          </Link>

          <div className="hidden lg:flex items-center gap-7">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-xs uppercase tracking-wider font-mono text-text-secondary hover:text-text transition-colors"
              >
                {l.label}
              </a>
            ))}
          </div>

          <div className="hidden lg:flex items-center gap-3">
            <Link
              href="/login"
              className="text-xs font-mono uppercase tracking-wider text-text-secondary hover:text-text px-4 py-2 rounded-lg border border-white/[0.08] hover:border-white/[0.18] transition-all"
            >
              Log In
            </Link>
            <Link
              href="/register"
              className="btn-primary text-xs uppercase tracking-wider font-mono !py-2 !px-4 !min-h-[38px] shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_30px_rgba(139,92,246,0.4)]"
            >
              Sign Up <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>

          <button
            className="lg:hidden p-2 text-text-secondary hover:text-text"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {menuOpen && (
          <div className="lg:hidden border-t border-white/[0.06] px-6 py-5 space-y-2 bg-bg/95 backdrop-blur-2xl">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setMenuOpen(false)}
                className="block py-2.5 text-sm font-mono text-text-secondary hover:text-text transition-colors"
              >
                {l.label}
              </a>
            ))}
            <div className="flex gap-3 pt-4 border-t border-white/[0.06]">
              <Link href="/login" className="btn-secondary text-xs flex-1 justify-center py-2.5">
                Log In
              </Link>
              <Link href="/register" className="btn-primary text-xs flex-1 justify-center py-2.5">
                Sign Up
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* ─── 2. Hero Section with Interactive 3D Orb ─── */}
      <section className="relative overflow-hidden pt-12 pb-20 lg:pt-16 lg:pb-28">
        {/* Subtle Ambient Radial Lighting */}
        <div className="absolute top-[-20%] left-[-10%] w-[700px] h-[700px] rounded-full blur-[140px] bg-[#8B5CF6]/10 pointer-events-none" />
        <div className="absolute top-[20%] right-[-15%] w-[650px] h-[650px] rounded-full blur-[150px] bg-[#EC4899]/8 pointer-events-none" />

        <div className="container relative grid lg:grid-cols-2 gap-12 lg:gap-8 items-center">
          {/* Left Column: Storytelling & Conversion */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE }}
            className="text-left"
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#8B5CF6]/30 bg-[#8B5CF6]/10 mb-7 backdrop-blur-md">
              <span className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6] animate-pulse" />
              <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-medium">
                YOUR AI MARKETING TEAM
              </span>
            </div>

            <h1 className="font-display text-4xl sm:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.02] text-balance">
              Your entire marketing team.{" "}
              <span className="text-gradient">Powered by intelligence.</span>
            </h1>

            <p className="mt-6 max-w-xl text-base sm:text-lg text-text-secondary leading-relaxed">
              From strategy and creative production to social publishing and campaign
              growth, CURV AI brings your entire marketing workflow together in one
              intelligent platform.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link
                href="/register"
                className="btn-primary text-sm sm:text-base group !px-8 !min-h-[50px] shadow-[0_0_25px_rgba(139,92,246,0.3)] hover:shadow-[0_0_35px_rgba(139,92,246,0.5)]"
              >
                Start Creating
                <ArrowRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
              </Link>
              <a
                href="#capabilities"
                className="btn-secondary text-sm sm:text-base !px-7 !min-h-[50px]"
              >
                Explore the Platform
              </a>
            </div>

            <div className="mt-7 flex items-center gap-2 text-xs font-mono text-text-muted">
              <ShieldCheck className="w-4 h-4 text-[#34D399]" />
              <span>One platform. Your entire marketing workflow. Human approval guaranteed.</span>
            </div>
          </motion.div>

          {/* Right Column: Genuine 3D Interactive WebGL Orb */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.15, ease: EASE }}
            className="relative flex items-center justify-center"
          >
            <InteractiveCurv3DOrb />
          </motion.div>
        </div>
      </section>

      {/* ─── 3. Trust and Platform Scale Section ─── */}
      <section id="platform" className="border-y border-white/[0.06] bg-[#0E1118]/80 backdrop-blur-md">
        <div className="container py-12 lg:py-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 lg:gap-12">
            {STATS.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: EASE }}
                className="text-left"
              >
                <div className="font-display text-4xl lg:text-5xl font-bold tracking-tight text-gradient">
                  {stat.value}
                </div>
                <div className="font-mono text-xs uppercase tracking-wider text-text font-medium mt-1.5">
                  {stat.label}
                </div>
                <div className="text-xs text-text-secondary mt-1 leading-snug">
                  {stat.desc}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── 4. Meet the AI Team ─── */}
      <section id="ai-team" className="py-24 lg:py-32 relative overflow-hidden">
        <div className="absolute top-1/2 left-0 w-[500px] h-[500px] rounded-full blur-[140px] bg-[#8B5CF6]/6 pointer-events-none" />

        <div className="container relative">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-semibold mb-3">
              THE CURV SPECIALISTS
            </div>
            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              Three specialists.<br />One autonomous engine.
            </h2>
            <p className="mt-4 text-sm sm:text-base text-text-secondary">
              Aria, Nova, and Kian handle strategy, creative, and lead recovery 24/7.
              Every morning, your finished plan is ready for your 1-tap say.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8 max-w-6xl mx-auto">
            {TEAM.map((member, i) => {
              const isSelected = activeTeamMember === member.id;
              return (
                <motion.div
                  key={member.id}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: i * 0.12, ease: EASE }}
                  onClick={() => setActiveTeamMember(member.id)}
                  className={`card-3d rounded-2xl p-7 sm:p-8 flex flex-col justify-between relative cursor-pointer transition-all duration-300 ${
                    isSelected ? "border-white/[0.2] glow-ring bg-bg-surface" : "border-white/[0.06]"
                  }`}
                >
                  <div
                    className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
                    style={{ background: member.color }}
                  />

                  <div>
                    <div className="flex items-center justify-between mb-5">
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center font-display text-xl font-bold"
                        style={{
                          background: member.avatarBg,
                          color: member.color,
                          boxShadow: `0 0 25px ${member.color}35`,
                        }}
                      >
                        {member.name[0]}
                      </div>
                      <span
                        className="font-mono text-[11px] uppercase tracking-wider px-2.5 py-1 rounded-full border border-white/[0.08]"
                        style={{ color: member.color }}
                      >
                        {member.badge}
                      </span>
                    </div>

                    <h3 className="font-display text-2xl font-bold text-text">{member.name}</h3>
                    <p className="font-mono text-xs text-text-muted mt-0.5">{member.title}</p>

                    <p className="mt-4 text-xs sm:text-sm text-text-secondary leading-relaxed">
                      {member.bio}
                    </p>

                    <div className="mt-6 pt-5 border-t border-white/[0.06]">
                      <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2.5">
                        Core Responsibilities
                      </div>
                      <ul className="space-y-2">
                        {member.deliverables.map((item) => (
                          <li key={item} className="flex items-start gap-2 text-xs text-text-secondary">
                            <CheckCircle2
                              className="w-3.5 h-3.5 shrink-0 mt-0.5"
                              style={{ color: member.color }}
                            />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="mt-6 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                    <div className="font-mono text-[10px] text-text-muted uppercase tracking-wider mb-1">
                      Live Sample Output
                    </div>
                    <p className="text-xs text-text italic">"{member.sampleAction}"</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ─── 5. Product Capabilities (Visual Storytelling) ─── */}
      <section id="capabilities" className="py-24 bg-[#0E1118]/90 border-y border-white/[0.06]">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-semibold mb-3">
              IMPLEMENTED CAPABILITIES
            </div>
            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              Real capabilities.<br />Zero marketing fiction.
            </h2>
            <p className="mt-4 text-text-secondary text-sm sm:text-base">
              Every feature described here is fully wired into our adapters, models, and execution runtime.
            </p>
          </div>

          <div className="grid lg:grid-cols-12 gap-8 items-start max-w-6xl mx-auto">
            {/* Capability Nav Tabs (5 cols) */}
            <div className="lg:col-span-5 space-y-2">
              {CAPABILITIES.map((cap) => {
                const isActive = activeCapability === cap.id;
                const Icon = cap.icon;
                return (
                  <button
                    key={cap.id}
                    onClick={() => setActiveCapability(cap.id)}
                    className={`w-full text-left p-4 rounded-xl transition-all border flex items-center justify-between ${
                      isActive
                        ? "bg-bg-card border-white/[0.15] shadow-3d-md"
                        : "bg-transparent border-transparent hover:bg-white/[0.02] hover:border-white/[0.05]"
                    }`}
                  >
                    <div className="flex items-center gap-3.5">
                      <div
                        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                        style={{
                          background: `${cap.color}15`,
                          color: cap.color,
                        }}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-text">{cap.title}</div>
                        <div className="text-xs text-text-muted">{cap.tag}</div>
                      </div>
                    </div>
                    {isActive && (
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cap.color }} />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Interactive Capability Preview Card (7 cols) */}
            <div className="lg:col-span-7">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentCap.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.3 }}
                  className="card-3d rounded-2xl p-6 sm:p-8 border-white/[0.1] relative overflow-hidden"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ background: currentCap.color }}
                      />
                      <span className="font-mono text-xs uppercase tracking-wider text-text-muted">
                        {currentCap.tag}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="font-display text-lg font-bold" style={{ color: currentCap.color }}>
                        {currentCap.metric}
                      </div>
                      <div className="font-mono text-[10px] text-text-muted">
                        {currentCap.metricLabel}
                      </div>
                    </div>
                  </div>

                  <h3 className="font-display text-2xl font-bold text-text mb-2">
                    {currentCap.title}
                  </h3>
                  <p className="text-sm text-text-secondary leading-relaxed mb-6">
                    {currentCap.description}
                  </p>

                  {/* Mock Functional Product Interface */}
                  <div className="rounded-xl p-4 sm:p-5 bg-bg/90 border border-white/[0.06] font-mono text-xs">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/[0.06] text-text-muted text-[11px]">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-success/80" />
                        curvai.org/platform/{currentCap.id}
                      </span>
                      <span>Execution: ACTIVE</span>
                    </div>

                    {currentCap.id === "strategy" && (
                      <div className="space-y-2.5">
                        <div className="flex justify-between text-text">
                          <span className="text-text-muted">Campaign Intent:</span>
                          <span className="text-[#A78BFA]">High-Conversion Regional Scale</span>
                        </div>
                        <div className="flex justify-between text-text">
                          <span className="text-text-muted">Agency Council Verdict:</span>
                          <span className="text-[#34D399]">9/9 Directors Consensual</span>
                        </div>
                        <div className="flex justify-between text-text">
                          <span className="text-text-muted">Budget Philosophy:</span>
                          <span>Softmax Performance-First</span>
                        </div>
                        <div className="p-2.5 rounded bg-white/[0.02] border border-white/[0.04] text-[11px] text-text-secondary">
                          "Shifting 35% budget from awareness toward Instagram Reels and YouTube Shorts targeting striking Google Search queries."
                        </div>
                      </div>
                    )}

                    {currentCap.id === "creative" && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-3">
                          <div className="w-16 h-16 rounded-lg bg-[#EC4899]/15 border border-[#EC4899]/30 flex items-center justify-center shrink-0">
                            <Video className="w-6 h-6 text-[#EC4899]" />
                          </div>
                          <div>
                            <div className="text-text font-semibold">Wan 3.0 Canonical Render</div>
                            <div className="text-text-muted text-[11px]">1080×1920 · 5.0s · 60fps · Watermarked</div>
                            <div className="text-[#34D399] text-[11px] mt-0.5">✓ Ready for approval</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-text font-bold">5 Slides</div>
                            <div className="text-text-muted">Carousel</div>
                          </div>
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-text font-bold">9:16 + 1:1</div>
                            <div className="text-text-muted">Dual Aspect</div>
                          </div>
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-text font-bold">3 Copies</div>
                            <div className="text-text-muted">A/B Testing</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {currentCap.id === "publishing" && (
                      <div className="space-y-2">
                        {[
                          { ch: "Instagram", status: "Scheduled 10:15 AM (Peak Window)", ok: true },
                          { ch: "YouTube Shorts", status: "Scheduled 12:30 PM (Peak Window)", ok: true },
                          { ch: "Facebook Page", status: "Published 08:00 AM", ok: true },
                          { ch: "LinkedIn", status: "UgcPost Scaffolding Complete", ok: true },
                        ].map((row) => (
                          <div key={row.ch} className="flex items-center justify-between text-[11px]">
                            <span className="text-text">{row.ch}</span>
                            <span className="text-text-muted flex items-center gap-1">
                              <Check className="w-3 h-3 text-[#34D399]" />
                              {row.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {currentCap.id === "ads" && (
                      <div className="space-y-2.5">
                        <div className="flex justify-between text-[11px]">
                          <span className="text-text-muted">Daily Hard Cap:</span>
                          <span className="text-text">₹2,500 (Hard Cap Table Verified)</span>
                        </div>
                        <div className="flex justify-between text-[11px]">
                          <span className="text-text-muted">Dry-Run Status:</span>
                          <span className="text-[#34D399]">Completed (Day 9 of Live Bidding)</span>
                        </div>
                        <div className="flex justify-between text-[11px]">
                          <span className="text-text-muted">Underperforming Ad Watchdog:</span>
                          <span className="text-[#F59E0B]">1 Ad Set Auto-Paused (CPA &gt; ₹320)</span>
                        </div>
                      </div>
                    )}

                    {currentCap.id === "leads" && (
                      <div className="space-y-2.5">
                        <div className="p-2.5 rounded bg-[#34D399]/10 border border-[#34D399]/20 text-[#34D399] text-[11px]">
                          ✓ Inbound WhatsApp inquiry detected (Rahul: "Price for weekend booking?")
                        </div>
                        <div className="p-2.5 rounded bg-white/[0.02] border border-white/[0.04] text-[11px] text-text-secondary">
                          Kian Draft: "Hi Rahul! It's ₹1,499 with complimentary grooming. We have 3 slots left for Saturday — shall I reserve one for you?"
                        </div>
                        <div className="flex justify-end gap-2 text-[10px]">
                          <span className="px-2 py-1 rounded bg-white/[0.05] text-text-muted">Dismiss</span>
                          <span className="px-2.5 py-1 rounded bg-[#34D399] text-black font-semibold">1-Tap Send</span>
                        </div>
                      </div>
                    )}

                    {currentCap.id === "insights" && (
                      <div className="space-y-2.5">
                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-text font-bold text-sm">₹94,800</div>
                            <div className="text-text-muted text-[10px]">Attributed Rev</div>
                          </div>
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-[#34D399] font-bold text-sm">4.8x</div>
                            <div className="text-text-muted text-[10px]">ROAS</div>
                          </div>
                          <div className="p-2 rounded bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-[#A78BFA] font-bold text-sm">124</div>
                            <div className="text-text-muted text-[10px]">Leads Closed</div>
                          </div>
                        </div>
                        <div className="text-[11px] text-text-muted">
                          Touchpoints: GSC Organic (40%) → Meta Ad (20%) → WhatsApp Close (40%)
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="mt-6 flex justify-end">
                    <Link
                      href="/register"
                      className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-text hover:text-accent transition-colors"
                    >
                      Get Started with {currentCap.tag} →
                    </Link>
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </section>

      {/* ─── 6. Intelligent Workflow Animation Section ─── */}
      <section id="workflow" className="py-24 lg:py-32 relative overflow-hidden">
        <div className="container relative">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-semibold mb-3">
              THE AUTONOMOUS PIPELINE
            </div>
            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              How CURV AI executes.<br />Step by step.
            </h2>
            <p className="mt-4 text-sm sm:text-base text-text-secondary">
              A transparent, closed-loop workflow where human approval remains the ultimate authority.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 max-w-6xl mx-auto">
            {WORKFLOW_STEPS.map((step, i) => (
              <motion.div
                key={step.number}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}
                className={`card-3d rounded-xl p-5 relative flex flex-col justify-between ${
                  step.isCheckpoint
                    ? "border-[#F59E0B]/50 bg-[#F59E0B]/5 glow-ring"
                    : "border-white/[0.06]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className="font-mono text-sm font-bold"
                      style={{ color: step.color }}
                    >
                      {step.number}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-white/[0.04] text-text-muted">
                      {step.actor}
                    </span>
                  </div>
                  <h4 className="font-display text-base font-bold text-text mb-1.5">
                    {step.title}
                  </h4>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {step.desc}
                  </p>
                </div>

                {step.isCheckpoint && (
                  <div className="mt-4 pt-3 border-t border-[#F59E0B]/20 flex items-center gap-1.5 text-[11px] text-[#FBBF24] font-mono">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Mandatory user approval</span>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── 7. Product Demonstration / Interface Preview ─── */}
      <section id="demo" className="py-24 bg-[#0E1118]/80 border-y border-white/[0.06]">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-semibold mb-3">
              LIVE INTERFACE SHOWCASE
            </div>
            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              Consumer simple.<br />Agency intelligent.
            </h2>
            <p className="mt-4 text-sm sm:text-base text-text-secondary">
              No blank prompts. You open the app to finished action cards ready for 1-tap review.
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, ease: EASE }}
            className="card-3d rounded-2xl p-6 sm:p-8 max-w-5xl mx-auto border-white/[0.1] shadow-3d-xl"
          >
            {/* Window chrome */}
            <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-[#EF4444]/60" />
                <div className="w-3 h-3 rounded-full bg-[#F59E0B]/60" />
                <div className="w-3 h-3 rounded-full bg-[#10B981]/60" />
                <span className="font-mono text-xs text-text-muted ml-3">
                  curvai.org/app
                </span>
              </div>
              <div className="font-mono text-[11px] text-text-muted flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#34D399] animate-pulse" />
                <span>AI Growth Team · 24/7 Active</span>
              </div>
            </div>

            {/* Dashboard Demo Grid */}
            <div className="grid md:grid-cols-3 gap-4">
              {/* Card 1: Aria Ready to Post */}
              <div className="card-3d rounded-xl p-5 border-l-4 border-l-[#8B5CF6] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-[#A78BFA] font-bold">
                      Aria · Marketing
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#8B5CF6]/15 text-[#A78BFA]">
                      Ready
                    </span>
                  </div>
                  <h4 className="font-display text-sm font-semibold text-text">
                    Diwali Weekend Special Reel
                  </h4>
                  <p className="text-xs text-text-secondary mt-1">
                    Scheduled for Instagram & YouTube Shorts at 10:15 AM peak window.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="text-[11px] font-mono text-text-muted">1-Tap:</span>
                  <span className="px-3 py-1 rounded bg-[#8B5CF6] text-white text-xs font-medium cursor-pointer">
                    Approve & Schedule
                  </span>
                </div>
              </div>

              {/* Card 2: Kian Lead Recovery */}
              <div className="card-3d rounded-xl p-5 border-l-4 border-l-[#34D399] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-[#34D399] font-bold">
                      Kian · Leads
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#34D399]/15 text-[#34D399]">
                      4 Leads
                    </span>
                  </div>
                  <h4 className="font-display text-sm font-semibold text-text">
                    Follow up unconfirmed inquiries
                  </h4>
                  <p className="text-xs text-text-secondary mt-1">
                    4 inquiries from WhatsApp awaiting reply. 15% discount nudge drafted.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="text-[11px] font-mono text-text-muted">1-Tap:</span>
                  <span className="px-3 py-1 rounded bg-[#34D399] text-black text-xs font-semibold cursor-pointer">
                    Review & Send
                  </span>
                </div>
              </div>

              {/* Card 3: Nova Fill My Week */}
              <div className="card-3d rounded-xl p-5 border-l-4 border-l-[#EC4899] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-[#F472B6] font-bold">
                      Nova · Studio
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#EC4899]/15 text-[#F472B6]">
                      Autopilot
                    </span>
                  </div>
                  <h4 className="font-display text-sm font-semibold text-text">
                    Fill this week's content calendar
                  </h4>
                  <p className="text-xs text-text-secondary mt-1">
                    Generate 5 companion carousels using last week's top-performing product angles.
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="text-[11px] font-mono text-text-muted">1-Tap:</span>
                  <span className="px-3 py-1 rounded bg-[#EC4899] text-white text-xs font-medium cursor-pointer">
                    Fill My Week
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 8. Pricing Section ─── */}
      <section id="pricing" className="py-24 lg:py-32">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#C4B5FD] font-semibold mb-3">
              TRANSPARENT PRICING
            </div>
            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              Simple pricing.<br />Powerful platform.
            </h2>
            <p className="mt-4 text-sm sm:text-base text-text-secondary">
              No hidden agency retainers. Full autonomous execution at small-business pricing.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8 max-w-5xl mx-auto">
            {TIERS.map((tier, i) => (
              <motion.div
                key={tier.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: EASE }}
                className={tier.featured ? "md:-translate-y-4" : ""}
              >
                <div
                  className={`card-3d rounded-2xl p-7 sm:p-8 h-full flex flex-col justify-between relative ${
                    tier.featured
                      ? "border-[#8B5CF6]/50 glow-ring bg-bg-surface"
                      : "border-white/[0.06]"
                  }`}
                >
                  {tier.featured && (
                    <div className="badge badge-accent absolute -top-3.5 right-6 text-xs font-mono uppercase tracking-wider px-3 py-1">
                      {tier.badge}
                    </div>
                  )}

                  <div>
                    <h3 className="font-display text-2xl font-bold text-text">{tier.name}</h3>
                    <p className="text-xs text-text-secondary mt-1">{tier.desc}</p>

                    <div className="mt-5 flex items-baseline gap-1">
                      <span className="font-display text-4xl lg:text-5xl font-bold text-text">
                        {tier.price}
                      </span>
                      <span className="font-mono text-xs text-text-muted">{tier.period}</span>
                    </div>

                    <ul className="mt-7 space-y-3">
                      {tier.features.map((f) => (
                        <li key={f} className="flex items-start gap-2.5 text-xs text-text-secondary">
                          <CheckCircle2 className="w-4 h-4 text-[#34D399] shrink-0 mt-0.5" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <Link
                    href={tier.href}
                    className={`mt-8 w-full block text-center text-xs font-mono uppercase tracking-wider py-3 rounded-lg transition-all ${
                      tier.featured
                        ? "btn-primary shadow-[0_0_20px_rgba(139,92,246,0.3)]"
                        : "btn-secondary"
                    }`}
                  >
                    {tier.cta}
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── 9. Final Conversion Section ─── */}
      <section id="about" className="py-24 lg:py-32 border-t border-white/[0.06] relative overflow-hidden">
        <div className="absolute bottom-[-10%] left-1/2 -translate-x-1/2 w-[800px] h-[350px] rounded-full blur-[140px] bg-[#8B5CF6]/10 pointer-events-none" />

        <div className="container relative text-center">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: EASE }}
            className="max-w-3xl mx-auto"
          >
            <div className="flex justify-center mb-8">
              <div className="w-20 h-20 rounded-2xl bg-white/[0.02] border border-white/[0.08] flex items-center justify-center p-3 shadow-3d-lg">
                <img
                  src="/curv-logo.png"
                  alt="CURV AI"
                  width={64}
                  height={64}
                  className="object-contain"
                />
              </div>
            </div>

            <h2 className="font-display text-3xl sm:text-5xl font-semibold text-text leading-tight">
              Your next marketing team<br />is already here.
            </h2>

            <p className="mt-5 text-base sm:text-lg text-text-secondary max-w-xl mx-auto">
              Bring your strategy, creativity and marketing operations together with CURV AI.
            </p>

            <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/register"
                className="btn-primary text-sm sm:text-base group !px-8 !min-h-[50px] shadow-[0_0_25px_rgba(139,92,246,0.35)]"
              >
                Start Creating
                <ArrowRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/login"
                className="btn-secondary text-sm sm:text-base !px-7 !min-h-[50px]"
              >
                Explore Live Demo
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 10. Footer ─── */}
      <footer className="border-t border-white/[0.06] py-10 bg-bg">
        <div className="container flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="font-mono text-[11px] text-text-muted uppercase tracking-wider">
              Autonomous AI Growth Platform
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-6">
            <a href="#platform" className="text-xs text-text-muted hover:text-text transition-colors">
              Platform
            </a>
            <a href="#ai-team" className="text-xs text-text-muted hover:text-text transition-colors">
              AI Team
            </a>
            <a href="#pricing" className="text-xs text-text-muted hover:text-text transition-colors">
              Pricing
            </a>
            <Link href="/privacy" className="text-xs text-text-muted hover:text-text transition-colors">
              Privacy
            </Link>
            <Link href="/terms" className="text-xs text-text-muted hover:text-text transition-colors">
              Terms
            </Link>
            <Link href="/support" className="text-xs text-text-muted hover:text-text transition-colors">
              Support
            </Link>
            <Link href="/login" className="text-xs text-text-muted hover:text-text transition-colors">
              Login
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
