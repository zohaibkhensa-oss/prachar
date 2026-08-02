"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Loader2, Mail } from "lucide-react";
import { Logo } from "@/components/Logo";

function VerifyEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided. Check your email for the correct link.");
      return;
    }
    void verify();
  }, [token]);

  async function verify() {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/auth/verify-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
        setMessage(data.message || "Email verified successfully!");
      } else {
        setStatus("error");
        setMessage(data.detail || "Verification failed. The link may be expired.");
      }
    } catch {
      setStatus("error");
      setMessage("Could not connect to the server. Try again later.");
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

        <div className="glass-strong rounded-2xl p-8 shadow-3d-lg text-center">
          {status === "loading" && (
            <>
              <Loader2 className="w-12 h-12 text-accent animate-spin mx-auto mb-4" />
              <h1 className="font-display text-xl font-semibold text-text mb-2">Verifying your email…</h1>
              <p className="text-sm text-text-secondary">Please wait a moment.</p>
            </>
          )}

          {status === "success" && (
            <>
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
              >
                <CheckCircle2 className="w-16 h-16 text-success mx-auto mb-4" />
              </motion.div>
              <h1 className="font-display text-2xl font-semibold text-text mb-2">Email verified!</h1>
              <p className="text-sm text-text-secondary mb-6">{message}</p>
              <button onClick={() => router.push("/login")} className="btn-primary w-full">
                Continue to Login
              </button>
            </>
          )}

          {status === "error" && (
            <>
              <XCircle className="w-16 h-16 text-danger mx-auto mb-4" />
              <h1 className="font-display text-2xl font-semibold text-text mb-2">Verification failed</h1>
              <p className="text-sm text-text-secondary mb-6">{message}</p>
              <div className="space-y-2">
                <Link href="/login" className="btn-secondary w-full block text-center">
                  Back to Login
                </Link>
                <p className="text-xs text-text-muted">
                  Need a new link? <Link href="/auth/resend-verification" className="text-accent hover:underline">Resend verification email</Link>
                </p>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-accent" /></div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
