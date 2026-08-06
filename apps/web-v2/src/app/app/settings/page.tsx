"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  User,
  Building2,
  KeyRound,
  CreditCard,
  Bell,
  Check,
  Crown,
  Clock,
  Loader2,
  Sparkles,
  Zap,
  AlertCircle,
  Copy,
  Plus,
  Download,
  FileText,
} from "lucide-react";
import { Card } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { apiGet } from "@/lib/api";

// ─── Types matching backend schemas ──────────────────────────────────────────

interface UserOut {
  id: string;
  email: string;
  role: string; // owner | admin | member
  tenant_id: string;
}

interface SubscriptionOut {
  plan: string; // starter | growth | agency
  status: string; // active | past_due | canceled | trialing
  provider: string | null;
  sub_id: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

interface PlanDeliverable {
  label: string;
  value: string;
  included: boolean;
}

interface PlanOut {
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
  deliverables: PlanDeliverable[];
}

interface PlansResponse {
  plans: PlanOut[];
  currency: string;
}

interface ApiTokenOut {
  id: string;
  name: string;
  token: string; // masked
  scopes: string[];
  created_at: string;
}

interface InvoiceOut {
  id: string;
  tenant_id: string;
  plan: string;
  amount_inr: number;
  gst_inr: number;
  total_inr: number;
  currency: string;
  status: string;
  created_at: string;
  invoice_number: string;
  gstin: string | null;
}

interface InvoicesResponse {
  invoices: InvoiceOut[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const TABS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "org", label: "Organization", icon: Building2 },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "api", label: "API Access", icon: KeyRound },
  { id: "notifications", label: "Notifications", icon: Bell },
];

const NOTIF_TYPES = [
  { id: "n1", label: "Campaign performance alerts", desc: "Get notified when ROAS drops below threshold", on: true },
  { id: "n2", label: "AI weekly summary", desc: "Receive AI-generated performance digest every Monday", on: true },
  { id: "n3", label: "Budget threshold warnings", desc: "Alert when spend reaches 80% of monthly cap", on: true },
  { id: "n4", label: "Creative approval requests", desc: "Notify when AI-generated creative needs review", on: false },
  { id: "n5", label: "Channel disconnections", desc: "Alert when an ad account disconnects", on: true },
  { id: "n6", label: "Product updates", desc: "News about new features and improvements", on: false },
];

const PLAN_LABELS: Record<string, string> = {
  starter: "Starter",
  growth: "Growth",
  agency: "Agency",
};

const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};

const PLAN_ICONS: Record<string, typeof Sparkles> = {
  Sparkles: Sparkles,
  Zap: Zap,
  Crown: Crown,
};

// ─── Small UI helpers ────────────────────────────────────────────────────────

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative w-11 h-6 rounded-full transition-colors duration-200",
        on ? "bg-accent" : "bg-white/[0.1]",
      )}
    >
      <motion.div
        layout
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className={cn(
          "absolute top-0.5 w-5 h-5 rounded-full bg-bg shadow-md",
          on ? "left-[22px]" : "left-0.5",
        )}
      />
    </button>
  );
}

function LoadingRow({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-4">
      <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
      <span className="text-sm text-text-secondary">{label}</span>
    </div>
  );
}

function ErrorRow({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 py-4">
      <AlertCircle className="w-4 h-4 text-danger" />
      <p className="text-sm text-text-secondary">{message}</p>
    </div>
  );
}

