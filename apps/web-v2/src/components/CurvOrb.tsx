"use client";

import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  type OrbState,
  ORB_STATE_LABELS,
  shouldShowWaves,
  getOrbAnimationDuration,
  isOrbActive,
} from "@/lib/orb-states";

interface CurvOrbProps {
  state?: OrbState;
  size?: number;
  showWaves?: boolean;
  showLabel?: boolean;
  className?: string;
  onClick?: () => void;
}

/**
 * CurvOrb — the CURV AI assistant identity.
 *
 * Uses the actual approved CURV AI logo PNG asset directly.
 * The logo itself IS the orb — no extra circular container.
 * Animations are applied to the container (breathing, rotation, scale),
 * not to individual dots.
 *
 * Animation states:
 * - idle: subtle breathing/glow
 * - thinking/planning/reasoning: gentle rotation
 * - generating: scale pulsing
 * - completed: pulse confirmation → return to idle
 * - error: shake
 * - waiting_approval: amber pulse ring
 *
 * Respects prefers-reduced-motion via CSS.
 */
export function CurvOrb({
  state = "idle",
  size = 110,
  showWaves = false,
  showLabel = false,
  className,
  onClick,
}: CurvOrbProps) {
  const active = isOrbActive(state);
  const waves = showWaves && shouldShowWaves(state);
  const duration = getOrbAnimationDuration(state);

  const isApproval = state === "waiting_approval";
  const isError = state === "error";
  const isCompleted = state === "completed";
  const isCancelled = state === "cancelled";
  const isThinking =
    state === "planning" || state === "reasoning" || state === "understanding";
  const isGenerating = state === "generating" || state === "executing";

  // State-specific glow colors (subtle ambient glow behind the logo)
  const glowColor = isError
    ? "rgba(239, 68, 68, 0.3)"
    : isApproval
    ? "rgba(250, 204, 21, 0.3)"
    : isCompleted
    ? "rgba(34, 197, 94, 0.25)"
    : isCancelled
    ? "rgba(120, 120, 140, 0.15)"
    : "rgba(139, 92, 246, 0.2)";

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div
        className="relative"
        style={{ width: size, height: size }}
        onClick={onClick}
        role={onClick ? "button" : undefined}
        aria-label={`CURV AI — ${ORB_STATE_LABELS[state]}`}
      >
        {/* Ripple waves — when active and producing output */}
        <AnimatePresence>
          {waves && (
            <>
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="absolute inset-0 rounded-full border pointer-events-none"
                  style={{
                    borderColor: isApproval
                      ? "rgba(250, 204, 21, 0.4)"
                      : "rgba(139, 92, 246, 0.2)",
                  }}
                  initial={{ scale: 1, opacity: 0.5 }}
                  animate={{ scale: 1.8, opacity: 0 }}
                  transition={{
                    duration: 2.5,
                    repeat: Infinity,
                    delay: i * 0.6,
                    ease: "easeOut",
                  }}
                />
              ))}
            </>
          )}
        </AnimatePresence>

        {/* Approval ring — pulsing amber */}
        <AnimatePresence>
          {isApproval && (
            <motion.div
              className="absolute rounded-full border-2 border-amber-400 pointer-events-none"
              style={{ inset: -4 }}
              initial={{ opacity: 0.8, scale: 1 }}
              animate={{ opacity: [0.8, 0.3, 0.8], scale: [1, 1.08, 1] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
            />
          )}
        </AnimatePresence>

        {/* Subtle ambient glow behind the logo — does not change logo silhouette */}
        <motion.div
          className="absolute pointer-events-none"
          style={{ inset: -size * 0.08 }}
          animate={{
            scale: active ? [1, 1.1, 1] : [1, 1.03, 1],
            opacity: active ? [0.4, 0.2, 0.4] : [0.25, 0.12, 0.25],
          }}
          transition={{
            duration,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div
            className="w-full h-full"
            style={{
              background: `radial-gradient(circle, ${glowColor} 0%, transparent 65%)`,
            }}
          />
        </motion.div>

        {/* The actual CURV logo — the PNG asset IS the orb */}
        <motion.div
          className={cn(
            "relative w-full h-full flex items-center justify-center",
            onClick && "cursor-pointer"
          )}
          animate={
            isError
              ? { x: [0, -4, 4, -4, 0] }
              : isThinking
              ? { rotate: 360 }
              : isGenerating
              ? { scale: [1, 1.05, 1] }
              : state === "completed"
              ? { scale: [1, 1.1, 1] }
              : state === "listening"
              ? { scale: [1, 1.06, 1] }
              : state === "speaking"
              ? { scale: [1, 1.04, 0.98, 1.03, 1] }
              : { scale: [1, 1.03, 1] }
          }
          transition={{
            duration: isThinking ? 6 : duration,
            repeat: Infinity,
            ease: isThinking ? "linear" : "easeInOut",
          }}
        >
          <img
            src="/curv-logo.png"
            alt="CURV AI"
            width={size}
            height={size}
            className="object-contain select-none"
            style={{
              width: size,
              height: size,
              filter: isError ? "hue-rotate(0deg) saturate(2) brightness(0.8)" : undefined,
            }}
            draggable={false}
          />
        </motion.div>
      </div>

      {/* Label */}
      {showLabel && (
        <div className="mt-4 text-center">
          <span className="text-xs text-text-secondary">
            <span
              className="font-semibold"
              style={{
                background: "linear-gradient(135deg, #8B5CF6, #EC4899, #F97316)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              {ORB_STATE_LABELS[state]}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
