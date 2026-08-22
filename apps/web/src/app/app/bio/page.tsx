"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { Sparkline } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  Link as LinkIcon, Plus, GripVertical, Trash2, ExternalLink,
  Instagram, Youtube, Twitter, Linkedin, Facebook, Music2,
  Wand2, Eye, MousePointerClick, TrendingUp, Globe, Smartphone,
  Monitor, Check, Palette, Type, Layout, Eye as EyeIcon, Sparkles,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const THEMES = [
  { id: "gradient", name: "Gradient", bg: "linear-gradient(135deg, #667eea, #764ba2)", text: "#fff" },
  { id: "minimal", name: "Minimal", bg: "#ffffff", text: "#111" },
  { id: "dark", name: "Dark", bg: "#0B0F14", text: "#F9FAFB" },
  { id: "light", name: "Light", bg: "#f5f5f5", text: "#222" },
  { id: "neon", name: "Neon", bg: "linear-gradient(135deg, #FF006E, #8338EC)", text: "#fff" },
  { id: "pastel", name: "Pastel", bg: "linear-gradient(135deg, #a8edea, #fed6e3)", text: "#333" },
  { id: "corporate", name: "Corporate", bg: "#1e3a5f", text: "#fff" },
  { id: "creator", name: "Creator", bg: "linear-gradient(135deg, #f093fb, #f5576c)", text: "#fff" },
];

const FONTS = ["Inter", "Space Grotesk", "Poppins", "DM Sans", "Outfit", "Plus Jakarta Sans"];
const LAYOUTS = ["Stacked", "Grid", "Carousel"];

const SOCIAL_ICONS = [
  { id: "instagram", icon: Instagram, color: "#E1306C" },
  { id: "tiktok", icon: Music2, color: "#000" },
  { id: "youtube", icon: Youtube, color: "#FF0000" },
  { id: "twitter", icon: Twitter, color: "#1DA1F2" },
  { id: "linkedin", icon: Linkedin, color: "#0A66C2" },
  { id: "facebook", icon: Facebook, color: "#1877F2" },
];

const LINK_TYPES = [
  { id: "website", label: "Website", icon: ExternalLink },
  { id: "social", label: "Social", icon: Instagram },
  { id: "product", label: "Product", icon: LinkIcon },
  { id: "video", label: "Video", icon: Youtube },
  { id: "music", label: "Music", icon: Music2 },
  { id: "event", label: "Event", icon: Calendar },
];

function Calendar(props: any) { return <LinkIcon {...props} />; }

const INITIAL_LINKS = [
  { id: 1, title: "Shop Our Coffee", url: "prachar.coffee/shop", icon: "🛒", clicks: 1240, ctr: 8.5, conversions: 89 },
  { id: 2, title: "Cold Brew Subscription", url: "prachar.coffee/subscribe", icon: "☕", clicks: 890, ctr: 6.2, conversions: 56 },
  { id: 3, title: "Watch Our Story", url: "youtube.com/prachar", icon: "▶️", clicks: 670, ctr: 4.8, conversions: 12 },
  { id: 4, title: "Follow on Instagram", url: "instagram.com/prachar", icon: "📸", clicks: 450, ctr: 3.1, conversions: 0 },
  { id: 5, title: "Read Our Blog", url: "prachar.coffee/blog", icon: "📖", clicks: 320, ctr: 2.4, conversions: 8 },
  { id: 6, title: "Contact Us", url: "prachar.coffee/contact", icon: "✉️", clicks: 180, ctr: 1.5, conversions: 23 },
];

const CLICK_DATA = INITIAL_LINKS.map(l => ({ name: l.title.slice(0, 12), clicks: l.clicks }));

