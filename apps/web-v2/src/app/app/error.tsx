"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[curv] app error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <div className="text-center max-w-md">
        <AlertTriangle className="w-10 h-10 text-danger mx-auto mb-4" />
        <h1 className="font-display text-xl text-text mb-2">Something went wrong</h1>
        <p className="text-sm text-text-secondary mb-2">
          This page hit an unexpected error.
        </p>
        <p className="text-xs font-mono text-text-muted mb-6 break-words">
          {error.message}
          {error.digest ? ` (${error.digest})` : ""}
        </p>
        <button
          onClick={reset}
          className="px-5 py-2.5 rounded-xl bg-bg-hover border border-line/10 text-sm text-text hover:bg-bg-card transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
