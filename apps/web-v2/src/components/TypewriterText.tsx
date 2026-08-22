"use client";

import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";

interface TypewriterTextProps {
  text: string;
  speed?: number; // chars per frame
  className?: string;
  onDone?: () => void;
  startDelay?: number;
}

/**
 * TypewriterText — animates text appearing character-by-character,
 * simulating a streaming LLM response (Gemini-like).
 *
 * Renders instantly if text is short (≤ 60 chars) for snappy UX on
 * quick replies, and typewriter-animates longer responses.
 */
export function TypewriterText({
  text,
  speed = 2,
  className,
  onDone,
  startDelay = 0,
}: TypewriterTextProps) {
  const [displayed, setDisplayed] = useState("");
  const [isAnimating, setIsAnimating] = useState(false);
  const doneRef = useRef(false);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    // Short text — render instantly
    if (text.length <= 60) {
      setDisplayed(text);
      if (!doneRef.current) {
        doneRef.current = true;
        onDone?.();
      }
      return;
    }

    setIsAnimating(true);
    setDisplayed("");
    doneRef.current = false;

    const startTimer = setTimeout(() => {
      let charIndex = 0;

      const animate = () => {
        if (charIndex >= text.length) {
          setIsAnimating(false);
          if (!doneRef.current) {
            doneRef.current = true;
            onDone?.();
          }
          return;
        }

        // Add `speed` characters per frame
        const next = charIndex + speed;
        setDisplayed(text.slice(0, next));
        charIndex = next;

        frameRef.current = requestAnimationFrame(animate);
      };

      frameRef.current = requestAnimationFrame(animate);
    }, startDelay);

    return () => {
      clearTimeout(startTimer);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return (
    <span className={className}>
      {displayed}
      {isAnimating && (
        <motion.span
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 0.8, repeat: Infinity, ease: "easeInOut" }}
          className="inline-block w-[2px] h-[1em] bg-accent ml-0.5 align-text-bottom"
          style={{ borderRadius: "1px" }}
        />
      )}
    </span>
  );
}
