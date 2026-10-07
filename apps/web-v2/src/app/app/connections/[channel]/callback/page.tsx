"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import { apiGet } from "@/lib/api";

function CallbackInner() {
  const params = useParams<{ channel: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const channel = params.channel;

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const oauthError = searchParams.get("error") || searchParams.get("error_description");

    if (oauthError) {
      setError(String(oauthError));
      return;
    }
    if (!code || !state) {
      setError("Missing OAuth response parameters");
      return;
    }

    apiGet(`/connections/${channel}/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`)
      .then(() => {
        router.replace(`/app/connections?connected=${encodeURIComponent(channel)}`);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Connection failed");
      });
  }, [channel, searchParams, router]);

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <div className="text-center max-w-md">
        {error ? (
          <>
            <XCircle className="w-12 h-12 text-error mx-auto mb-4" />
            <h1 className="font-display text-xl text-text mb-2">
              {channel} connection failed
            </h1>
            <p className="text-sm text-text-secondary mb-6">{error}</p>
            <button
              onClick={() => router.replace("/app/connections")}
              className="px-5 py-2.5 rounded-lg bg-white/[0.05] border border-white/[0.08] text-sm text-text hover:bg-white/[0.08] transition-colors"
            >
              Back to connections
            </button>
          </>
        ) : (
          <>
            <Loader2 className="w-10 h-10 text-accent animate-spin mx-auto mb-4" />
            <h1 className="font-display text-xl text-text mb-2">
              Connecting {channel}…
            </h1>
            <p className="text-sm text-text-secondary">
              Finishing secure authorisation with {channel}. You will be redirected shortly.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default function ConnectionCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-64px)] items-center justify-center">
          <Loader2 className="w-10 h-10 text-accent animate-spin" />
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}
