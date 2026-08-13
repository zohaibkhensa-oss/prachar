"use client";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AudienceSpec } from "@/lib/schemas";

function ChipList({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  return (
    <div className="flex flex-wrap gap-2 items-center">
      {values.map((v, i) => (
        <span
          key={`${v}-${i}`}
          className="inline-flex items-center gap-1 border-2 border-white/[0.06] px-2 py-0.5 font-mono text-xs"
        >
          {v}
          <button
            type="button"
            onClick={() => onChange(values.filter((_, idx) => idx !== i))}
            className="text-text-muted hover:text-text"
          >
            x
          </button>
        </span>
      ))}
      <input
        className="bg-transparent font-mono text-xs outline-none border-b-2 border-white/[0.08] focus:border-white/[0.06] min-w-[120px] flex-1"
        placeholder={placeholder}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            const val = (e.target as HTMLInputElement).value.trim();
            if (val) {
              onChange([...values, val]);
              (e.target as HTMLInputElement).value = "";
            }
          }
        }}
      />
    </div>
  );
}

export function AudienceBuilder({
  value,
  onChange,
  networks,
}: {
  value: AudienceSpec;
  onChange: (v: AudienceSpec) => void;
  networks: string[];
}) {
  const set = <K extends keyof AudienceSpec>(k: K, v: AudienceSpec[K]) =>
    onChange({ ...value, [k]: v });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 border border-white/[0.06]">
      <div className="lg:col-span-2 p-6 space-y-5 border-b lg:border-b-0 lg:border-r border-white/[0.06]">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label>Geo</Label>
            <ChipList
              values={value.geo}
              onChange={(v) => set("geo", v)}
              placeholder="US, IN, GB…"
            />
          </div>
          <div>
            <Label>Languages</Label>
            <ChipList
              values={value.languages}
              onChange={(v) => set("languages", v)}
              placeholder="en, hi, es…"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label>Age range</Label>
            <div className="flex items-center gap-2 font-mono text-sm">
              <input
                type="number"
                className="w-20 input-ink px-2 py-1.5"
                value={value.age[0]}
                onChange={(e) => set("age", [Number(e.target.value), value.age[1]])}
              />
              <span>—</span>
              <input
                type="number"
                className="w-20 input-ink px-2 py-1.5"
                value={value.age[1]}
                onChange={(e) => set("age", [value.age[0], Number(e.target.value)])}
              />
            </div>
          </div>
          <div>
            <Label>Gender</Label>
            <div className="flex border border-white/[0.06]">
              {(["all", "male", "female"] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => set("gender", g)}
                  className={cn(
                    "flex-1 py-2 font-mono text-xs uppercase tracking-wider",
                    value.gender === g ? "bg-bg-surface text-text" : "bg-bg-card text-text hover:bg-white/[0.04]",
                  )}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div>
          <Label>Interests</Label>
          <ChipList
            values={value.interests}
            onChange={(v) => set("interests", v)}
            placeholder="coffee, running…"
          />
        </div>
        <div>
          <Label>Intents</Label>
          <ChipList
            values={value.intents}
            onChange={(v) => set("intents", v)}
            placeholder="buy, compare…"
          />
        </div>
        <div>
          <Label>Lookalike seed</Label>
          <Input
            value={value.lookalike_seed}
            onChange={(e) => set("lookalike_seed", e.target.value)}
            placeholder="@handle or customer list id"
          />
        </div>
      </div>
      <div className="p-6 bg-bg-surface text-text">
        <div className="font-mono text-xs uppercase tracking-wider text-text-secondary mb-4">
          NETWORK TRANSLATION
        </div>
        <div className="space-y-4 font-mono text-xs leading-relaxed">
          {networks.includes("meta") && (
            <div>
              <div className="text-accent uppercase tracking-wider mb-1">META</div>
              <div className="text-text/80">
                interests[{value.interests.join(", ")}] · age {value.age[0]}-{value.age[1]} ·
                geo[{value.geo.join(", ")}]
                {value.lookalike_seed && ` · lookalike(${value.lookalike_seed})`}
              </div>
            </div>
          )}
          {networks.includes("tiktok") && (
            <div>
              <div className="text-accent uppercase tracking-wider mb-1">TIKTOK</div>
              <div className="text-text/80">
                hashtag audiences[{value.interests.join(", ")}] · age {value.age[0]}-{value.age[1]}
                · geo[{value.geo.join(", ")}]
              </div>
            </div>
          )}
          {networks.includes("google") && (
            <div>
              <div className="text-accent uppercase tracking-wider mb-1">GOOGLE</div>
              <div className="text-text/80">
                keywords[{value.intents.join(", ")}] + in-market[{value.interests.join(", ")}] ·
                geo[{value.geo.join(", ")}]
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
