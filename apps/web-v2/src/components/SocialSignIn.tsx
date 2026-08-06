"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiPost, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";

/* ─── Google Icon ─── */
function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09a7.68 7.68 0 0 1 0-4.18V7.07H2.18a11.91 11.91 0 0 0 0 10.86l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  );
}

/* ─── Apple Icon ─── */
function AppleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <path d="M17.05 12.04c-.03-2.66 2.17-3.94 2.27-4-1.24-1.82-3.17-2.07-3.85-2.09-1.64-.17-3.2.97-4.03.97-.84 0-2.12-.95-3.49-.92-1.8.03-3.45 1.04-4.37 2.66-1.86 3.23-.48 8.01 1.33 10.63.88 1.28 1.93 2.72 3.3 2.67 1.33-.05 1.83-.86 3.43-.86 1.6 0 2.06.86 3.46.83 1.43-.03 2.34-1.31 3.21-2.6 1.01-1.49 1.43-2.94 1.45-3.02-.03-.01-2.78-1.07-2.81-4.25zM14.6 4.59c.73-.89 1.22-2.12 1.09-3.34-1.05.04-2.33.7-3.09 1.58-.68.78-1.27 2.03-1.11 3.23 1.17.09 2.37-.6 3.11-1.47z" />
    </svg>
  );
}

interface SocialSignInProps {
  mode: "login" | "register";
  onError?: (msg: string) => void;
}

export function SocialSignIn({ mode, onError }: SocialSignInProps) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);

  // Load Google client ID from public env (exposed via next.config)
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const appleClientId = process.env.NEXT_PUBLIC_APPLE_CLIENT_ID || "";
  const appleRedirectUri = process.env.NEXT_PUBLIC_APPLE_REDIRECT_URI || "";

  useEffect(() => {
    // Configure Apple Sign-In JS once loaded
    const initApple = () => {
      if (typeof window === "undefined" || !window.AppleID) return;
      if (!appleClientId) return;
      window.AppleID.auth.init({
        clientId: appleClientId,
        scope: "name email",
        redirectURI: appleRedirectUri || window.location.origin + "/auth/apple/callback",
        usePopup: true,
      });
    };
    // Try immediately, then retry after a delay (script may still be loading)
    initApple();
    const timer = setTimeout(initApple, 2000);
    return () => clearTimeout(timer);
  }, [appleClientId, appleRedirectUri]);

  const handleGoogleSuccess = async (response: { credential: string }) => {
    setLoading("google");
    try {
      const data = await apiPost<{ access_token: string; refresh_token: string; user: { id: string; email: string } }>("/auth/social", {
        provider: "google",
        token: response.credential,
      });
      setToken(data.access_token);
      window.localStorage.setItem("prachar_refresh_token", data.refresh_token);
      window.localStorage.setItem("prachar_email", data.user.email);
      localStorage.setItem("prachar_onboarded", "true");
      router.push("/app");
      router.refresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Google sign-in failed. Please try again.";
      onError?.(msg);
    } finally {
      setLoading(null);
    }
  };

  const handleGoogleClick = () => {
    if (typeof window === "undefined" || !window.google) {
      onError?.("Google sign-in is not available. Please refresh the page.");
      return;
    }
    if (!googleClientId) {
      onError?.("Google sign-in is not configured.");
      return;
    }
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: handleGoogleSuccess,
    });
    window.google.accounts.id.prompt();
  };

  const handleAppleClick = async () => {
    if (typeof window === "undefined" || !window.AppleID) {
      onError?.("Apple sign-in is not available. Please refresh the page.");
      return;
    }
    if (!appleClientId) {
      onError?.("Apple sign-in is not configured.");
      return;
    }
    setLoading("apple");
    try {
      const response = await window.AppleID.auth.signIn();
      const id_token = response.id_token || response.authorization?.id_token;
      const user = response.user;
      if (!id_token) {
        onError?.("Apple sign-in failed: no identity token received.");
        return;
      }
      const fullName = user?.name
        ? `${user.name.firstName || ""} ${user.name.lastName || ""}`.trim()
        : undefined;
      const data = await apiPost<{ access_token: string; refresh_token: string; user: { id: string; email: string } }>("/auth/social", {
        provider: "apple",
        token: id_token,
        full_name: fullName,
      });
      setToken(data.access_token);
      window.localStorage.setItem("prachar_refresh_token", data.refresh_token);
      window.localStorage.setItem("prachar_email", data.user.email);
      localStorage.setItem("prachar_onboarded", "true");
      router.push("/app");
      router.refresh();
    } catch (err) {
      if (err instanceof Error && err.message.includes("popup")) {
        // User cancelled — don't show error
      } else {
        const msg = err instanceof ApiError ? err.message : "Apple sign-in failed. Please try again.";
        onError?.(msg);
      }
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-3">
      {/* Google */}
      <button
        type="button"
        onClick={handleGoogleClick}
        disabled={loading !== null}
        className="w-full flex items-center justify-center gap-3 px-4 py-3 min-h-[48px] rounded-xl bg-white text-gray-900 font-medium text-sm hover:bg-gray-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading === "google" ? (
          <span className="w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
        ) : (
          <GoogleIcon />
        )}
        Continue with Google
      </button>

      {/* Apple */}
      <button
        type="button"
        onClick={handleAppleClick}
        disabled={loading !== null}
        className="w-full flex items-center justify-center gap-3 px-4 py-3 min-h-[48px] rounded-xl bg-black text-white border border-white/20 font-medium text-sm hover:bg-gray-900 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading === "apple" ? (
          <span className="w-5 h-5 border-2 border-gray-600 border-t-white rounded-full animate-spin" />
        ) : (
          <AppleIcon />
        )}
        Continue with Apple
      </button>

      {/* Divider */}
      <div className="relative py-1">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-white/[0.06]" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-bg-surface px-3 text-text-muted uppercase tracking-wider">or {mode} with email</span>
        </div>
      </div>
    </div>
  );
}
