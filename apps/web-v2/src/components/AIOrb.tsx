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

interface AIOrbProps {
  state?: OrbState;
  size?: number;
  showWaves?: boolean;
  showLabel?: boolean;
  className?: string;
  onClick?: () => void;
}

/**
 * AIOrb — the floating PRACHAR AI sphere.
 * 13 states from Architecture Freeze v2.0.
 * Neon-lime theme. State is driven by runtime events.
 */
export function AIOrb({
  state = "idle",
  size = 110,
  showWaves = false,
  showLabel = false,
  className,
  onClick,
}: AIOrbProps) {
  const active = isOrbActive(state);
  const waves = showWaves && shouldShowWaves(state);
  const duration = getOrbAnimationDuration(state);

  // State-specific colors
  const isApproval = state === "waiting_approval";
  const isError = state === "error";
  const isCancelled = state === "cancelled";
  const isCompleted = state === "completed";

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div
        className="relative"
        style={{ width: size, height: size }}
        onClick={onClick}
        role={onClick ? "button" : undefined}
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
                      : "rgba(190, 242, 100, 0.3)",
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

        {/* Approval ring — pulsing amber when waiting for approval */}
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

        {/* Outer halo */}
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{ inset: -size * 0.15 }}
          animate={{
            scale: active ? [1, 1.15, 1] : [1, 1.05, 1],
            opacity: active ? [0.6, 0.3, 0.6] : [0.4, 0.2, 0.4],
          }}
          transition={{
            duration,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div
            className="w-full h-full rounded-full"
            style={{
              background: isError
                ? "radial-gradient(circle, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.06) 40%, transparent 70%)"
                : isApproval
                ? "radial-gradient(circle, rgba(250,204,21,0.15) 0%, rgba(250,204,21,0.06) 40%, transparent 70%)"
                : isCompleted
                ? "radial-gradient(circle, rgba(34,197,94,0.12) 0%, rgba(34,197,94,0.04) 40%, transparent 70%)"
                : "radial-gradient(circle, rgba(190,242,100,0.12) 0%, rgba(132,204,22,0.06) 40%, transparent 70%)",
            }}
          />
        </motion.div>

        {/* Core sphere */}
        <motion.div
          className="relative w-full h-full rounded-full flex items-center justify-center cursor-pointer"
          animate={
            state === "idle"
              ? { scale: [1, 1.04, 1] }
              : state === "listening"
              ? { scale: [1, 1.08, 1] }
              : state === "speaking"
              ? { scale: [1, 1.06, 0.98, 1.05, 1] }
              : state === "generating"
              ? { scale: [1, 1.05, 1], rotate: [0, 8, -8, 0] }
              : state === "planning" || state === "understanding"
              ? { rotate: 360 }
              : state === "reasoning"
              ? { rotate: 360 }
              : state === "executing"
              ? { scale: [1, 1.06, 1] }
              : state === "waiting_approval"
              ? { scale: [1, 1.03, 1] }
              : state === "completed"
              ? { scale: [1, 1.1, 1] }
              : state === "error"
              ? { x: [0, -4, 4, -4, 0] }
              : { scale: [1, 1.04, 1] }
          }
          transition={{
            duration: state === "planning" || state === "reasoning" || state === "understanding"
              ? 4
              : duration,
            repeat: Infinity,
            ease: state === "planning" || state === "reasoning" || state === "understanding"
              ? "linear"
              : "easeInOut",
          }}
          style={{
            background: isError
              ? "radial-gradient(circle at 38% 32%, rgba(255,200,200,0.95) 0%, rgba(239,68,68,0.85) 25%, rgba(220,50,50,0.6) 55%, rgba(150,30,30,0.3) 80%, rgba(60,15,15,0.1) 100%)"
              : isApproval
              ? "radial-gradient(circle at 38% 32%, rgba(255,250,200,0.95) 0%, rgba(250,204,21,0.9) 25%, rgba(245,180,20,0.7) 55%, rgba(200,150,15,0.4) 80%, rgba(80,60,10,0.15) 100%)"
              : isCompleted
              ? "radial-gradient(circle at 38% 32%, rgba(220,255,220,0.95) 0%, rgba(34,197,94,0.85) 25%, rgba(22,160,80,0.6) 55%, rgba(15,120,60,0.3) 80%, rgba(5,40,20,0.1) 100%)"
              : isCancelled
              ? "radial-gradient(circle at 38% 32%, rgba(200,200,210,0.9) 0%, rgba(120,120,140,0.7) 25%, rgba(80,80,100,0.5) 55%, rgba(40,40,60,0.25) 80%, rgba(15,15,25,0.08) 100%)"
              : state === "speaking"
              ? "radial-gradient(circle at 38% 32%, rgba(240,255,220,1) 0%, rgba(190,242,100,0.95) 25%, rgba(132,204,22,0.75) 55%, rgba(100,160,30,0.45) 80%, rgba(50,80,20,0.2) 100%)"
              : state === "listening"
              ? "radial-gradient(circle at 38% 32%, rgba(230,255,200,0.95) 0%, rgba(190,242,100,0.9) 25%, rgba(132,204,22,0.7) 55%, rgba(100,160,30,0.4) 80%, rgba(40,80,15,0.15) 100%)"
              : state === "generating"
              ? "radial-gradient(circle at 38% 32%, rgba(245,255,230,1) 0%, rgba(210,250,120,0.95) 25%, rgba(163,230,53,0.8) 55%, rgba(130,180,40,0.5) 80%, rgba(60,100,25,0.2) 100%)"
              : "radial-gradient(circle at 38% 32%, rgba(230,255,200,0.95) 0%, rgba(190,242,100,0.85) 25%, rgba(132,204,22,0.6) 55%, rgba(100,160,30,0.3) 80%, rgba(40,80,15,0.1) 100%)",
            boxShadow: isError
              ? "inset 0 -15px 30px rgba(100,20,10,0.3), inset 0 10px 20px rgba(255,200,200,0.2), 0 0 40px rgba(239,68,68,0.2)"
              : isApproval
              ? "inset 0 -15px 30px rgba(100,80,10,0.3), inset 0 10px 20px rgba(255,250,200,0.25), 0 0 50px rgba(250,204,21,0.25)"
              : isCompleted
              ? "inset 0 -15px 30px rgba(10,80,30,0.3), inset 0 10px 20px rgba(220,255,220,0.2), 0 0 40px rgba(34,197,94,0.2)"
              : state === "speaking"
              ? "inset 0 -15px 30px rgba(50,80,20,0.3), inset 0 10px 20px rgba(240,255,220,0.25), 0 0 50px rgba(190,242,100,0.25)"
              : state === "listening"
              ? "inset 0 -15px 30px rgba(50,80,20,0.3), inset 0 10px 20px rgba(240,255,220,0.2), 0 0 40px rgba(190,242,100,0.2)"
              : state === "generating"
              ? "inset 0 -15px 30px rgba(50,80,20,0.3), inset 0 10px 20px rgba(245,255,230,0.25), 0 0 45px rgba(210,250,120,0.2)"
              : "inset 0 -15px 30px rgba(50,80,20,0.3), inset 0 10px 20px rgba(240,255,220,0.15), 0 0 30px rgba(190,242,100,0.15)",
          }}
        >
          {/* Inner highlight (glassy sphere look) */}
          <div
            className="absolute rounded-full pointer-events-none"
            style={{
              top: "15%",
              left: "25%",
              width: "30%",
              height: "25%",
              background: "radial-gradient(ellipse, rgba(255,255,255,0.25) 0%, transparent 70%)",
              filter: "blur(4px)",
            }}
          />

          {/* Orb icon — changes based on state */}
          <span
            className="relative z-10"
            style={{
              fontSize: size * 0.33,
              filter: "drop-shadow(0 0 12px rgba(190,242,100,0.6))",
            }}
          >
            {isError ? "⚠" : isApproval ? "?" : isCompleted ? "✓" : isCancelled ? "✕" : "✦"}
          </span>
        </motion.div>
      </div>

      {/* Label */}
      {showLabel && (
        <div className="mt-4 text-center">
          <span className="text-xs text-text-secondary">
            <span className="font-semibold text-accent">{ORB_STATE_LABELS[state]}</span>
          </span>
        </div>
      )}
    </div>
  );
}
