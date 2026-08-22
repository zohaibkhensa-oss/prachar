"use client";

import { cn } from "@/lib/utils";

/**
 * CurvMark — the CURV AI logo mark.
 *
 * Uses the actual approved CURV AI logo PNG asset directly.
 * Not a recreation or approximation.
 *
 * Variants:
 * - "mark"    — just the logo symbol (for compact spaces, favicons, avatars)
 * - "full"    — logo + "CURV AI" wordmark with gradient text
 * - "minimal" — logo + "CURV AI" wordmark in plain text
 */

interface CurvMarkProps {
  size?: number;
  variant?: "mark" | "full" | "minimal";
  className?: string;
  animated?: boolean;
}

export function CurvMark({
  size = 40,
  variant = "mark",
  className,
  animated = false,
}: CurvMarkProps) {
  const showText = variant === "full" || variant === "minimal";
  const showGradientText = variant === "full";

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      style={{ height: size }}
    >
      <img
        src="/curv-logo.png"
        width={size}
        height={size}
        alt="CURV AI logo"
        className={cn(
          "object-contain select-none",
          animated && "curv-breathe"
        )}
        style={{ width: size, height: size }}
        draggable={false}
      />

      {showText && (
        <span
          className={cn(
            "font-display font-bold tracking-tight whitespace-nowrap",
            showGradientText && "text-gradient-accent"
          )}
          style={{ fontSize: size * 0.38 }}
        >
          {showGradientText ? (
            <span
              style={{
                background: "linear-gradient(135deg, #8B5CF6, #EC4899, #F97316)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              CURV AI
            </span>
          ) : (
            "CURV AI"
          )}
        </span>
      )}
    </div>
  );
}