function initialsFromEmail(email: string): string {
  const name = email.split("@")[0] ?? email;
  const parts = name.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2 && parts[0] && parts[1]) {
    return (parts[0][0]! + parts[1][0]!).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

// ─── Data hooks ──────────────────────────────────────────────────────────────

function useCurrentUser() {
  return useQuery<UserOut>({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<UserOut>("/auth/me"),
    retry: 1,
  });
}

function useSubscription() {
  return useQuery<SubscriptionOut>({
    queryKey: ["billing", "subscription"],
    queryFn: () => apiGet<SubscriptionOut>("/billing/subscription"),
    retry: 1,
  });
}

function useInvoices(enabled: boolean) {
  return useQuery<InvoicesResponse>({
    queryKey: ["billing", "invoices"],
    queryFn: () => apiGet<InvoicesResponse>("/billing/invoices"),
    enabled,
    retry: 1,
  });
}

function usePlans() {
  return useQuery<PlansResponse>({
    queryKey: ["billing", "plans"],
    queryFn: () => apiGet<PlansResponse>("/billing/plans"),
    retry: 1,
  });
}

function useApiTokens(enabled: boolean) {
  return useQuery<ApiTokenOut[]>({
    queryKey: ["admin", "api-tokens"],
    queryFn: () => apiGet<ApiTokenOut[]>("/admin/api-tokens"),
    enabled,
    retry: 1,
  });
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [tab, setTab] = useState("profile");
  const [notifs, setNotifs] = useState(() =>
    Object.fromEntries(NOTIF_TYPES.map((n) => [n.id, n.on])),
  );
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const userQuery = useCurrentUser();
  const subQuery = useSubscription();
  const plansQuery = usePlans();
  const isAgencyPlan = subQuery.data?.plan === "agency";
  const tokensQuery = useApiTokens(tab === "api" && !!isAgencyPlan);
  const invoicesQuery = useInvoices(tab === "billing" && !!subQuery.data);
  const invoices = invoicesQuery.data?.invoices ?? [];

  const user = userQuery.data;
  const sub = subQuery.data;
  const plans = plansQuery.data?.plans ?? [];
  const planLabel = sub ? (PLAN_LABELS[sub.plan] ?? sub.plan) : null;
  const roleLabel = user ? (ROLE_LABELS[user.role] ?? user.role) : null;

  const handleCopyToken = (token: string) => {
    navigator.clipboard.writeText(token).then(() => {
      setCopiedToken(token);
      setTimeout(() => setCopiedToken(null), 2000);
    });
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto animate-fade-in pb-32">
      <div className="mb-8">
        <h1 className="font-display uppercase text-4xl tracking-wide text-text mb-1">Settings</h1>
        <p className="text-sm text-text-secondary">Manage your account, organization, and preferences.</p>
      </div>

      {/* Tab nav */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-bg-card border border-white/[0.04] mb-8 overflow-x-auto">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
                tab === t.id
                  ? "bg-accent text-bg"
                  : "text-text-secondary hover:text-text hover:bg-white/[0.03]",
              )}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {/* Profile */}
          {tab === "profile" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 flex flex-col items-center text-center" hover={false}>
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-accent/30 to-accent/5 flex items-center justify-center mb-4 glow-ring">
                  <span className="font-display text-3xl font-semibold text-accent">
                    {user ? initialsFromEmail(user.email) : "··"}
                  </span>
                </div>
                {userQuery.isLoading ? (
                  <LoadingRow label="Loading profile…" />
                ) : userQuery.error ? (
                  <ErrorRow message="Could not load your profile." />
                ) : user ? (
                  <>
                    <p className="font-display text-lg font-medium text-text">{user.email}</p>
                    <p className="text-sm text-text-secondary">{roleLabel}</p>
                    {planLabel && (
                      <span className="badge badge-accent mt-3">{planLabel} Plan</span>
                    )}
                  </>
                ) : null}
              </Card>
              <Card className="lg:col-span-2" hover={false}>
                <SectionHeader title="Profile Details" subtitle="Your personal information" />
                {userQuery.isLoading ? (
                  <LoadingRow label="Loading profile details…" />
                ) : userQuery.error ? (
                  <ErrorRow message="Could not load your profile details." />
                ) : user ? (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="label-field mb-1.5 block">Email</label>
                        <input className="input-field" defaultValue={user.email} disabled />
                      </div>
                      <div>
                        <label className="label-field mb-1.5 block">Role</label>
                        <input className="input-field" defaultValue={roleLabel ?? user.role} disabled />
                      </div>
                      <div>
                        <label className="label-field mb-1.5 block">Tenant ID</label>
                        <input className="input-field font-mono text-xs" defaultValue={user.tenant_id} disabled />
                      </div>
                      <div>
                        <label className="label-field mb-1.5 block">Timezone</label>
                        <select className="input-field" disabled>
                          <option>Asia/Kolkata (IST)</option>
                          <option>America/New_York (EST)</option>
                          <option>Europe/London (GMT)</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex justify-end gap-3 mt-6">
                      <button disabled title="Profile editing coming soon" className="btn-primary flex items-center gap-2 opacity-40 cursor-not-allowed">
                        <Check className="w-4 h-4" /> Save Changes
                      </button>
                    </div>
                  </>
                ) : null}
              </Card>
            </div>
          )}

          {/* Organization */}
          {tab === "org" && (
            <div className="space-y-6">
              <Card hover={false}>
                <SectionHeader title="Organization" subtitle="Workspace details and plan" />
                {userQuery.isLoading ? (
                  <LoadingRow label="Loading organization…" />
                ) : userQuery.error ? (
                  <ErrorRow message="Could not load organization details." />
                ) : user ? (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                      <div>
                        <label className="label-field mb-1.5 block">Workspace ID</label>
                        <input className="input-field font-mono text-xs" defaultValue={user.tenant_id} disabled />
                      </div>
                      <div>
                        <label className="label-field mb-1.5 block">Plan</label>
                        <input className="input-field" defaultValue={planLabel ?? "—"} disabled />
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-4 rounded-lg bg-accent/5 border border-accent/20">
                      <Crown className="w-5 h-5 text-accent" />
                      <div className="flex-1">
                        <p className="font-display text-sm text-text">
                          Current Plan: {planLabel ?? "—"}
                        </p>
                        <p className="text-xs text-text-secondary">
                          {sub?.status ? `Status: ${sub.status}` : ""}
                        </p>
                      </div>
                      <button
                        onClick={() => setTab("billing")}
                        className="btn-primary text-xs"
                      >
                        Upgrade
                      </button>
                    </div>
                  </>
                ) : null}
              </Card>

              <Card hover={false}>
                <SectionHeader title="Members" subtitle="Manage team access" />
                <div className="py-8 text-center">
                  <Building2 className="w-10 h-10 text-text-muted mx-auto mb-3" />
                  <p className="text-sm text-text-secondary">Team management is coming soon.</p>
                </div>
              </Card>
            </div>
          )}

          {/* Billing */}
          {tab === "billing" && (
            <div className="space-y-6">
              {/* Current Plan */}
              <Card hover={false}>
                <SectionHeader title="Current Plan" subtitle="Your subscription details" />
                {subQuery.isLoading ? (
                  <LoadingRow label="Loading subscription…" />
                ) : subQuery.error ? (
                  <ErrorRow message="Could not load subscription details." />
                ) : sub ? (
                  <div className="flex items-center justify-between p-5 rounded-xl bg-gradient-to-r from-accent/10 to-transparent border border-accent/20 flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                      <Crown className="w-8 h-8 text-accent" />
                      <div>
                        <p className="font-display text-xl font-semibold text-text">
                          {planLabel ?? sub.plan} Plan
                        </p>
                        <p className="text-sm text-text-secondary flex items-center gap-1.5">
                          <span className={cn(
                            "inline-block w-2 h-2 rounded-full",
                            sub.status === "active" || sub.status === "trialing" ? "bg-success" : "bg-warning",
                          )} />
                          Status: {sub.status}
                          {sub.current_period_end ? ` · Renews ${sub.current_period_end}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {sub.cancel_at_period_end && (
                        <span className="badge badge-warning">Cancels at period end</span>
                      )}
                    </div>
                  </div>
                ) : null}
              </Card>

              {/* Plans */}
              <Card hover={false}>
                <SectionHeader
                  title="Available Plans"
                  subtitle="Upgrade or change your plan"
                  icon={<CreditCard className="w-4 h-4" />}
                />
                {plansQuery.isLoading ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[0, 1, 2].map((i) => (
                      <Skeleton key={i} className="h-80 rounded-xl" />
                    ))}
                  </div>
                ) : plansQuery.error ? (
                  <ErrorRow message="Could not load plans." />
                ) : plans.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {plans.map((p, i) => {
                      const Icon = PLAN_ICONS[p.icon] ?? Sparkles;
                      const isCurrent = sub?.plan === p.key;
                      return (
                        <motion.div
                          key={p.key}
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.08 }}
                          className={cn(
                            "card-3d rounded-xl p-5 flex flex-col relative",
                            p.popular && "border-accent/40",
                          )}
                        >
                          {p.popular && (
                            <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 badge badge-accent text-[10px]">
                              Most Popular
                            </span>
                          )}
                          <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                              <Icon className="w-5 h-5 text-accent" />
                            </div>
                            <div>
                              <h3 className="font-display text-lg font-semibold text-text">{p.name}</h3>
                              <p className="text-[11px] text-text-secondary leading-tight">{p.tagline}</p>
                            </div>
                          </div>
                          <div className="mb-4">
                            <span className="font-display text-3xl font-bold text-text">
                              ₹{p.price_inr.toLocaleString("en-IN")}
                            </span>
                            <span className="text-sm text-text-secondary">/mo</span>
                          </div>
                          <ul className="space-y-2 mb-6 flex-1">
                            {p.deliverables.map((d) => (
                              <li key={d.label} className="flex items-start gap-2 text-xs">
                                {d.included ? (
                                  <Check className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
                                ) : (
                                  <span className="w-3.5 h-3.5 shrink-0 mt-0.5 flex items-center justify-center text-text-muted">—</span>
                                )}
                                <span className={cn(d.included ? "text-text-secondary" : "text-text-muted line-through")}>
                                  <span className="font-medium text-text">{d.label}:</span> {d.value}
                                </span>
                              </li>
                            ))}
                          </ul>
                          {isCurrent ? (
                            <button disabled className="btn-secondary w-full opacity-60 cursor-default">
                              Current Plan
                            </button>
                          ) : (
                            <a
                              href="/app/pricing"
                              className={cn(
                                "w-full text-center",
                                p.popular ? "btn-primary" : "btn-secondary",
                              )}
                            >
                              {sub && p.price_inr > (plans.find((x) => x.key === sub.plan)?.price_inr ?? 0)
                                ? "Upgrade"
                                : "Choose Plan"}
                            </a>
                          )}
                        </motion.div>
                      );
                    })}
                  </div>
                ) : (
                  <ErrorRow message="No plans available." />
                )}
              </Card>

              {/* Payment Method */}
              <Card hover={false}>
                <SectionHeader title="Payment Method" />
                <div className="py-8 text-center">
                  <CreditCard className="w-10 h-10 text-text-muted mx-auto mb-3" />
                  <p className="text-sm text-text-secondary">No payment method on file.</p>
                </div>
              </Card>

              {/* Invoices */}
              <Card hover={false}>
                <SectionHeader title="Invoices" subtitle="Download past invoices (PDF)" />
                {invoicesQuery.isLoading ? (
                  <LoadingRow label="Loading invoices…" />
                ) : invoicesQuery.error ? (
                  <ErrorRow message="Could not load invoices." />
                ) : invoices.length === 0 ? (
                  <div className="py-8 text-center">
                    <Clock className="w-10 h-10 text-text-muted mx-auto mb-3" />
                    <p className="text-sm text-text-secondary">No invoices yet.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {invoices.map((inv) => (
                      <div
                        key={inv.id}
                        className="flex items-center justify-between p-4 hover:bg-surface-secondary/50 transition rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                            <FileText className="w-5 h-5 text-accent" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-text">
                              {inv.invoice_number}
                            </p>
                            <p className="text-xs text-text-secondary">
                              {PLAN_LABELS[inv.plan] ?? inv.plan} ·{" "}
                              Rs. {inv.total_inr.toLocaleString("en-IN")} ·{" "}
                              {new Date(inv.created_at).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span
                            className={cn(
                              "text-xs px-2 py-1 rounded-full font-medium",
                              inv.status === "active"
                                ? "bg-success/10 text-success"
                                : "bg-warning/10 text-warning"
                            )}
                          >
                            {inv.status.toUpperCase()}
                          </span>
                          <a
                            href={`/api/billing/invoices/${inv.invoice_number}/pdf`}
                            download={`${inv.invoice_number}.pdf`}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 text-accent text-sm font-medium hover:bg-accent/20 transition"
                          >
                            <Download className="w-4 h-4" />
                            PDF
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* API Access */}
          {tab === "api" && (
            <div className="space-y-6">
              <Card hover={false}>
                <SectionHeader
                  title="API Tokens"
                  subtitle="Manage programmatic access to your PRACHAR data"
                  icon={<KeyRound className="w-4 h-4" />}
                />
                {subQuery.isLoading ? (
                  <LoadingRow label="Checking your plan…" />
                ) : !isAgencyPlan ? (
                  <div className="py-12 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                      <Crown className="w-7 h-7 text-accent" />
                    </div>
                    <h3 className="font-display text-lg font-medium text-text mb-2">
                      Agency Plan Required
                    </h3>
                    <p className="text-sm text-text-secondary max-w-sm mx-auto mb-6">
                      API tokens are available on the Agency plan. Upgrade to
                      get full REST API access and webhooks.
                    </p>
                    <button
                      onClick={() => setTab("billing")}
                      className="btn-primary inline-flex items-center gap-2"
                    >
                      <Crown className="w-4 h-4" /> Upgrade to Agency
                    </button>
                  </div>
                ) : tokensQuery.isLoading ? (
                  <LoadingRow label="Loading API tokens…" />
                ) : tokensQuery.error ? (
                  <ErrorRow message="Could not load API tokens." />
                ) : tokensQuery.data && tokensQuery.data.length > 0 ? (
                  <div className="space-y-2">
                    {tokensQuery.data.map((t) => (
                      <div
                        key={t.id}
                        className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-display text-sm text-text">{t.name}</span>
                            <button
                              onClick={() => handleCopyToken(t.token)}
                              className="text-text-muted hover:text-accent transition-colors"
                              title="Copy token"
                            >
                              {copiedToken === t.token ? (
                                <Check className="w-3.5 h-3.5 text-success" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                            <span className="font-mono text-[10px] text-text-muted">{t.token}</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 mb-1">
                            {t.scopes.map((s) => (
                              <span key={s} className="badge text-[10px]">{s}</span>
                            ))}
                          </div>
                          <p className="text-[10px] text-text-muted font-mono">
                            Created {t.created_at}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-12 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mx-auto mb-4">
                      <KeyRound className="w-7 h-7 text-text-secondary" />
                    </div>
                    <h3 className="font-display text-lg font-medium text-text mb-2">
                      No API tokens yet
                    </h3>
                    <p className="text-sm text-text-secondary max-w-sm mx-auto mb-6">
                      Create an API token to access PRACHAR programmatically.
                    </p>
                    <button
                      disabled
                      title="Token creation coming soon"
                      className="btn-primary inline-flex items-center gap-2 opacity-50 cursor-not-allowed"
                    >
                      <Plus className="w-4 h-4" /> Create Token
                    </button>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* Notifications */}
          {tab === "notifications" && (
            <Card hover={false}>
              <SectionHeader title="Notifications" subtitle="Choose what you want to hear about" icon={<Bell className="w-4 h-4" />} />
              <div className="space-y-2">
                {NOTIF_TYPES.map((n) => (
                  <div
                    key={n.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <div className="flex-1">
                      <p className="font-display text-sm text-text">{n.label}</p>
                      <p className="text-xs text-text-secondary mt-0.5">{n.desc}</p>
                    </div>
                    <Toggle
                      on={notifs[n.id] ?? false}
                      onClick={() => setNotifs((prev) => ({ ...prev, [n.id]: !prev[n.id] }))}
                    />
                  </div>
                ))}
              </div>
              <p className="text-xs text-text-muted mt-4">
                Notification preferences are not saved yet — they reset when you leave this page.
              </p>
            </Card>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
