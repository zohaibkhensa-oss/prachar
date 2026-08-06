"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { apiPost, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { Mail, Lock, ArrowRight, Sparkles } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await apiPost<{ access_token: string; refresh_token?: string }>("/auth/login", { email, password });
      setToken(res.access_token);
      window.localStorage.setItem("prachar_email", email);
      if (res.refresh_token) {
        window.localStorage.setItem("prachar_refresh_token", res.refresh_token);
      }
      // Save password for silent re-login on token expiry (dev/demo only)
      window.localStorage.setItem("prachar_password", password);
      router.push("/app");
    } catch {
      setError("Invalid credentials. Try demo@prachar.app / prachar123");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg grid-pattern relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-info/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-md"
      >
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <Logo size="lg" />
        </div>

        {/* Card */}
        <div className="glass-strong rounded-2xl p-6 sm:p-8 shadow-3d-lg">
          <div className="mb-6">
            <h1 className="font-display text-2xl font-semibold text-text">Welcome back</h1>
            <p className="text-sm text-text-secondary mt-1">Sign in to your AI advertising OS</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
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
                  autoComplete="current-password"
                  className="input-field pl-10"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <div className="text-right">
              <Link href="/auth/forgot-password" className="text-xs text-text-secondary hover:text-accent transition-colors inline-block py-1.5 min-h-[36px]">
                Forgot password?
              </Link>
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

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full group"
            >
              {loading ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="w-4 h-4 rounded-full border-2 border-bg/20 border-t-bg"
                />
              ) : (
                <>
                  Sign In
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-6 p-3 rounded-lg bg-accent/5 border border-accent/10">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-3 h-3 text-accent" />
              <span className="font-mono text-[10px] uppercase tracking-wider text-accent">Demo Access</span>
            </div>
            <p className="font-mono text-xs text-text-secondary">
              demo@prachar.app · prachar123
            </p>
          </div>

          <div className="mt-6 text-center">
            <span className="text-sm text-text-secondary">No account? </span>
            <Link href="/register" className="text-accent hover:underline text-sm font-medium inline-block py-1 min-h-[36px]">
              Create one →
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
