"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  User,
  Building2,
  KeyRound,
  CreditCard,
  Bell,
  Palette,
  Plus,
  Copy,
  Trash2,
  Check,
  Crown,
  Mail,
  Clock,
} from "lucide-react";
import { Card, Card3D } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { ProgressBar } from "@/components/ui/charts";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "org", label: "Organization", icon: Building2 },
  { id: "api", label: "API Access", icon: KeyRound },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "appearance", label: "Appearance", icon: Palette },
];

const MEMBERS = [
  { id: "m1", name: "Aarav Mehta", email: "aarav@brewcraft.co", role: "Owner", avatar: "AM", color: "bg-accent/20 text-accent" },
  { id: "m2", name: "Priya Sharma", email: "priya@brewcraft.co", role: "Admin", avatar: "PS", color: "bg-info/20 text-info" },
  { id: "m3", name: "Rohan Kapoor", email: "rohan@brewcraft.co", role: "Editor", avatar: "RK", color: "bg-success/20 text-success" },
  { id: "m4", name: "Sara Khan", email: "sara@brewcraft.co", role: "Viewer", avatar: "SK", color: "bg-white/10 text-text-secondary" },
];

const TOKENS = [
  { id: "t1", name: "Production API", scopes: ["campaigns:rw", "reports:r"], created: "Jan 12, 2025", lastUsed: "2h ago" },
  { id: "t2", name: "Analytics Export", scopes: ["reports:r"], created: "Feb 03, 2025", lastUsed: "1d ago" },
  { id: "t3", name: "Webhook Sync", scopes: ["campaigns:r", "audiences:rw"], created: "Mar 18, 2025", lastUsed: "5m ago" },
];

const ALL_SCOPES = ["campaigns:rw", "campaigns:r", "reports:r", "audiences:rw", "audiences:r", "billing:r"];

const INVOICES = [
  { id: "i1", date: "Mar 01, 2025", amount: "₹49,000", status: "Paid" },
  { id: "i2", date: "Feb 01, 2025", amount: "₹49,000", status: "Paid" },
  { id: "i3", date: "Jan 01, 2025", amount: "₹29,000", status: "Paid" },
  { id: "i4", date: "Dec 01, 2024", amount: "₹29,000", status: "Paid" },
];

const NOTIF_TYPES = [
  { id: "n1", label: "Campaign performance alerts", desc: "Get notified when ROAS drops below threshold", on: true },
  { id: "n2", label: "AI weekly summary", desc: "Receive AI-generated performance digest every Monday", on: true },
  { id: "n3", label: "Budget threshold warnings", desc: "Alert when spend reaches 80% of monthly cap", on: true },
  { id: "n4", label: "Creative approval requests", desc: "Notify when AI-generated creative needs review", on: false },
  { id: "n5", label: "Channel disconnections", desc: "Alert when an ad account disconnects", on: true },
  { id: "n6", label: "Product updates", desc: "News about new features and improvements", on: false },
];

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

