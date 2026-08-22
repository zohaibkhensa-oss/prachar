"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card3D, Card } from "@/components/ui/card-3d";
import { Metric } from "@/components/ui/metric";
import { AIRecommendation } from "@/components/ui/ai-blocks";
import { Sparkline, ProgressBar } from "@/components/ui/charts";
import { SectionHeader } from "@/components/ui/empty-state";
import {
  ShoppingBag, Package, Wand2, Plus, Check, Zap, TrendingUp,
  DollarSign, Eye, MousePointerClick, ShoppingCart, RefreshCw,
  Sparkles, Settings, AlertTriangle, Play,
} from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

const PRODUCTS = [
  { id: 1, name: "Cold Brew Concentrate", price: 24, category: "Beverages", stock: "in", posts: 12, views: 12400, clicks: 890, sales: 145, gradient: "from-info/20 to-accent/10", autopilot: true },
  { id: 2, name: "Signature Blend Beans", price: 18, category: "Beans", stock: "in", posts: 8, views: 8900, clicks: 670, sales: 89, gradient: "from-accent/20 to-success/10", autopilot: true },
  { id: 3, name: "Espresso Roast Dark", price: 22, category: "Beans", stock: "low", posts: 6, views: 6700, clicks: 450, sales: 56, gradient: "from-success/20 to-info/10", autopilot: false },
  { id: 4, name: "Vanilla Cold Brew", price: 26, category: "Beverages", stock: "in", posts: 10, views: 9800, clicks: 720, sales: 98, gradient: "from-warning/20 to-danger/10", autopilot: true },
  { id: 5, name: "Ceramic Mug Set", price: 34, category: "Merchandise", stock: "in", posts: 4, views: 3200, clicks: 210, sales: 23, gradient: "from-danger/20 to-info/10", autopilot: false },
  { id: 6, name: "Pour Over Kit", price: 45, category: "Equipment", stock: "out", posts: 3, views: 2100, clicks: 180, sales: 0, gradient: "from-info/20 to-warning/10", autopilot: false },
  { id: 7, name: "Decaf House Blend", price: 16, category: "Beans", stock: "in", posts: 5, views: 4500, clicks: 320, sales: 34, gradient: "from-accent/20 to-info/10", autopilot: false },
  { id: 8, name: "Holiday Gift Box", price: 65, category: "Gifts", stock: "in", posts: 15, views: 18500, clicks: 1400, sales: 178, gradient: "from-success/20 to-accent/10", autopilot: true },
];

const RULES = [
  { id: 1, condition: "New product added", action: "Generate Instagram post + Facebook post", active: true },
  { id: 2, condition: "Product on sale", action: "Launch Google Shopping ad + Email campaign", active: true },
  { id: 3, condition: "Low stock alert", action: "Create urgency post (Instagram Story)", active: true },
  { id: 4, condition: "Back in stock", action: "Generate announcement post (all platforms)", active: false },
  { id: 5, condition: "Trending product", action: "Boost with paid ad campaign", active: true },
];

const REVENUE_DATA = PRODUCTS.slice(0, 6).map(p => ({ name: p.name.slice(0, 12), revenue: p.sales * p.price }));
const FUNNEL_DATA = [
  { stage: "Views", value: 12400, pct: 100, icon: Eye, color: "#3B82F6" },
  { stage: "Clicks", value: 890, pct: 7.2, icon: MousePointerClick, color: "#FFD400" },
  { stage: "Add to Cart", value: 320, pct: 2.6, icon: ShoppingCart, color: "#F97316" },
  { stage: "Purchases", value: 145, pct: 1.2, icon: DollarSign, color: "#22C55E" },
];

const VIEWS_SALES = Array.from({ length: 30 }, (_, i) => ({
  day: i + 1,
  views: 200 + Math.sin(i / 3) * 80 + i * 5,
  sales: 5 + Math.cos(i / 4) * 3 + i * 0.3,
}));

