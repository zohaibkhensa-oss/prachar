"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { apiPost, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { Mail, Lock, User, ArrowRight, CheckCircle2 } from "lucide-react";

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
    <div className="min-h-screen flex items-center justify-center bg-bg grid-pattern relative overflow-hidden">
      <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-success/5 rounded-full blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-md"
      >
        <div className="flex justify-center mb-8">
          <Logo size="lg" />
        </div>

        <div className="glass-strong rounded-2xl p-8 shadow-3d-lg">
          <div className="mb-6">
            <h1 className="font-display text-2xl font-semibold text-text">Create your workspace</h1>
            <p className="text-sm text-text-secondary mt-1">Start your AI advertising journey</p>
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
                  <CheckCircle2 className="w-3.5 h-3.5 text-success" />
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

          <div className="mt-6 text-center">
            <span className="text-sm text-text-secondary">Have an account? </span>
            <Link href="/login" className="text-accent hover:underline text-sm font-medium">
              Sign in →
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