export default function BioPage() {
  const [name, setName] = useState("Prachar Coffee");
  const [bio, setBio] = useState("Premium coffee, powered by AI. Sustainable. Ethical. Delicious. ☕");
  const [verified, setVerified] = useState(true);
  const [theme, setTheme] = useState(THEMES[2]!);
  const [font, setFont] = useState("Space Grotesk");
  const [layout, setLayout] = useState("Stacked");
  const [links, setLinks] = useState(INITIAL_LINKS);
  const [activeSocial, setActiveSocial] = useState<string[]>(["instagram", "youtube", "twitter"]);
  const [customDomain, setCustomDomain] = useState("link.prachar.coffee");
  const [trackAnalytics, setTrackAnalytics] = useState(true);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">Link-in-Bio</h1>
          <p className="text-sm text-text-secondary mt-1">Your all-in-one bio link — better than Buffer's Start Page</p>
        </div>
        <button className="btn-primary text-sm"><Check className="w-4 h-4" />Publish</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Editor */}
        <div className="lg:col-span-7 space-y-4">
          {/* Profile */}
          <Card>
            <SectionHeader title="Profile" icon={<EyeIcon className="w-4 h-4" />} />
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-accent to-info flex items-center justify-center text-2xl font-bold text-bg">P</div>
                <button className="btn-secondary text-xs">Upload Avatar</button>
              </div>
              <div><label className="label-field block mb-1.5">Name</label><input value={name} onChange={(e) => setName(e.target.value)} className="input-field" /></div>
              <div><label className="label-field block mb-1.5">Verified Badge</label><button onClick={() => setVerified(!verified)} className={cn("w-full px-3 py-2 rounded-lg text-sm border transition-all", verified ? "bg-accent/10 border-accent/30 text-accent" : "bg-white/[0.02] border-white/[0.06] text-text-secondary")}>{verified ? "Verified ✓" : "Not Verified"}</button></div>
              <div className="col-span-2"><label className="label-field block mb-1.5">Bio</label><textarea value={bio} onChange={(e) => setBio(e.target.value)} className="input-field h-16 resize-none" maxLength={160} /><div className="text-right text-[10px] text-text-muted mt-1">{bio.length}/160</div></div>
            </div>
          </Card>

          {/* Theme */}
          <Card>
            <SectionHeader title="Theme & Appearance" icon={<Palette className="w-4 h-4" />} />
            <div className="space-y-4">
              <div>
                <label className="label-field block mb-2">Theme</label>
                <div className="grid grid-cols-4 gap-2">
                  {THEMES.map(t => (
                    <button key={t.id} onClick={() => setTheme(t)} className={cn("p-2 rounded-lg border-2 transition-all", theme.id === t.id ? "border-accent" : "border-white/[0.06] hover:border-white/[0.12]")}>
                      <div className="aspect-square rounded-md mb-1" style={{ background: t.bg }} />
                      <span className="text-[10px] text-text-secondary">{t.name}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label-field block mb-1.5">Font</label><select value={font} onChange={(e) => setFont(e.target.value)} className="input-field">{FONTS.map(f => <option key={f} value={f}>{f}</option>)}</select></div>
                <div><label className="label-field block mb-1.5">Layout</label><select value={layout} onChange={(e) => setLayout(e.target.value)} className="input-field">{LAYOUTS.map(l => <option key={l}>{l}</option>)}</select></div>
              </div>
            </div>
          </Card>

          {/* Links */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <SectionHeader title="Links" subtitle={`${links.length} links`} icon={<LinkIcon className="w-4 h-4" />} />
              <div className="flex gap-2">
                <button className="btn-secondary text-xs"><Wand2 className="w-3 h-3 inline mr-1" />AI Suggest</button>
                <button onClick={() => setLinks([...links, { id: Date.now(), title: "New Link", url: "", icon: "🔗", clicks: 0, ctr: 0, conversions: 0 }])} className="btn-primary text-xs"><Plus className="w-3 h-3 inline mr-1" />Add Link</button>
              </div>
            </div>
            <div className="space-y-2">
              {links.map((l, i) => (
                <motion.div key={l.id} drag="y" dragConstraints={{ top: 0, bottom: 0 }} whileDrag={{ scale: 1.02 }} className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <GripVertical className="w-4 h-4 text-text-muted cursor-grab" />
                  <span className="text-lg">{l.icon}</span>
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <input value={l.title} onChange={(e) => setLinks(links.map(x => x.id === l.id ? { ...x, title: e.target.value } : x))} className="input-field text-xs py-1" />
                    <input value={l.url} onChange={(e) => setLinks(links.map(x => x.id === l.id ? { ...x, url: e.target.value } : x))} className="input-field text-xs py-1" placeholder="URL" />
                  </div>
                  <button onClick={() => setLinks(links.filter(x => x.id !== l.id))} className="p-1 text-text-muted hover:text-danger transition-all"><Trash2 className="w-3.5 h-3.5" /></button>
                </motion.div>
              ))}
            </div>
          </Card>

          {/* Social Icons */}
          <Card>
            <SectionHeader title="Social Icons" />
            <div className="flex gap-2 flex-wrap">
              {SOCIAL_ICONS.map(s => (
                <button key={s.id} onClick={() => setActiveSocial(activeSocial.includes(s.id) ? activeSocial.filter(x => x !== s.id) : [...activeSocial, s.id])} className={cn("w-10 h-10 rounded-lg flex items-center justify-center border transition-all", activeSocial.includes(s.id) ? "border-accent/30 bg-accent/10" : "border-white/[0.06] bg-white/[0.02]")}>
                  <s.icon className="w-4 h-4" style={{ color: activeSocial.includes(s.id) ? s.color : "#94A3B8" }} />
                </button>
              ))}
            </div>
          </Card>

          {/* Settings */}
          <Card>
            <SectionHeader title="Settings" />
            <div className="space-y-3">
              <div><label className="label-field block mb-1.5">Custom Domain</label><input value={customDomain} onChange={(e) => setCustomDomain(e.target.value)} className="input-field" /></div>
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-xs text-text-secondary">Track analytics (clicks, views, conversions)</span>
                <button onClick={() => setTrackAnalytics(!trackAnalytics)} className={cn("w-9 h-5 rounded-full transition-all relative", trackAnalytics ? "bg-accent" : "bg-white/[0.08]")}>
                  <span className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: trackAnalytics ? "18px" : "2px" }} />
                </button>
              </label>
            </div>
          </Card>
        </div>

        {/* Live Preview */}
        <div className="lg:col-span-5">
          <div className="sticky top-4">
            <SectionHeader title="Live Preview" subtitle="Real-time" icon={<Smartphone className="w-4 h-4" />} />
            <div className="mx-auto w-[280px] h-[560px] rounded-[2.5rem] border-4 border-bg-surface bg-bg-surface p-3 shadow-3d">
              <div className="w-full h-full rounded-[2rem] overflow-y-auto" style={{ background: theme.bg, color: theme.text, fontFamily: font }}>
                <div className="p-5 flex flex-col items-center min-h-full">
                  {/* Avatar */}
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-accent to-info flex items-center justify-center text-3xl font-bold text-bg mb-3">P</div>
                  {/* Name */}
                  <div className="flex items-center gap-1 mb-1">
                    <span className="font-bold text-lg">{name}</span>
                    {verified && <span className="text-accent text-sm">✓</span>}
                  </div>
                  {/* Bio */}
                  <p className="text-xs text-center opacity-70 mb-4 max-w-[200px]">{bio}</p>
                  {/* Social icons */}
                  <div className="flex gap-2 mb-4">
                    {SOCIAL_ICONS.filter(s => activeSocial.includes(s.id)).map(s => (
                      <div key={s.id} className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: `${theme.text}15` }}>
                        <s.icon className="w-3.5 h-3.5" style={{ color: s.color }} />
                      </div>
                    ))}
                  </div>
                  {/* Links */}
                  <div className={cn("w-full space-y-2", layout === "Grid" && "grid grid-cols-2 gap-2")}>
                    {links.map(l => (
                      <motion.button key={l.id} whileTap={{ scale: 0.95 }} className={cn("w-full p-3 rounded-xl flex items-center gap-2 text-sm font-medium transition-all", layout === "Grid" && "flex-col text-center")} style={{ background: `${theme.text}10`, border: `1px solid ${theme.text}15` }}>
                        <span className="text-lg">{l.icon}</span>
                        <span className="truncate">{l.title}</span>
                      </motion.button>
                    ))}
                  </div>
                  <div className="mt-auto pt-4 text-[9px] opacity-40">Powered by CURV AI</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Metric label="Total Views" value={14500} format="compact" delta={18} icon={<Eye className="w-4 h-4" />} accent="info" />
            <Metric label="Total Clicks" value={3750} format="compact" delta={12} icon={<MousePointerClick className="w-4 h-4" />} accent="accent" />
            <Metric label="Avg CTR" value={25.9} suffix="%" delta={4} icon={<TrendingUp className="w-4 h-4" />} accent="success" />
            <Metric label="Top Link Clicks" value={1240} format="compact" delta={8} icon={<LinkIcon className="w-4 h-4" />} accent="accent" />
          </div>
          <Card>
            <SectionHeader title="Clicks by Link" />
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={CLICK_DATA} layout="vertical">
                  <XAxis type="number" tick={{ fill: "#94A3B8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} width={80} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="clicks" radius={[0, 4, 4, 0]}>
                    {CLICK_DATA.map((_, i) => <Cell key={i} fill={i === 0 ? "#FFD400" : "#3B82F6"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
        <div className="space-y-4">
          <Card>
            <SectionHeader title="Geographic Distribution" icon={<Globe className="w-4 h-4" />} />
            <div className="space-y-2">
              {[{ c: "United States", v: 45 }, { c: "United Kingdom", v: 18 }, { c: "India", v: 12 }, { c: "Canada", v: 10 }, { c: "Australia", v: 8 }, { c: "Others", v: 7 }].map(g => (
                <div key={g.c} className="flex items-center gap-2">
                  <span className="text-xs text-text-secondary w-24">{g.c}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-white/[0.04]"><div className="h-full rounded-full bg-gradient-to-r from-info to-accent" style={{ width: `${g.v}%` }} /></div>
                  <span className="font-mono text-[10px] text-text w-8 text-right">{g.v}%</span>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <SectionHeader title="Device Breakdown" icon={<Smartphone className="w-4 h-4" />} />
            <div className="space-y-2">
              <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><Smartphone className="w-3 h-3" />Mobile</span><span className="font-mono text-xs text-text">78%</span></div>
              <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><Monitor className="w-3 h-3" />Desktop</span><span className="font-mono text-xs text-text">19%</span></div>
              <div className="flex items-center justify-between"><span className="flex items-center gap-2 text-xs text-text-secondary"><Globe className="w-3 h-3" />Tablet</span><span className="font-mono text-xs text-text">3%</span></div>
            </div>
          </Card>
        </div>
      </div>

      {/* Link Performance Table */}
      <Card>
        <SectionHeader title="Link Performance" />
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-text-muted border-b border-white/[0.06]">
              <th className="py-2 px-3">Link</th><th className="py-2 px-3">Clicks</th><th className="py-2 px-3">CTR</th><th className="py-2 px-3">Conversions</th><th className="py-2 px-3">Trend</th>
            </tr></thead>
            <tbody>
              {links.map(l => (
                <tr key={l.id} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-all">
                  <td className="py-2 px-3"><span className="mr-2">{l.icon}</span><span className="text-text">{l.title}</span></td>
                  <td className="py-2 px-3 font-mono text-text">{l.clicks.toLocaleString()}</td>
                  <td className="py-2 px-3 font-mono text-success">{l.ctr}%</td>
                  <td className="py-2 px-3 font-mono text-text">{l.conversions}</td>
                  <td className="py-2 px-3"><Sparkline data={[10, 15, 12, 20, 18, 25]} width={50} height={16} color="#FFD400" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
