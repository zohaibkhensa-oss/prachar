"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Mail, ArrowRight, CheckCircle2 } from "lucide-react";
import { Logo } from "@/components/Logo";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
      const res = await fetch(`${apiBase}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      // Always show "sent" message — even on error, to prevent email enumeration
      setSent(true);
    } catch {
      setSent(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg grid-pattern relative overflow-hidden">
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-md"
      >
        <div className="flex justify-center mb-8">
          <Logo size="lg" />
        </div>

        <div className="glass-strong rounded-2xl p-8 shadow-3d-lg">
          {!sent ? (
            <>
              <div className="mb-6">
                <h1 className="font-display text-2xl font-semibold text-text">Forgot password?</h1>
                <p className="text-sm text-text-secondary mt-1">
                  Enter your email and we'll send you a link to reset your password.
                </p>
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

                {error && (
                  <div className="text-xs text-danger bg-danger/5 border border-danger/10 rounded-lg p-3">
                    {error}
                  </div>
                )}

                <button type="submit" disabled={loading} className="btn-primary w-full group">
                  {loading ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="w-4 h-4 rounded-full border-2 border-bg/20 border-t-bg mx-auto"
                    />
                  ) : (
                    <>
                      Send Reset Link
                      <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>
            </>
          ) : (
            <div className="text-center py-4">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className="mb-4"
              >
                <CheckCircle2 className="w-16 h-16 text-success mx-auto" />
              </motion.div>
              <h1 className="font-display text-xl font-semibold text-text mb-2">Check your email</h1>
              <p className="text-sm text-text-secondary mb-6">
                If an account exists for <span className="text-text font-medium">{email}</span>,
                you'll receive a password reset link within a few minutes.
              </p>
              <p className="text-xs text-text-muted mb-4">
                Don't see it? Check your spam folder, or{" "}
                <button onClick={() => setSent(false)} className="text-accent hover:underline">
                  try a different email
                </button>
                .
              </p>
            </div>
          )}

          <div className="mt-6 text-center">
            <Link href="/login" className="text-sm text-text-secondary hover:text-accent">
              ← Back to login
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
