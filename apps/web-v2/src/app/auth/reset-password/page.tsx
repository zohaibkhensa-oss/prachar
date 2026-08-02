"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Lock, ArrowRight, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Logo } from "@/components/Logo";

function ResetPasswordContent() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"form" | "success" | "error">("form");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("No reset token provided. Click the link from your email.");
    }
  }, [token]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
      } else {
        setError(data.detail || "Reset failed. The link may be expired.");
      }
    } catch {
      setError("Could not connect to the server. Try again later.");
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
          {status === "form" && (
            <>
              <div className="mb-6">
                <h1 className="font-display text-2xl font-semibold text-text">Set new password</h1>
                <p className="text-sm text-text-secondary mt-1">Choose a new password for your account.</p>
              </div>

              <form onSubmit={onSubmit} className="space-y-4">
                <div>
                  <label className="label-field block mb-2">New password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
                      className="input-field pl-10"
                      placeholder="At least 8 characters"
                    />
                  </div>
                </div>
                <div>
                  <label className="label-field block mb-2">Confirm password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
                      className="input-field pl-10"
                      placeholder="Re-enter password"
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
                      Reset Password
                      <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>
            </>
          )}

          {status === "success" && (
            <div className="text-center py-4">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className="mb-4"
              >
                <CheckCircle2 className="w-16 h-16 text-success mx-auto" />
              </motion.div>
              <h1 className="font-display text-xl font-semibold text-text mb-2">Password reset!</h1>
              <p className="text-sm text-text-secondary mb-6">
                Your password has been changed. You can now log in with your new password.
              </p>
              <button onClick={() => router.push("/login")} className="btn-primary w-full">
                Continue to Login
              </button>
            </div>
          )}

          {status === "error" && (
            <div className="text-center py-4">
              <XCircle className="w-16 h-16 text-danger mx-auto mb-4" />
              <h1 className="font-display text-xl font-semibold text-text mb-2">Reset link invalid</h1>
              <p className="text-sm text-text-secondary mb-6">{error}</p>
              <Link href="/auth/forgot-password" className="btn-primary w-full block text-center">
                Request a new reset link
              </Link>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-accent" /></div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}