export default function SettingsPage() {
  const [tab, setTab] = useState("profile");
  const [notifs, setNotifs] = useState(() =>
    Object.fromEntries(NOTIF_TYPES.map((n) => [n.id, n.on])),
  );
  const [newTokenScopes, setNewTokenScopes] = useState<string[]>([]);
  const [showCreateToken, setShowCreateToken] = useState(false);

  return (
    <div className="p-8 max-w-[1400px] mx-auto animate-fade-in">
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
              <Card className="lg:col-span-1 flex flex-col items-center text-center">
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-accent/30 to-accent/5 flex items-center justify-center mb-4 glow-ring">
                  <span className="font-display text-3xl font-semibold text-accent">AM</span>
                </div>
                <p className="font-display text-lg font-medium text-text">Aarav Mehta</p>
                <p className="text-sm text-text-secondary">Owner</p>
                <span className="badge badge-accent mt-3">Pro Plan</span>
                <button className="btn-ghost text-xs mt-4">Change Avatar</button>
              </Card>
              <Card className="lg:col-span-2">
                <SectionHeader title="Profile Details" subtitle="Your personal information" />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="label-field mb-1.5 block">Full Name</label>
                    <input className="input-field" defaultValue="Aarav Mehta" />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Email</label>
                    <input className="input-field" defaultValue="aarav@brewcraft.co" />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Role</label>
                    <input className="input-field" defaultValue="Owner" disabled />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Timezone</label>
                    <select className="input-field">
                      <option>Asia/Kolkata (IST)</option>
                      <option>America/New_York (EST)</option>
                      <option>Europe/London (GMT)</option>
                    </select>
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Phone</label>
                    <input className="input-field" defaultValue="+91 98765 43210" />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Department</label>
                    <input className="input-field" defaultValue="Marketing" />
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button className="btn-ghost">Cancel</button>
                  <button className="btn-primary flex items-center gap-2">
                    <Check className="w-4 h-4" /> Save Changes
                  </button>
                </div>
              </Card>
            </div>
          )}

          {/* Organization */}
          {tab === "org" && (
            <div className="space-y-6">
              <Card>
                <SectionHeader title="Organization" subtitle="Company details and plan" />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="label-field mb-1.5 block">Organization Name</label>
                    <input className="input-field" defaultValue="BrewCraft Coffee Pvt Ltd" />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Industry</label>
                    <select className="input-field">
                      <option>Food & Beverage</option>
                      <option>Retail</option>
                      <option>Technology</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-4 rounded-lg bg-accent/5 border border-accent/20">
                  <Crown className="w-5 h-5 text-accent" />
                  <div className="flex-1">
                    <p className="font-display text-sm text-text">Current Plan: Pro</p>
                    <p className="text-xs text-text-secondary">Renews on Apr 01, 2025</p>
                  </div>
                  <button className="btn-primary text-xs">Upgrade</button>
                </div>
              </Card>

              <Card>
                <SectionHeader
                  title="Members"
                  subtitle="Manage team access"
                  action={
                    <button className="btn-primary text-xs flex items-center gap-1.5">
                      <Plus className="w-3.5 h-3.5" /> Invite
                    </button>
                  }
                />
                <div className="space-y-2">
                  {MEMBERS.map((m) => (
                    <div
                      key={m.id}
                      className="flex items-center justify-between p-3 rounded-lg hover:bg-white/[0.03] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn("w-10 h-10 rounded-full flex items-center justify-center font-display text-sm font-medium", m.color)}>
                          {m.avatar}
                        </div>
                        <div>
                          <p className="font-display text-sm text-text">{m.name}</p>
                          <p className="text-xs text-text-muted font-mono">{m.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={cn(
                          "badge",
                          m.role === "Owner" ? "badge-accent" : "badge",
                        )}>{m.role}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* API Access */}
          {tab === "api" && (
            <div className="space-y-6">
              <Card>
                <SectionHeader
                  title="API Tokens"
                  subtitle="Manage programmatic access"
                  action={
                    <button
                      onClick={() => setShowCreateToken((v) => !v)}
                      className="btn-primary text-xs flex items-center gap-1.5"
                    >
                      <Plus className="w-3.5 h-3.5" /> Create Token
                    </button>
                  }
                />
                {showCreateToken && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="mb-4 p-4 rounded-lg bg-white/[0.03] border border-white/[0.06]"
                  >
                    <p className="label-field mb-2">Select Scopes</p>
                    <div className="flex flex-wrap gap-2 mb-4">
                      {ALL_SCOPES.map((s) => (
                        <button
                          key={s}
                          onClick={() =>
                            setNewTokenScopes((prev) =>
                              prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
                            )
                          }
                          className={cn(
                            "badge transition-colors",
                            newTokenScopes.includes(s) ? "badge-accent" : "hover:bg-white/10",
                          )}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button className="btn-primary text-xs">Generate</button>
                      <button onClick={() => setShowCreateToken(false)} className="btn-ghost text-xs">
                        Cancel
                      </button>
                    </div>
                  </motion.div>
                )}
                <div className="space-y-2">
                  {TOKENS.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-display text-sm text-text">{t.name}</span>
                          <span className="font-mono text-[10px] text-text-muted">
                            sk-...{t.id}4f2a
                          </span>
                          <button className="text-text-muted hover:text-accent transition-colors">
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-1.5 mb-1">
                          {t.scopes.map((s) => (
                            <span key={s} className="badge text-[10px]">{s}</span>
                          ))}
                        </div>
                        <p className="text-[10px] text-text-muted font-mono">
                          Created {t.created} · Last used {t.lastUsed}
                        </p>
                      </div>
                      <button className="text-text-muted hover:text-danger transition-colors p-2">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Billing */}
          {tab === "billing" && (
            <div className="space-y-6">
              <Card>
                <SectionHeader title="Current Plan" subtitle="Your subscription details" />
                <div className="flex items-center justify-between p-5 rounded-xl bg-gradient-to-r from-accent/10 to-transparent border border-accent/20">
                  <div className="flex items-center gap-4">
                    <Crown className="w-8 h-8 text-accent" />
                    <div>
                      <p className="font-display text-xl font-semibold text-text">Pro Plan</p>
                      <p className="text-sm text-text-secondary">₹49,000/month · Renews Apr 01</p>
                    </div>
                  </div>
                  <button className="btn-primary">Manage Plan</button>
                </div>
              </Card>

              <Card>
                <SectionHeader title="Usage" subtitle="Current billing cycle consumption" />
                <div className="space-y-5">
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="font-display text-sm text-text">AI Tokens</span>
                      <span className="font-mono text-xs text-text-secondary">1.2M / 2M</span>
                    </div>
                    <ProgressBar value={60} accent="accent" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="font-display text-sm text-text">Ad Spend Tracked</span>
                      <span className="font-mono text-xs text-text-secondary">₹38L / ₹50L</span>
                    </div>
                    <ProgressBar value={76} accent="info" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="font-display text-sm text-text">API Calls</span>
                      <span className="font-mono text-xs text-text-secondary">340K / 500K</span>
                    </div>
                    <ProgressBar value={68} accent="success" />
                  </div>
                </div>
              </Card>

              <Card>
                <SectionHeader title="Payment Method" />
                <div className="flex items-center justify-between p-4 rounded-lg bg-white/[0.03]">
                  <div className="flex items-center gap-3">
                    <CreditCard className="w-6 h-6 text-text-secondary" />
                    <div>
                      <p className="font-display text-sm text-text">•••• •••• •••• 4242</p>
                      <p className="text-xs text-text-muted">Expires 08/27</p>
                    </div>
                  </div>
                  <button className="btn-ghost text-xs">Update</button>
                </div>
              </Card>

              <Card>
                <SectionHeader title="Invoices" subtitle="Download past invoices" />
                <div className="space-y-2">
                  {INVOICES.map((inv) => (
                    <div
                      key={inv.id}
                      className="flex items-center justify-between p-3 rounded-lg hover:bg-white/[0.03] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <Clock className="w-4 h-4 text-text-muted" />
                        <div>
                          <p className="font-mono text-sm text-text">{inv.date}</p>
                          <p className="text-xs text-text-muted">{inv.amount}</p>
                        </div>
                      </div>
                      <span className="badge badge-success">{inv.status}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Notifications */}
          {tab === "notifications" && (
            <Card>
              <SectionHeader title="Notifications" subtitle="Choose what you want to hear about" />
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
            </Card>
          )}

          {/* Appearance */}
          {tab === "appearance" && (
            <Card>
              <SectionHeader title="Appearance" subtitle="Customize your interface" />
              <div className="space-y-6">
                <div>
                  <p className="label-field mb-3">Theme</p>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { id: "dark", label: "Dark", active: true },
                      { id: "midnight", label: "Midnight", active: false },
                      { id: "system", label: "System", active: false },
                    ].map((th) => (
                      <button
                        key={th.id}
                        className={cn(
                          "p-4 rounded-xl border-2 transition-all text-center",
                          th.active
                            ? "border-accent bg-accent/5"
                            : "border-white/[0.06] hover:border-white/20",
                        )}
                      >
                        <div className={cn(
                          "w-full h-16 rounded-lg mb-2",
                          th.id === "dark" && "bg-gradient-to-br from-bg to-bg-surface",
                          th.id === "midnight" && "bg-gradient-to-br from-[#0a0a1a] to-[#1a1a3a]",
                          th.id === "system" && "bg-gradient-to-br from-bg to-bg-surface",
                        )} />
                        <span className={cn("text-sm font-medium", th.active ? "text-accent" : "text-text-secondary")}>
                          {th.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="label-field mb-3">Accent Color</p>
                  <div className="flex gap-3">
                    {["#FFD400", "#22C55E", "#3B82F6", "#EF4444", "#A855F7"].map((c, i) => (
                      <button
                        key={c}
                        className={cn(
                          "w-10 h-10 rounded-full transition-all",
                          i === 0 && "ring-2 ring-offset-2 ring-offset-bg ring-accent",
                        )}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
