"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Logo } from "@/components/Logo";
import { CurvOrb } from "@/components/CurvOrb";
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
} from "lucide-react";

const NAV_LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "AI Team", href: "#ai-team" },
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
  { label: "About", href: "#about" },
];

const TEAM = [
  {
    name: "Aria",
    role: "Marketing & Growth",
    color: "#8B5CF6",
    desc: "Plans your week, writes your posts and campaigns, schedules across every channel at peak times, and reallocates budget where it performs.",
    points: ["Weekly content plan", "Campaign strategy", "Multi-channel scheduling"],
  },
  {
    name: "Nova",
    role: "Creative Studio",
    color: "#EC4899",
    desc: "Turns a product photo into finished creatives — carousels, reels, thumbnails and ad assets — on-brand, every time.",
    points: ["Carousels & reels", "Ad creatives", "Brand-consistent output"],
  },
  {
    name: "Kian",
    role: "Leads & Customers",
    color: "#34D399",
    desc: "Watches WhatsApp and Instagram inquiries, drafts replies in your voice, and follows up with unconfirmed leads before they go cold.",
    points: ["Instant draft replies", "Lead follow-ups", "Sales recovery"],
  },
];

const FEATURES = [
  { icon: Brain, title: "Your marketing team", desc: "We plan, write, and run your marketing — automatically, every week." },
  { icon: Share2, title: "Every platform", desc: "Google, Instagram, YouTube, Facebook, TikTok, LinkedIn, and more — all from one place." },
  { icon: Sparkles, title: "Ads & posts written for you", desc: "We craft your headlines, ad copy, and social posts. You approve everything." },
  { icon: BarChart3, title: "See what's working", desc: "Know exactly how many people you're reaching and how they're responding." },
  { icon: Megaphone, title: "Campaigns in 30 seconds", desc: "Tell us your goal and budget. We build the entire campaign for you." },
  { icon: Zap, title: "Smart spending", desc: "We put your budget where it works best — no wasted spend, no guesswork." },
];

const STATS = [
  { value: "16+", label: "Channels" },
  { value: "10", label: "Ad Networks" },
  { value: "14", label: "Locales" },
  { value: "24/7", label: "AI Active" },
];

const TIERS = [
  { name: "Starter", price: "₹999", period: "/mo", features: ["1 brand", "2 videos/mo", "10 images/mo", "Weekly loop"], cta: "Start free" },
  { name: "Growth", price: "₹2,999", period: "/mo", features: ["1 brand", "8 videos/mo", "40 images/mo", "Google + Meta Ads"], cta: "Start free", featured: true },
  { name: "Agency", price: "₹9,999", period: "/mo", features: ["5 brands", "50 videos/mo", "500 images/mo", "API + White-label"], cta: "Contact us" },
];

// Deterministic pseudo-random positions (stable across SSR/hydration).
const PARTICLES = Array.from({ length: 24 }, (_, i) => {
  const seed = (i * 2654435761) % 1000 / 1000;
  const seed2 = (i * 40503 + 67) % 997 / 997;
  return {
    left: `${8 + seed * 84}%`,
    top: `${6 + seed2 * 88}%`,
    size: 2 + ((i * 7) % 4),
    delay: (i % 8) * 0.9,
    duration: 6 + (i % 5) * 2,
  };
});