const AI_CONTENT = {
  instagram: "☕ Start your morning right with our premium Cold Brew Concentrate. Smooth, bold, and ready in seconds. Link in bio! #CoffeeLovers #ColdBrew #MorningRoutine",
  facebook: "Introducing our Cold Brew Concentrate — the perfect balance of bold and smooth. Made with 100% ethically sourced beans. Order now and get free shipping! 🚚",
  tiktok: "POV: You just discovered the best cold brew ever 🤤 Pour over ice, add milk, and your morning is transformed! #CoffeeTok #ColdBrew #MorningVibes",
  google: "Premium Cold Brew Concentrate | Prachar Coffee — Smooth & bold cold brew made from ethically sourced beans. $24. Free shipping on orders $35+.",
};

export default function ShopPage() {
  const [connected, setConnected] = useState(true);
  const [selectedProduct, setSelectedProduct] = useState(PRODUCTS[0]!);
  const [showAIContent, setShowAIContent] = useState(false);
  const [rules, setRules] = useState(RULES);
  const [aiContent, setAiContent] = useState<Record<string, string>>(AI_CONTENT);
  const [generatingContent, setGeneratingContent] = useState(false);

  async function generateContent() {
    setGeneratingContent(true);
    setShowAIContent(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const { authedFetch } = await import("@/lib/auth");
      const res = await authedFetch(`${apiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: [{
            role: "user",
            content: `You are an AI advertising copywriter for CURV AI. Generate social media content for the product "${selectedProduct.name}" ($${selectedProduct.price}, category: ${selectedProduct.category}). Generate 4 posts in this exact format:\n\nINSTAGRAM: [engaging caption with emojis and hashtags]\n\nFACEBOOK: [detailed post with CTA]\n\nTIKTOK: [short punchy script with trending hashtags]\n\nGOOGLE: [concise shopping ad copy with price]\n\nKeep each platform's style appropriate for its format.`,
          }],
        }),
        signal: AbortSignal.timeout(20000),
      });
      if (res.ok) {
        const data = await res.json() as { reply: string };
        // Parse the LLM response into platform sections
        const reply = data.reply;
        const parsed: Record<string, string> = {};
        const platforms = ["instagram", "facebook", "tiktok", "google"];
        platforms.forEach(p => {
          const regex = new RegExp(`${p.toUpperCase()}:\\s*(.+?)(?=\\n\\n(?:INSTAGRAM|FACEBOOK|TIKTOK|GOOGLE):|$)`, "is");
          const match = reply.match(regex);
          parsed[p] = match?.[1] ? match[1].trim() : (AI_CONTENT as Record<string, string>)[p] ?? "";
        });
        setAiContent(Object.keys(parsed).length > 0 ? parsed : AI_CONTENT);
      }
    } catch {
      setAiContent(AI_CONTENT);
    }
    setGeneratingContent(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-text">E-Commerce Integration</h1>
          <p className="text-sm text-text-secondary mt-1">Auto-generate ads from your product catalog</p>
        </div>
        <span className="badge badge-accent"><Sparkles className="w-3 h-3" /> AI-Powered</span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric label="Products Synced" value={124} delta={8} icon={<Package className="w-4 h-4" />} accent="info" />
        <Metric label="Auto-Generated Posts" value={342} delta={45} icon={<Wand2 className="w-4 h-4" />} accent="accent" />
        <Metric label="Product Revenue" value={89000} format="compact" prefix="$" delta={22} icon={<DollarSign className="w-4 h-4" />} accent="success" />
        <Metric label="Conversion Rate" value={3.2} suffix="%" delta={0.8} icon={<TrendingUp className="w-4 h-4" />} accent="accent" />
      </div>

      {/* Store Connection */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-success/20 to-accent/10 flex items-center justify-center"><ShoppingBag className="w-6 h-6 text-success" /></div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display text-sm font-medium text-text">Shopify Store</span>
                <span className={cn("badge text-[9px]", connected ? "badge-success" : "badge-neutral")}>{connected ? "Connected" : "Not Connected"}</span>
              </div>
              <div className="text-xs text-text-muted">prachar-coffee.myshopify.com · 124 products · Last sync: 5 min ago</div>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-secondary text-xs"><RefreshCw className="w-3 h-3 inline mr-1" />Sync Now</button>
            <button className="btn-secondary text-xs"><Settings className="w-3 h-3 inline mr-1" />Settings</button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Product Catalog */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <SectionHeader title="Product Catalog" subtitle={`${PRODUCTS.length} products`} icon={<Package className="w-4 h-4" />} />
              <div className="flex gap-2">
                <button className="btn-secondary text-xs"><Wand2 className="w-3 h-3 inline mr-1" />Generate for All</button>
                <button className="btn-primary text-xs"><Plus className="w-3 h-3 inline mr-1" />Add Product</button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {PRODUCTS.map((p, i) => (
                <motion.div key={p.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.04 }}>
                  <Card3D className="overflow-hidden p-0">
                    <div className={cn("aspect-square bg-gradient-to-br flex items-center justify-center", p.gradient)}>
                      <Package className="w-8 h-8 text-white/30" />
                      <span className={cn("absolute top-2 right-2 badge text-[8px]", p.stock === "in" ? "badge-success" : p.stock === "low" ? "badge-warning" : "badge-danger")}>{p.stock === "in" ? "In Stock" : p.stock === "low" ? "Low" : "Out"}</span>
                    </div>
                    <div className="p-2.5">
                      <h4 className="text-xs font-medium text-text truncate mb-1">{p.name}</h4>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-xs text-accent">${p.price}</span>
                        <span className="text-[9px] text-text-muted">{p.posts} posts</span>
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-center mb-2">
                        <div><div className="font-mono text-[10px] text-text">{(p.views / 1000).toFixed(1)}K</div><div className="text-[7px] text-text-muted">views</div></div>
                        <div><div className="font-mono text-[10px] text-text">{p.clicks}</div><div className="text-[7px] text-text-muted">clicks</div></div>
                        <div><div className="font-mono text-[10px] text-success">{p.sales}</div><div className="text-[7px] text-text-muted">sales</div></div>
                      </div>
                      <div className="flex items-center justify-between">
                        <button onClick={() => { setSelectedProduct(p); setShowAIContent(true); }} className="btn-secondary text-[10px] px-2 py-1 flex-1 mr-1"><Wand2 className="w-2.5 h-2.5 inline" />Posts</button>
                        <label className="flex items-center cursor-pointer">
                          <input type="checkbox" checked={p.autopilot} onChange={() => {}} className="accent-accent w-3 h-3" title="Auto-Pilot" />
                        </label>
                      </div>
                    </div>
                  </Card3D>
                </motion.div>
              ))}
            </div>
          </Card>

          {/* Auto-Post Rules */}
          <Card>
            <SectionHeader title="Auto-Post Rules" subtitle="Automate content generation" icon={<Zap className="w-4 h-4" />} />
            <div className="space-y-2">
              {rules.map(r => (
                <div key={r.id} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-text-secondary">When</span>
                      <span className="badge badge-info text-[9px]">{r.condition}</span>
                      <span className="text-text-secondary">→</span>
                      <span className="text-text">{r.action}</span>
                    </div>
                  </div>
                  <button onClick={() => setRules(rules.map(x => x.id === r.id ? { ...x, active: !x.active } : x))} className={cn("w-9 h-5 rounded-full transition-all relative", r.active ? "bg-accent" : "bg-white/[0.08]")}>
                    <span className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: r.active ? "18px" : "2px" }} />
                  </button>
                </div>
              ))}
              <button className="btn-secondary text-xs w-full"><Plus className="w-3 h-3 inline mr-1" />Create Rule</button>
            </div>
          </Card>

          {/* Performance */}
          <Card>
            <SectionHeader title="Product Performance" icon={<TrendingUp className="w-4 h-4" />} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-text-secondary mb-2">Top Products by Revenue</div>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={REVENUE_DATA} layout="vertical">
                      <XAxis type="number" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="name" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} width={70} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                      <Bar dataKey="revenue" fill="#FFD400" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div>
                <div className="text-xs text-text-secondary mb-2">Views vs Sales (30 days)</div>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={VIEWS_SALES}>
                      <XAxis dataKey="day" tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#94A3B8", fontSize: 9 }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, fontSize: 11 }} />
                      <Line type="monotone" dataKey="views" stroke="#3B82F6" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="sales" stroke="#22C55E" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
            {/* Funnel */}
            <div className="mt-4">
              <div className="text-xs text-text-secondary mb-2">Conversion Funnel</div>
              <div className="space-y-2">
                {FUNNEL_DATA.map(f => (
                  <div key={f.stage} className="flex items-center gap-3">
                    <f.icon className="w-4 h-4 shrink-0" style={{ color: f.color }} />
                    <span className="text-xs text-text w-24">{f.stage}</span>
                    <div className="flex-1 h-6 rounded-md bg-white/[0.04] overflow-hidden">
                      <div className="h-full rounded-md flex items-center px-2" style={{ width: `${f.pct}%`, background: `${f.color}30`, borderLeft: `2px solid ${f.color}` }}>
                        <span className="font-mono text-[10px] text-text">{f.value.toLocaleString()}</span>
                      </div>
                    </div>
                    <span className="font-mono text-xs text-text-muted w-12 text-right">{f.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* AI Product-to-Post */}
          <Card3D glow>
            <SectionHeader title="AI Product-to-Post" subtitle="Generate content from products" icon={<Wand2 className="w-4 h-4" />} />
            <select value={selectedProduct.id} onChange={(e) => { setSelectedProduct(PRODUCTS.find(p => p.id === Number(e.target.value))!); setShowAIContent(false); }} className="input-field mb-3">
              {PRODUCTS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <button onClick={generateContent} disabled={generatingContent} className="btn-primary text-xs w-full mb-3 disabled:opacity-50">
              {generatingContent ? <><span className="ai-dots" /> Generating...</> : <><Wand2 className="w-3 h-3 inline mr-1" />Generate Content</>}
            </button>
            {showAIContent && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
                {Object.entries(aiContent).map(([platform, content]) => (
                  <div key={platform} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-medium capitalize text-accent">{platform}</span>
                      <span className="badge badge-success text-[8px]">92% AI</span>
                    </div>
                    <p className="text-[10px] text-text-secondary leading-relaxed mb-2">{content}</p>
                    <div className="flex gap-1">
                      <button className="btn-secondary text-[9px] px-2 py-0.5 flex-1">Edit</button>
                      <button className="btn-primary text-[9px] px-2 py-0.5 flex-1">Publish</button>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </Card3D>

          {/* Shopping Ads */}
          <Card>
            <SectionHeader title="Shopping Ads" subtitle="Google Shopping campaigns" icon={<DollarSign className="w-4 h-4" />} />
            <div className="space-y-2">
              {[
                { name: "Cold Brew Campaign", products: 8, spend: 1200, roas: 4.2, conv: 89 },
                { name: "Beans Promotion", products: 5, spend: 800, roas: 3.1, conv: 45 },
                { name: "Gift Box Holiday", products: 3, spend: 2400, roas: 5.8, conv: 178 },
              ].map(c => (
                <div key={c.name} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="text-xs font-medium text-text mb-1">{c.name}</div>
                  <div className="grid grid-cols-4 gap-1 text-[10px]">
                    <div><span className="text-text-muted">Spend</span> <span className="font-mono text-text">${c.spend}</span></div>
                    <div><span className="text-text-muted">ROAS</span> <span className="font-mono text-success">{c.roas}x</span></div>
                    <div><span className="text-text-muted">Conv</span> <span className="font-mono text-text">{c.conv}</span></div>
                    <div><span className="text-text-muted">Items</span> <span className="font-mono text-text">{c.products}</span></div>
                  </div>
                </div>
              ))}
              <button className="btn-secondary text-xs w-full"><Plus className="w-3 h-3 inline mr-1" />Create Shopping Campaign</button>
            </div>
            <div className="mt-3 p-2.5 rounded-lg bg-success/5 border border-success/10 flex items-center gap-2">
              <Check className="w-3.5 h-3.5 text-success" />
              <span className="text-[10px] text-success">Product feed synced · 0 errors</span>
            </div>
          </Card>

          {/* AI Insights */}
          <div className="space-y-2">
            <AIRecommendation title="Best Seller Opportunity" reasoning="Holiday Gift Box is your top performer with 5.8x ROAS. Consider increasing ad spend by 30%." />
            <AIRecommendation title="Restock Alert" reasoning="Pour Over Kit is out of stock but still getting views. Restock to capture lost sales." />
          </div>
        </div>
      </div>
    </div>
  );
}
