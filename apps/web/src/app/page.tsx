"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Logo } from "@/components/Logo";
import { PerformanceRing } from "@/components/ui/charts";
import { VoiceAssistant } from "@/components/VoiceAssistant";
import {
  ArrowRight,
  Brain,
  Megaphone,
  Share2,
  BarChart3,
  Sparkles,
  Zap,
  Globe,
  CheckCircle2,
  TrendingUp,
  Eye,
  Target,
} from "lucide-react";

const FEATURES = [
  { icon: Brain, title: "AI Engine", desc: "Autonomous weekly loops that measure, diagnose, generate, and publish across every platform." },
  { icon: Share2, title: "16+ Channels", desc: "Google, YouTube, Meta, TikTok, LinkedIn, X, Pinterest, WhatsApp, Telegram, and more." },
  { icon: Sparkles, title: "Creative AI", desc: "Generate ad copy, headlines, and visuals. A/B test variants with automatic evolution." },
  { icon: BarChart3, title: "Analytics", desc: "Real-time visibility scores, ROAS, CPA, attribution. Pixel-verified + network-reported." },
  { icon: Megaphone, title: "Campaign Studio", desc: "Kanban, timeline, calendar. Build campaigns with AI-assisted audience targeting." },
  { icon: Zap, title: "Budget Optimizer", desc: "Softmax reallocation with ±20% safety clamps. Spend caps. Idempotency keys." },
];

const STATS = [
  { value: "16+", label: "Channels" },
  { value: "10", label: "Ad Networks" },
  { value: "14", label: "Locales" },
  { value: "24/7", label: "AI Active" },
];

