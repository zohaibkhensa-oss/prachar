"use client";

import { motion } from "framer-motion";
import { FlaskConical, Bell } from "lucide-react";
import { useState } from "react";

/**
 * LabsBanner — honestly marks a page as in active development.
 * No fake buttons. No "coming soon" toasts. Just the truth.
 *
 * Usage: place at the top of a Tier 3 page.
 * <LabsBanner title="AI Video" description="Generate marketing videos from text prompts." />
 */
export function LabsBanner({
  title,
  description,
  features,
}: {
  title: string;
  description: string;
  features?: string[];
}) {
  const [notified, setNotified] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-2xl border border-accent/20 bg-accent/[0.04] p-5"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
          <FlaskConical className="w-5 h-5 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-accent font-semibold">
              Labs
            </span>
            <span className="text-[10px] text-text-muted">· In active development</span>
          </div>
          <h2 className="font-display text-base font-semibold text-text mt-1">{title}</h2>
          <p className="text-sm text-text-secondary mt-1">{description}</p>

          {features && features.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {features.map((f) => (
                <span
                  key={f}
                  className="text-[11px] px-2 py-1 rounded-md bg-white/[0.03] border border-white/[0.06] text-text-muted"
                >
                  {f}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={() => setNotified(true)}
            disabled={notified}
            className="mt-3 inline-flex items-center gap-1.5 text-xs text-accent hover:text-accent/80 transition-colors disabled:opacity-60"
          >
            <Bell className="w-3.5 h-3.5" />
            {notified ? "We'll notify you when it's ready" : "Notify me when available"}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