const EASE = [0.16, 1, 0.3, 1] as const;

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-bg text-text">
      <VoiceAssistant />

      {/* ─── Nav ─── */}
      <nav className="sticky top-0 z-50 border-b border-white/[0.06] bg-bg/70 backdrop-blur-xl">
        <div className="container flex items-center justify-between py-3">
          <Link href="/" aria-label="CURV AI home"><Logo size="sm" /></Link>

          <div className="hidden lg:flex items-center gap-8">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-sm text-text-secondary hover:text-text transition-colors"
              >
                {l.label}
              </a>
            ))}
          </div>

          <div className="hidden lg:flex items-center gap-3">
            <Link href="/login" className="btn-secondary text-sm !min-h-[38px]">Log In</Link>
            <Link href="/register" className="btn-primary text-sm !min-h-[38px]">
              Sign Up <ArrowRight className="w-3.5 h-3.5" />
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
          <div className="lg:hidden border-t border-white/[0.06] px-6 py-4 space-y-1 bg-bg/95 backdrop-blur-xl">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setMenuOpen(false)}
                className="block py-2.5 text-sm text-text-secondary hover:text-text transition-colors"
              >
                {l.label}
              </a>
            ))}
            <div className="flex gap-3 pt-3">
              <Link href="/login" className="btn-secondary text-sm flex-1 justify-center">Log In</Link>
              <Link href="/register" className="btn-primary text-sm flex-1 justify-center">Sign Up</Link>
            </div>
          </div>
        )}
      </nav>

      {/* ─── Hero ─── */}
      <section className="relative overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full blur-3xl bg-[#8B5CF6]/10" />
        <div className="absolute bottom-[-20%] right-[-5%] w-[500px] h-[500px] rounded-full blur-3xl bg-[#EC4899]/8" />

        <div className="container relative grid lg:grid-cols-2 gap-12 lg:gap-8 items-center py-20 lg:py-28">
          {/* Left */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: EASE }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#8B5CF6]/25 bg-[#8B5CF6]/10 mb-7">
              <span className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6]" />
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#A78BFA]">Your AI Marketing Team</span>
            </div>

            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.02] text-balance">
              Your entire marketing team.{" "}
              <span className="text-gradient">Powered by intelligence.</span>
            </h1>

            <p className="mt-6 max-w-lg text-lg text-text-secondary leading-relaxed">
              From strategy and creative production to social publishing and campaign
              growth, CURV AI brings your marketing workflow together in one
              intelligent platform.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link href="/register" className="btn-primary text-base group !px-7 !min-h-[48px]">
                Get Started Free
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link href="/login" className="btn-secondary text-base !px-7 !min-h-[48px]">Log In</Link>
            </div>

            <p className="mt-6 text-sm text-text-muted">One platform. Your entire marketing workflow.</p>
          </motion.div>

          {/* Right — Orb visual */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.9, delay: 0.15, ease: EASE }}
            className="relative flex items-center justify-center min-h-[380px] lg:min-h-[520px]"
            aria-hidden="true"
          >
            {/* Ambient rings */}
            <div className="absolute w-[78%] aspect-square rounded-full bg-[#8B5CF6]/12 blur-3xl" />
            <div className="absolute w-[52%] aspect-square rounded-full bg-[#EC4899]/14 blur-2xl" />
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
              className="absolute w-[88%] aspect-square rounded-full border border-white/[0.05]"
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 45, repeat: Infinity, ease: "linear" }}
              className="absolute w-[110%] aspect-square rounded-full border border-dashed border-[#8B5CF6]/15"
            />

            {/* Floating particles */}
            {PARTICLES.map((p, i) => (
              <motion.span
                key={i}
                className="absolute rounded-full"
                style={{
                  left: p.left,
                  top: p.top,
                  width: p.size,
                  height: p.size,
                  background: i % 3 === 0 ? "#EC4899" : i % 3 === 1 ? "#8B5CF6" : "#FBBF24",
                  boxShadow: "0 0 8px currentColor",
                }}
                animate={{ y: [0, -18, 0], opacity: [0.15, 0.7, 0.15] }}
                transition={{ duration: p.duration, repeat: Infinity, delay: p.delay, ease: "easeInOut" }}
              />
            ))}

            {/* The orb */}
            <motion.div
              animate={{ y: [0, -12, 0] }}
              transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
              className="relative drop-shadow-[0_0_60px_rgba(139,92,246,0.45)]"
            >
              <CurvOrb size={240} state="idle" />
            </motion.div>

            {/* Floating mini-cards */}
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.6 }}
              className="absolute top-[8%] right-[2%] glass-strong rounded-xl px-4 py-3 hidden sm:block"
            >
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-[#8B5CF6]/20 flex items-center justify-center">
                  <Brain className="w-3.5 h-3.5 text-[#A78BFA]" />
                </div>
                <div>
                  <div className="text-xs font-medium text-text">Aria</div>
                  <div className="font-mono text-[10px] text-text-muted">Post scheduled · 10:00 AM</div>
                </div>
              </div>
            </motion.div>
            <motion.div
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1.2 }}
              className="absolute bottom-[10%] left-[0%] glass-strong rounded-xl px-4 py-3 hidden sm:block"
            >
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-[#34D399]/20 flex items-center justify-center">
                  <MessageCircle className="w-3.5 h-3.5 text-[#34D399]" />
                </div>
                <div>
                  <div className="text-xs font-medium text-text">Kian</div>
                  <div className="font-mono text-[10px] text-text-muted">4 leads followed up</div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ─── Platform strip ─── */}
      <section id="platform" className="border-y border-white/[0.06] bg-bg-surface">
        <div className="container py-14">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto">
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="font-display text-3xl md:text-4xl font-semibold text-gradient-accent">{stat.value}</div>
                <div className="font-mono text-[11px] uppercase tracking-wider text-text-muted mt-1.5">{stat.label}</div>
              </div>
            ))}
          </div>
          <p className="text-center text-sm text-text-muted mt-10 max-w-xl mx-auto">
            One brand upload becomes organic + paid visibility across Google, Meta,
            YouTube, TikTok, LinkedIn and regional networks — on a weekly autonomous loop.
          </p>
        </div>
      </section>

      {/* ─── AI Team ─── */}
      <section id="ai-team" className="py-24 lg:py-32 relative overflow-hidden">
        <div className="absolute top-1/3 right-0 w-[400px] h-[400px] rounded-full blur-3xl bg-[#8B5CF6]/6" />
        <div className="container relative">
          <div className="text-center mb-16 max-w-2xl mx-auto">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#A78BFA] mb-4">Meet the team</div>
            <h2 className="font-display text-4xl lg:text-5xl font-semibold text-text leading-tight">
              Three specialists.<br />One intelligent platform.
            </h2>
            <p className="mt-5 text-text-secondary">
              Every morning, your AI team prepares the work — you approve it in one tap.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {TEAM.map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: EASE }}
                className="card-3d rounded-2xl p-7 relative overflow-hidden group"
              >
                <div
                  className="absolute top-0 left-0 right-0 h-px"
                  style={{ background: `linear-gradient(90deg, transparent, ${t.color}60, transparent)` }}
                />
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center font-display text-lg font-bold mb-5"
                  style={{ background: `${t.color}18`, color: t.color, boxShadow: `0 0 24px ${t.color}30` }}
                >
                  {t.name[0]}
                </div>
                <h3 className="font-display text-xl font-semibold text-text">{t.name}</h3>
                <div className="font-mono text-[11px] uppercase tracking-wider mt-1" style={{ color: t.color }}>{t.role}</div>
                <p className="mt-4 text-sm text-text-secondary leading-relaxed">{t.desc}</p>
                <ul className="mt-5 space-y-2">
                  {t.points.map((p) => (
                    <li key={p} className="flex items-center gap-2 text-xs text-text-secondary">
                      <span className="w-1 h-1 rounded-full" style={{ background: t.color }} />
                      {p}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="py-24 bg-bg-surface border-y border-white/[0.06]">
        <div className="container">
          <div className="text-center mb-16">
            <h2 className="font-display text-4xl lg:text-5xl font-semibold text-text leading-tight">
              Everything you need.<br />Nothing you don't.
            </h2>
            <p className="mt-4 text-text-secondary max-w-xl mx-auto">A complete AI marketing platform built for the modern world.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.07, ease: EASE }}
              >
                <div className="card-3d rounded-xl p-6 h-full group">
                  <div className="w-10 h-10 rounded-lg bg-[#8B5CF6]/12 flex items-center justify-center mb-4 group-hover:glow-ring transition-all">
                    <feature.icon className="w-5 h-5 text-[#A78BFA]" />
                  </div>
                  <h3 className="font-display text-lg font-medium text-text mb-2">{feature.title}</h3>
                  <p className="text-sm text-text-secondary leading-relaxed">{feature.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Pricing ─── */}
      <section id="pricing" className="py-24 lg:py-32">
        <div className="container">
          <div className="text-center mb-16">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#A78BFA] mb-4">Pricing</div>
            <h2 className="font-display text-4xl lg:text-5xl font-semibold text-text leading-tight">
              Simple pricing.<br />Powerful platform.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {TIERS.map((tier, i) => (
              <motion.div
                key={tier.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className={tier.featured ? "md:-translate-y-4" : ""}
              >
                <div className={`card-3d rounded-2xl p-6 h-full ${tier.featured ? "border-[#8B5CF6]/40 glow-ring" : ""}`}>
                  {tier.featured && (
                    <div className="badge badge-accent mb-4">Most Popular</div>
                  )}
                  <h3 className="font-display text-xl font-medium text-text">{tier.name}</h3>
                  <div className="mt-3 flex items-end gap-1">
                    <span className="font-display text-4xl font-semibold text-text">{tier.price}</span>
                    <span className="font-mono text-xs text-text-muted pb-1">{tier.period}</span>
                  </div>
                  <ul className="mt-6 space-y-3">
                    {tier.features.map((f) => (
                      <li key={f} className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#34D399] shrink-0" />
                        <span className="text-sm text-text-secondary">{f}</span>
                      </li>
                    ))}
                  </ul>
                  <Link
                    href="/register"
                    className={`mt-6 w-full ${tier.featured ? "btn-primary" : "btn-secondary"} block text-center`}
                  >
                    {tier.cta}
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── About / Final CTA ─── */}
      <section id="about" className="py-24 border-t border-white/[0.06] relative overflow-hidden">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[700px] h-[300px] rounded-full blur-3xl bg-[#8B5CF6]/8" />
        <div className="container relative text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: EASE }}
            className="max-w-2xl mx-auto"
          >
            <div className="flex justify-center mb-8">
              <CurvOrb size={88} state="idle" />
            </div>
            <h2 className="font-display text-3xl lg:text-4xl font-semibold text-text leading-tight">
              Built for founders who'd rather<br />run the business than the marketing.
            </h2>
            <p className="mt-5 text-text-secondary">
              CURV AI is an intelligent marketing platform that plans, creates,
              publishes and grows — while you stay in control of every decision.
            </p>
            <Link href="/register" className="btn-primary text-base mt-9 group !px-8 !min-h-[48px]">
              Get Started Free
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/[0.06] py-8">
        <div className="container flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="font-mono text-[11px] text-text-muted uppercase tracking-wider">Intelligent Marketing Platform</span>
          </div>
          <div className="flex items-center gap-5">
            <Link href="/privacy" className="text-xs text-text-muted hover:text-text transition-colors">Privacy</Link>
            <Link href="/terms" className="text-xs text-text-muted hover:text-text transition-colors">Terms</Link>
            <Link href="/support" className="text-xs text-text-muted hover:text-text transition-colors">Support</Link>
            <Link href="/login" className="text-xs text-text-muted hover:text-text transition-colors">Login</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