const TIERS = [
  { name: "Starter", price: "₹499", period: "/mo", features: ["1 brand", "3 channels", "Weekly loop", "Visibility Score"], cta: "Start free" },
  { name: "Growth", price: "₹2,999", period: "/mo", features: ["5 brands", "All channels", "Paid + organic", "Audit + reports"], cta: "Start free", featured: true },
  { name: "Agency", price: "₹9,999", period: "/mo", features: ["Unlimited brands", "Multi-tenant", "API access", "White-label"], cta: "Contact us" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <VoiceAssistant />
      {/* ─── Nav ─── */}
      <nav className="sticky top-0 z-50 glass-strong border-b border-white/[0.04]">
        <div className="container flex items-center justify-between py-3">
          <Link href="/"><Logo size="sm" /></Link>
          <div className="flex items-center gap-6">
            <Link href="/audit" className="text-sm text-text-secondary hover:text-text transition-colors">Free Audit</Link>
            <Link href="/login" className="text-sm text-text-secondary hover:text-text transition-colors">Login</Link>
            <Link href="/register" className="btn-primary text-sm">Get Started <ArrowRight className="w-3.5 h-3.5" /></Link>
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section className="relative overflow-hidden grid-pattern">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-info/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-accent/5 rounded-full blur-3xl" />

        <div className="container relative py-24 lg:py-32 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 mb-8">
              <Sparkles className="w-3.5 h-3.5 text-accent" />
              <span className="font-mono text-xs text-accent">AI Advertising Operating System</span>
            </div>

            <h1 className="font-display text-5xl sm:text-7xl lg:text-8xl font-semibold tracking-tight leading-[0.95] text-balance">
              <span className="text-gradient">One brand upload.</span>
              <br />
              <span className="text-text">Every platform.</span>
              <br />
              <span className="text-gradient-accent">Worldwide.</span>
            </h1>

            <p className="mx-auto mt-8 max-w-2xl text-lg text-text-secondary leading-relaxed">
              Prachar runs an autonomous weekly loop — organic SEO, social, and paid
              across every major platform — at SMB pricing. Powered by AI.
            </p>

            <div className="mt-10 flex items-center justify-center gap-4">
              <Link href="/audit" className="btn-primary text-base group">
                Get Free Audit
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link href="/register" className="btn-secondary text-base">
                See Pricing
              </Link>
            </div>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto"
          >
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="font-display text-4xl font-semibold text-gradient-accent">{stat.value}</div>
                <div className="font-mono text-xs uppercase tracking-wider text-text-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── Dashboard Preview ─── */}
      <section className="border-y border-white/[0.04] bg-bg-surface py-24">
        <div className="container">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="relative max-w-5xl mx-auto"
          >
            <div className="card-3d rounded-2xl p-6 shadow-3d-xl">
              <div className="flex items-center gap-2 mb-4">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-danger/40" />
                  <div className="w-3 h-3 rounded-full bg-warning/40" />
                  <div className="w-3 h-3 rounded-full bg-success/40" />
                </div>
                <span className="font-mono text-xs text-text-muted ml-2">prachar.app/dashboard</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card-3d rounded-xl p-4 flex flex-col items-center">
                  <span className="label-field mb-3">Visibility Score</span>
                  <PerformanceRing value={87} size={100} strokeWidth={8} sublabel="out of 100" />
                </div>
                <div className="card-3d rounded-xl p-4">
                  <span className="label-field mb-3">AI Status</span>
                  <div className="flex items-center gap-2 mb-2">
                    <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity }}>
                      <div className="w-2 h-2 rounded-full bg-success" />
                    </motion.div>
                    <span className="font-mono text-xs text-success">AI Engine Online</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs"><span className="text-text-secondary">Generating</span><span className="text-accent font-mono">3 jobs</span></div>
                    <div className="flex justify-between text-xs"><span className="text-text-secondary">Analyzing</span><span className="text-info font-mono">2 jobs</span></div>
                    <div className="flex justify-between text-xs"><span className="text-text-secondary">Tokens used</span><span className="text-text font-mono">2,847</span></div>
                  </div>
                </div>
                <div className="card-3d rounded-xl p-4">
                  <span className="label-field mb-3">This Week</span>
                  <div className="space-y-3">
                    {[
                      { icon: Target, label: "Conversions", value: "127", trend: "+23%" },
                      { icon: Eye, label: "Impressions", value: "284K", trend: "+8%" },
                      { icon: TrendingUp, label: "ROAS", value: "3.2x", trend: "+12%" },
                    ].map((m) => (
                      <div key={m.label} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <m.icon className="w-3.5 h-3.5 text-text-muted" />
                          <span className="text-xs text-text-secondary">{m.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-text">{m.value}</span>
                          <span className="font-mono text-xs text-success">{m.trend}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section className="py-24">
        <div className="container">
          <div className="text-center mb-16">
            <h2 className="font-display text-4xl font-semibold text-text">Everything you need.<br />Nothing you don't.</h2>
            <p className="mt-4 text-text-secondary max-w-xl mx-auto">A complete AI advertising platform built for the modern world.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="card-3d rounded-xl p-6 h-full group">
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center mb-4 group-hover:glow-ring transition-all">
                    <feature.icon className="w-5 h-5 text-accent" />
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
      <section className="py-24 bg-bg-surface border-y border-white/[0.04]">
        <div className="container">
          <div className="text-center mb-16">
            <h2 className="font-display text-4xl font-semibold text-text">Simple pricing.<br />Powerful platform.</h2>
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
                <div className={`card-3d rounded-2xl p-6 h-full ${tier.featured ? "border-accent/30 glow-ring" : ""}`}>
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
                        <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
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

      {/* ─── CTA ─── */}
      <section className="py-24">
        <div className="container text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="card-3d rounded-3xl p-12 max-w-2xl mx-auto glow-ring"
          >
            <Globe className="w-12 h-12 text-accent mx-auto mb-6" />
            <h2 className="font-display text-3xl font-semibold text-text">Ready to go global?</h2>
            <p className="mt-4 text-text-secondary">Upload your brand. Let AI handle the rest.</p>
            <Link href="/register" className="btn-primary text-base mt-8 group">
              Start Free Trial
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/[0.04] py-8">
        <div className="container flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="font-mono text-xs text-text-muted">AI-DRIVEN GLOBAL AD AGENCY</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/audit" className="text-xs text-text-muted hover:text-text transition-colors">Free Audit</Link>
            <Link href="/login" className="text-xs text-text-muted hover:text-text transition-colors">Login</Link>
            <Link href="/register" className="text-xs text-text-muted hover:text-text transition-colors">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
