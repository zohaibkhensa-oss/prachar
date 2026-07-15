"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { cn } from "@/lib/utils";
import { apiPost } from "@/lib/api";
import { BrandNav } from "@/components/BrandNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { AudienceBuilder } from "@/components/AudienceBuilder";
import { CreativeBoard } from "@/components/CreativeBoard";
import type { AudienceSpec, Campaign, CreativeAsset } from "@/lib/schemas";

const STEPS = [
  "Objective",
  "Audience",
  "Budget",
  "Networks",
  "Creatives",
  "Review",
  "Launch",
];

const OBJECTIVES = ["Awareness", "Traffic", "Conversions", "Leads", "App installs"];

const NETWORKS = [
  "meta",
  "tiktok",
  "google",
  "youtube",
  "instagram",
  "x",
  "linkedin",
  "pinterest",
  "snap",
  "reddit",
];

const REGIONS = ["Americas", "Europe", "India", "SEA", "MENA", "East Asia", "CIS"];

export default function NewCampaignPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [objective, setObjective] = useState("Awareness");
  const [audience, setAudience] = useState<AudienceSpec>({
    geo: [],
    age: [18, 34],
    gender: "all",
    interests: [],
    intents: [],
    languages: ["en"],
    lookalike_seed: "",
  });
  const [budget, setBudget] = useState(5000);
  const [networks, setNetworks] = useState<string[]>(["meta", "google"]);
  const [creatives, setCreatives] = useState<CreativeAsset[]>([]);
  const [generating, setGenerating] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [name, setName] = useState("");

  function toggleNetwork(n: string) {
    setNetworks((prev) =>
      prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n],
    );
  }

  async function generateCreatives() {
    setGenerating(true);
    await new Promise((r) => setTimeout(r, 1200));
    const made: CreativeAsset[] = networks.flatMap((net) =>
      REGIONS.slice(0, 2).map((r, i) => ({
        id: `${net}-${r}-${i}`,
        type: "copy" as const,
        locale: "en",
        channel: net,
        variant_group: `${net}-${r}`,
        policy_status: "approved" as const,
        copy: `${objective} campaign for ${name || "your brand"} — ${r} audience variant ${i + 1}.`,
        image_url: "",
        ctr: Math.round((1 + Math.random() * 4) * 100) / 100,
        is_winner: i === 0,
      })),
    );
    setCreatives(made);
    setGenerating(false);
  }

  async function launch() {
    setLaunching(true);
    try {
      const c = await apiPost<Campaign>(`/brands/${id}/campaigns`, {
        name: name || `${objective} campaign`,
        network: networks[0] ?? "meta",
        objective,
        budget,
        audience,
        networks,
      });
      router.push(`/app/brands/${id}/campaigns` as Route);
      void c;
    } catch {
      router.push(`/app/brands/${id}/campaigns` as Route);
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div>
      <BrandNav brandId={id} active="Campaigns" />
      <div className="p-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-display uppercase text-4xl tracking-wide">
            New campaign
          </h1>
          <Link href={`/app/brands/${id}/campaigns`} className="font-mono text-xs uppercase tracking-wider text-ink/60 hover:underline">
            Cancel
          </Link>
        </div>

        <div className="flex border-3 border-ink mb-8 overflow-x-auto">
          {STEPS.map((s, i) => (
            <button
              key={s}
              onClick={() => i < step && setStep(i)}
              className={cn(
                "px-4 py-2 font-mono text-xs uppercase tracking-wider whitespace-nowrap border-r-3 border-ink last:border-r-0",
                i === step ? "bg-yellow text-ink" : i < step ? "bg-ink text-paper" : "bg-paper text-ink/40",
              )}
            >
              {String(i + 1).padStart(2, "0")} · {s}
            </button>
          ))}
        </div>

        {step === 0 && (
          <Card>
            <Label>Campaign name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Spring launch" className="mb-6" />
            <Label>Objective</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-0 border-3 border-ink">
              {OBJECTIVES.map((o) => (
                <button
                  key={o}
                  onClick={() => setObjective(o)}
                  className={cn(
                    "px-4 py-3 font-mono text-xs uppercase tracking-wider border-b-3 border-r-3 border-ink last:border-r-0",
                    objective === o ? "bg-ink text-paper" : "bg-paper hover:bg-ink/10",
                  )}
                >
                  {o}
                </button>
              ))}
            </div>
            <div className="mt-8 flex justify-end">
              <Button variant="yellow" onClick={() => setStep(1)}>Next →</Button>
            </div>
          </Card>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <AudienceBuilder value={audience} onChange={setAudience} networks={networks} />
            <div className="flex justify-between">
              <Button variant="paper" onClick={() => setStep(0)}>← Back</Button>
              <Button variant="yellow" onClick={() => setStep(2)}>Next →</Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <Card>
            <Label>Monthly budget</Label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={500}
                max={100000}
                step={500}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="flex-1 accent-yellow"
              />
              <span className="font-display text-3xl tabular-nums">₹{budget.toLocaleString()}</span>
            </div>
            <div className="mt-8 flex justify-between">
              <Button variant="paper" onClick={() => setStep(1)}>← Back</Button>
              <Button variant="yellow" onClick={() => setStep(3)}>Next →</Button>
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <Label>Networks</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-0 border-3 border-ink">
              {NETWORKS.map((n) => (
                <button
                  key={n}
                  onClick={() => toggleNetwork(n)}
                  className={cn(
                    "px-3 py-3 font-mono text-xs uppercase tracking-wider border-b-3 border-r-3 border-ink",
                    networks.includes(n) ? "bg-yellow text-ink" : "bg-paper hover:bg-ink/10",
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
            <div className="mt-8 flex justify-between">
              <Button variant="paper" onClick={() => setStep(2)}>← Back</Button>
              <Button variant="yellow" onClick={() => setStep(4)}>Next →</Button>
            </div>
          </Card>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-wider text-ink/60">
                AI-generated creatives · {networks.length} networks
              </span>
              <Button variant="yellow" size="sm" onClick={generateCreatives} disabled={generating}>
                {generating ? "Generating…" : "Generate"}
              </Button>
            </div>
            {creatives.length > 0 ? (
              <CreativeBoard creatives={creatives} />
            ) : (
              <Card className="text-center">
                <p className="font-mono text-xs uppercase tracking-wider text-ink/60">
                  Click Generate to create ad variants.
                </p>
              </Card>
            )}
            <div className="flex justify-between">
              <Button variant="paper" onClick={() => setStep(3)}>← Back</Button>
              <Button variant="yellow" onClick={() => setStep(5)} disabled={creatives.length === 0}>Next →</Button>
            </div>
          </div>
        )}

        {step === 5 && (
          <Card>
            <h2 className="font-display uppercase text-2xl tracking-wide mb-6">Review</h2>
            <div className="space-y-3 font-mono text-sm">
              <Row label="Name" value={name || `${objective} campaign`} />
              <Row label="Objective" value={objective} />
              <Row label="Budget" value={`₹${budget.toLocaleString()}/mo`} />
              <Row label="Networks" value={networks.join(", ")} />
              <Row label="Geo" value={audience.geo.join(", ") || "—"} />
              <Row label="Interests" value={audience.interests.join(", ") || "—"} />
              <Row label="Creatives" value={`${creatives.length} variants`} />
            </div>
            <div className="mt-8 flex justify-between">
              <Button variant="paper" onClick={() => setStep(4)}>← Back</Button>
              <Button variant="yellow" onClick={() => setStep(6)}>Next →</Button>
            </div>
          </Card>
        )}

        {step === 6 && (
          <Card className="text-center">
            <h2 className="font-display uppercase text-3xl tracking-wide mb-4">Ready to launch</h2>
            <p className="font-mono text-xs uppercase tracking-wider text-ink/60 mb-6">
              {creatives.length} creatives · {networks.length} networks · ₹{budget.toLocaleString()}/mo
            </p>
            <div className="flex justify-center gap-4">
              <Button variant="paper" onClick={() => setStep(5)}>← Back</Button>
              <Button variant="yellow" onClick={launch} disabled={launching}>
                {launching ? "Launching…" : "Launch campaign →"}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b-2 border-ink/10 pb-2">
      <span className="uppercase tracking-wider text-ink/60 text-xs">{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}
