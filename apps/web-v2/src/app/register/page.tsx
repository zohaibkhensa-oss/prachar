"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { apiPost, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { CurvOrb } from "@/components/CurvOrb";
import { SocialSignIn } from "@/components/SocialSignIn";
import { Mail, Lock, User, ArrowRight, CheckCircle2, Brain, Palette, MessageCircle } from "lucide-react";

const TEAM_TICKER = [
  { icon: Brain, name: "Aria", note: "plans & publishes your marketing", color: "#8B5CF6" },
  { icon: Palette, name: "Nova", note: "creates carousels, reels & ads", color: "#EC4899" },
  { icon: MessageCircle, name: "Kian", note: "answers leads before they go cold", color: "#34D399" },
];

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await apiPost<{ access_token: string }>("/auth/register", {
        name,
        email,
        password,
        tenant_name: name ? `${name}'s Workspace` : "My Workspace",
      });
      setToken(res.access_token);
      window.localStorage.setItem("prachar_email", email);
      router.push("/onboarding");
    } catch {
      setError("Registration failed. Email may already be in use.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-bg">
      {/* ─── Brand panel (desktop) ─── */}
      <div className="hidden lg:flex lg:w-[46%] relative flex-col justify-between p-12 overflow-hidden border-r border-white/[0.06]">
        <div className="absolute top-[-15%] right-[-15%] w-[500px] h-[500px] rounded-full blur-3xl bg-[#8B5CF6]/12" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[400px] h-[400px] rounded-full blur-3xl bg-[#FBBF24]/8" />

        <Link href="/" className="relative"><Logo size="md" /></Link>

        <div className="relative flex flex-col items-center text-center">
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
            className="drop-shadow-[0_0_50px_rgba(139,92,246,0.4)]"
          >
            <CurvOrb size={160} state="idle" />
          </motion.div>
          <h2 className="font-display text-3xl font-semibold text-text mt-10 leading-tight">
            Meet your new<br />marketing team.
          </h2>
          <p className="text-text-secondary text-sm mt-3 max-w-xs">
            Three AI specialists who plan, create, publish and follow up — every day.
          </p>

          <div className="mt-8 space-y-2 w-full max-w-xs">
            {TEAM_TICKER.map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 + i * 0.15 }}
                className="flex items-center gap-3 glass rounded-xl px-4 py-2.5"
              >
                <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${t.color}18` }}>
                  <t.icon className="w-3.5 h-3.5" style={{ color: t.color }} />
                </div>
                <div className="text-left">
                  <span className="text-xs font-medium text-text">{t.name} </span>
                  <span className="text-xs text-text-muted">{t.note}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        <p className="relative font-mono text-[11px] uppercase tracking-wider text-text-muted">
          Intelligent Marketing Platform
        </p>
      </div>

      {/* ─── Form panel ─── */}
      <div className="flex-1 flex items-center justify-center relative overflow-hidden px-5 py-12">
        <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-[#EC4899]/5 rounded-full blur-3xl lg:hidden" />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-md"
        >
          <div className="flex justify-center mb-8 lg:hidden">
            <Link href="/"><Logo size="lg" /></Link>
          </div>

          <div className="glass-strong rounded-2xl p-6 sm:p-8 shadow-3d-lg">
            <div className="mb-6">
              <h1 className="font-display text-2xl font-semibold text-text">Create your workspace</h1>
              <p className="text-sm text-text-secondary mt-1">Your AI marketing team starts today</p>
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="label-field block mb-2">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="input-field pl-10"
                    placeholder="Jane Doe"
                  />
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    className="input-field pl-10"
                    placeholder="you@brand.co"
                  />
                </div>
              </div>
              <div>
                <label className="label-field block mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    className="input-field pl-10"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="text-xs text-danger bg-danger/5 border border-danger/10 rounded-lg p-3"
                >
                  {error}
                </motion.div>
              )}

              {/* Feature list */}
              <div className="space-y-2 py-2">
                {["Free 14-day trial", "16+ channels included", "AI creative generation", "No credit card required"].map((f) => (
                  <div key={f} className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#34D399]" />
                    <span className="text-xs text-text-secondary">{f}</span>
                  </div>
                ))}
              </div>

              <button type="submit" disabled={loading} className="btn-primary w-full group">
                {loading ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-4 h-4 rounded-full border-2 border-bg/20 border-t-bg"
                  />
                ) : (
                  <>
                    Create Account
                    <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6">
              <SocialSignIn mode="register" placement="below" onError={setError} />
            </div>

            <div className="mt-6 text-center">
              <span className="text-sm text-text-secondary">Have an account? </span>
              <Link href="/login" className="text-accent hover:underline text-sm font-medium inline-block py-1 min-h-[36px]">
                Sign in →
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
