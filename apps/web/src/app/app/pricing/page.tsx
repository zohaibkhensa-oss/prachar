"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Check, X, Sparkles, Zap, Crown, Loader2, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface Deliverable {
  label: string;
  value: string;
  included: boolean;
}

interface Plan {
  key: string;
  name: string;
  tagline: string;
  price_inr: number;
  price_usd: number;
  currency_inr: string;
  currency_usd: string;
  popular: boolean;
  brands_limit: number;
  videos_per_month: number;
  images_per_month: number;
  platforms_limit: number;
  weekly_loop: boolean;
  google_ads: boolean;
  meta_ads: boolean;
  white_label: boolean;
  api_access: boolean;
  priority_support: boolean;
  ai_budget_inr: number;
  video_quality_tier: string;
  accent: string;
  icon: string;
  deliverables: Deliverable[];
}

interface PlansResponse {
  plans: Plan[];
  currency: string;
}

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Sparkles,
  Zap,
  Crown,
};

export default function PricingPage() {
  const [data, setData] = useState<PlansResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null); // plan_key being checked out
  const [currency, setCurrency] = useState<"INR" | "USD">("INR");

  useEffect(() => {
    void loadPlans();
  }, []);

  async function loadPlans() {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const { authedFetch } = await import("@/lib/auth");
      const res = await authedFetch(`${apiBase}/billing/plans`);
      if (!res.ok) throw new Error(`Failed to load plans: ${res.status}`);
      const json = (await res.json()) as PlansResponse;
      setData(json);
      setCurrency(json.currency as "INR" | "USD");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }

  async function startCheckout(planKey: string, provider: "stripe" | "razorpay") {
    setCheckoutLoading(`${planKey}-${provider}`);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const { authedFetch } = await import("@/lib/auth");
      const res = await authedFetch(`${apiBase}/billing/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: planKey,
          provider,
          success_url: `${window.location.origin}/app/settings?billing=success`,
          cancel_url: `${window.location.origin}/app/pricing?billing=cancelled`,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Checkout failed" }));
        throw new Error(err.detail || "Checkout failed");
      }
      const { checkout_url } = await res.json();
      if (checkout_url) {
        window.location.href = checkout_url;
      } else {
        throw new Error("No checkout URL returned");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
      setCheckoutLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-text-secondary">{error}</p>
        <button onClick={() => { setError(null); setLoading(true); void loadPlans(); }} className="btn-secondary">
          Retry
        </button>
      </div>
    );
  }

  const plans = data?.plans ?? [];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-3">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-text">
          Simple, transparent pricing
        </h1>
        <p className="text-text-secondary text-lg max-w-2xl mx-auto">
          One subscription. Everything included — AI strategy, videos, images, posting, ads, and analytics.
          No per-video charges. No hidden fees.
        </p>

        {/* Currency toggle */}
        <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-white/[0.04] border border-white/[0.06]">
          <button
            onClick={() => setCurrency("INR")}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              currency === "INR" ? "bg-accent/15 text-accent" : "text-text-secondary hover:text-text",
            )}
          >
            ₹ INR
          </button>
          <button
            onClick={() => setCurrency("USD")}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              currency === "USD" ? "bg-accent/15 text-accent" : "text-text-secondary hover:text-text",
            )}
          >
            $ USD
          </button>
        </div>
      </div>

      {/* Plans grid */}
      <div className="grid md:grid-cols-3 gap-6">
        {plans.map((plan, idx) => {
          const Icon = ICONS[plan.icon] ?? Sparkles;
          const price = currency === "INR" ? plan.price_inr : plan.price_usd;
          const symbol = currency === "INR" ? "₹" : "$";
          const isUnlimitedVideos = plan.videos_per_month === -1;
          const isUnlimitedImages = plan.images_per_month === -1;
          const isUnlimitedPlatforms = plan.platforms_limit === -1;

          return (
            <motion.div
              key={plan.key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className={cn(
                "relative rounded-2xl border p-6 flex flex-col",
                plan.popular
                  ? "border-accent/40 bg-gradient-to-b from-accent/[0.08] to-transparent shadow-lg shadow-accent/10"
                  : "border-white/[0.08] bg-white/[0.02]",
              )}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-accent text-white text-xs font-medium">
                  Most Popular
                </div>
              )}

              {/* Plan header */}
              <div className="flex items-center gap-3 mb-4">
                <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", `bg-${plan.accent}/15`)}>
                  <Icon className={cn("w-5 h-5", `text-${plan.accent}`)} />
                </div>
                <div>
                  <h3 className="font-display text-xl font-semibold text-text">{plan.name}</h3>
                  <p className="text-xs text-text-muted">{plan.tagline}</p>
                </div>
              </div>

              {/* Price */}
              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="font-display text-4xl font-bold text-text">{symbol}{price.toLocaleString()}</span>
                  <span className="text-text-secondary text-sm">/month</span>
                </div>
                <p className="text-xs text-text-muted mt-1">
                  {currency === "INR" ? "Billed monthly in INR" : "Billed monthly in USD"}
                </p>
              </div>

              {/* Quick stats */}
              <div className="grid grid-cols-2 gap-2 mb-6 text-xs">
                <div className="p-2 rounded-md bg-white/[0.03]">
                  <div className="text-text-muted">Brands</div>
                  <div className="font-medium text-text">{plan.brands_limit}</div>
                </div>
                <div className="p-2 rounded-md bg-white/[0.03]">
                  <div className="text-text-muted">Videos/mo</div>
                  <div className="font-medium text-text">{isUnlimitedVideos ? "Unlimited" : plan.videos_per_month}</div>
                </div>
                <div className="p-2 rounded-md bg-white/[0.03]">
                  <div className="text-text-muted">Images/mo</div>
                  <div className="font-medium text-text">{isUnlimitedImages ? "Unlimited" : plan.images_per_month}</div>
                </div>
                <div className="p-2 rounded-md bg-white/[0.03]">
                  <div className="text-text-muted">Platforms</div>
                  <div className="font-medium text-text">{isUnlimitedPlatforms ? "All" : plan.platforms_limit}</div>
                </div>
              </div>

              {/* Deliverables list */}
              <div className="space-y-2 mb-6 flex-1">
                {plan.deliverables.map((d) => (
                  <div key={d.label} className="flex items-start gap-2 text-sm">
                    {d.included ? (
                      <Check className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                    ) : (
                      <X className="w-4 h-4 text-text-muted flex-shrink-0 mt-0.5" />
                    )}
                    <div className={cn(d.included ? "text-text" : "text-text-muted")}>
                      <span className="font-medium">{d.label}:</span> <span className="text-text-secondary">{d.value}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Checkout buttons */}
              <div className="space-y-2">
                <button
                  onClick={() => startCheckout(plan.key, "razorpay")}
                  disabled={checkoutLoading === `${plan.key}-razorpay`}
                  className={cn(
                    "w-full py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2",
                    plan.popular
                      ? "btn-primary"
                      : "btn-secondary",
                    checkoutLoading === `${plan.key}-razorpay` && "opacity-50 cursor-not-allowed",
                  )}
                >
                  {checkoutLoading === `${plan.key}-razorpay` ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>Pay with Razorpay <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
                <button
                  onClick={() => startCheckout(plan.key, "stripe")}
                  disabled={checkoutLoading === `${plan.key}-stripe`}
                  className={cn(
                    "w-full py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2",
                    "bg-white/[0.04] border border-white/[0.08] text-text-secondary hover:text-text hover:bg-white/[0.06]",
                    checkoutLoading === `${plan.key}-stripe` && "opacity-50 cursor-not-allowed",
                  )}
                >
                  {checkoutLoading === `${plan.key}-stripe` ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>Pay with Stripe <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* FAQ section */}
      <div className="mt-12 max-w-3xl mx-auto space-y-4">
        <h2 className="font-display text-2xl font-semibold text-text text-center mb-6">Frequently asked questions</h2>
        {[
          {
            q: "Can I change plans anytime?",
            a: "Yes. Upgrades take effect immediately. Downgrades take effect at the end of your current billing cycle.",
          },
          {
            q: "What happens if I exceed my video limit?",
            a: "We'll notify you. You can upgrade to a higher plan or wait for the next billing cycle. We never charge overage fees.",
          },
          {
            q: "Do you charge per video?",
            a: "No. Your monthly subscription includes all videos, images, posts, and ads management. No per-unit charges.",
          },
          {
            q: "Which payment methods do you accept?",
            a: "Razorpay (UPI, cards, net banking, wallets — for India) and Stripe (cards, Apple Pay, Google Pay — international).",
          },
          {
            q: "Is there a free trial?",
            a: "Yes — every new account starts on a 14-day trial of the Growth plan. No credit card required.",
          },
        ].map((faq) => (
          <div key={faq.q} className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <p className="font-medium text-text text-sm">{faq.q}</p>
            <p className="text-text-secondary text-sm mt-1">{faq.a}</p>
          </div>
        ))}
      </div>

      {error && (
        <div className="fixed bottom-4 right-4 p-4 rounded-lg bg-error/10 border border-error/30 text-error text-sm max-w-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}
    </div>
  );
}
