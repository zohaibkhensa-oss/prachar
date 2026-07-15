"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiPost, apiGet, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { VisibilityScoreHero } from "@/components/VisibilityScore";
import { Logo } from "@/components/Logo";
import type { AuditFindings, AuditJob } from "@/lib/schemas";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Phase = "idle" | "running" | "done" | "error";

export default function AuditPage() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<AuditFindings | null>(null);
  const [error, setError] = useState<string>("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  async function startAudit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setPhase("running");
    setLogs([`> initializing audit for ${query.trim()}`]);
    setResult(null);
    setError("");
    try {
      const job = await apiPost<AuditJob>("/brands/audit", { url: query.trim() });
      setJobId(job.id);
      streamJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        mockRun();
      } else {
        setPhase("error");
        setError(err instanceof Error ? err.message : "Audit failed to start");
      }
    }
  }

  function streamJob(id: string) {
    let es: EventSource | null = null;
    try {
      es = new EventSource(`${BASE}/audits/${id}/events`);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as Partial<AuditJob>;
          if (data.stage) setLogs((l) => [...l, `> ${data.stage}`]);
          if (data.logs) setLogs((l) => [...l, ...data.logs!.map((x) => `> ${x}`)]);
          if (data.status === "done" && data.result) {
            setResult(data.result);
            setPhase("done");
            es?.close();
          }
          if (data.status === "failed") {
            setPhase("error");
            setError("Audit failed");
            es?.close();
          }
        } catch {
          setLogs((l) => [...l, `> ${ev.data}`]);
        }
      };
      es.onerror = () => {
        es?.close();
        pollJob(id);
      };
    } catch {
      es?.close();
      pollJob(id);
    }
  }

  function pollJob(id: string) {
    const iv = setInterval(async () => {
      try {
        const job = await apiGet<AuditJob>(`/audits/${id}`);
        if (job.stage) setLogs((l) => (l[l.length - 1] === `> ${job.stage}` ? l : [...l, `> ${job.stage}`]));
        if (job.status === "done" && job.result) {
          setResult(job.result);
          setPhase("done");
          clearInterval(iv);
        } else if (job.status === "failed") {
          setPhase("error");
          setError("Audit failed");
          clearInterval(iv);
        }
      } catch {
        clearInterval(iv);
        mockRun();
      }
    }, 1000);
  }

  function mockRun() {
    const steps = [
      "crawling…",
      "extracting entities…",
      "checking Google positions…",
      "querying AI engines…",
      "computing visibility score…",
    ];
    let i = 0;
    const iv = setInterval(() => {
      if (i < steps.length) {
        setLogs((l) => [...l, `> ${steps[i]}`]);
        i++;
      } else {
        clearInterval(iv);
        setResult({
          brand_id: "demo",
          score: {
            brand_id: "demo",
            overall: 62,
            organic_rank_index: 58,
            ai_citation_rate: 41,
            social_reach_index: 70,
            paid_efficiency: 55,
            momentum: 48,
            week: new Date().toISOString().slice(0, 10),
            breakdown: {},
          },
          findings: [
            {
              title: "No AI-engine citations detected",
              impact: "high",
              effort: "medium",
              category: "ai",
              fix_description: "Add structured FAQ + entity-rich schema to homepage.",
              gated: false,
            },
            {
              title: "Google position dropping for 3 core terms",
              impact: "high",
              effort: "low",
              category: "organic",
              fix_description: "Refresh stale content; rebuild internal links.",
              gated: false,
            },
            {
              title: "Instagram reach flat for 4 weeks",
              impact: "medium",
              effort: "medium",
              category: "social",
              fix_description: "Rotate reels cadence; localize hooks per region.",
              gated: false,
            },
            {
              title: "Paid CPA 2.3x above target",
              impact: "high",
              effort: "low",
              category: "paid",
              fix_description: "Pause underperforming ad sets; reallocate budget.",
              gated: true,
            },
            {
              title: "Missing TikTok presence in SEA",
              impact: "medium",
              effort: "high",
              category: "social",
              fix_description: "Launch localized TikTok variants for ID, TH, VN.",
              gated: true,
            },
            {
              title: "No LinkedIn thought leadership",
              impact: "low",
              effort: "medium",
              category: "social",
              fix_description: "Weekly founder posts + employee amplification.",
              gated: true,
            },
          ],
        });
        setPhase("done");
      }
    }, 700);
  }

  const visibleFindings = result?.findings.slice(0, 5) ?? [];
  const gatedFindings = result?.findings.slice(5) ?? [];

  return (
    <main className="min-h-screen">
      <header className="border-b-3 border-ink bg-paper">
        <div className="container flex items-center justify-between py-4">
          <Link href="/" className="flex items-center">
            <Logo size="sm" />
          </Link>
          <Link href="/register" className="btn-ink px-4 py-2 text-xs">
            Sign up
          </Link>
        </div>
      </header>

      <section className="border-b-3 border-ink bg-paper">
        <div className="container py-16 text-center">
          <h1 className="font-display uppercase text-5xl sm:text-6xl tracking-wide leading-[0.9]">
            FREE VISIBILITY AUDIT
          </h1>
          <p className="mx-auto mt-4 max-w-xl font-body text-ink/70">
            Enter your website or @handle. We crawl, measure, and report in seconds.
          </p>
          <form onSubmit={startAudit} className="mx-auto mt-8 max-w-2xl flex gap-0">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="yoursite.com or @handle"
              className="border-r-0"
              disabled={phase === "running"}
            />
            <Button type="submit" variant="yellow" className="rounded-none" disabled={phase === "running"}>
              {phase === "running" ? "Auditing…" : "Audit →"}
            </Button>
          </form>
        </div>
      </section>

      {phase === "error" && (
        <section className="border-b-3 border-ink bg-paper">
          <div className="container py-8">
            <div className="border-3 border-ink bg-ink text-yellow p-4 font-mono text-sm">
              ERROR / {error}
            </div>
          </div>
        </section>
      )}

      {phase === "running" && (
        <section className="border-b-3 border-ink bg-ink text-paper">
          <div className="container py-8">
            <div className="font-mono text-xs uppercase tracking-wider text-paper/60 mb-3">
              LIVE PROGRESS / JOB {jobId ?? "—"}
            </div>
            <div
              ref={logRef}
              className="h-64 overflow-y-auto border-3 border-paper/20 p-4 font-mono text-sm text-paper/90 bg-ink"
            >
              {logs.map((l, i) => (
                <div key={i} className="whitespace-pre-wrap">
                  {l}
                </div>
              ))}
              <div className="text-yellow animate-pulse">_</div>
            </div>
          </div>
        </section>
      )}

      {phase === "done" && result && (
        <section className="border-b-3 border-ink bg-paper">
          <div className="container py-12 space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <VisibilityScoreHero score={result.score} />
              <div className="border-3 border-ink bg-paper p-6">
                <div className="font-mono text-xs uppercase tracking-wider text-ink/60 mb-4">
                  TOP FINDINGS
                </div>
                <div className="space-y-4">
                  {visibleFindings.map((f, i) => (
                    <div key={i} className="border-b-2 border-ink/10 pb-4 last:border-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={f.impact === "high" ? "yellow" : "ink"}>
                          {f.impact}
                        </Badge>
                        <span className="font-display uppercase text-sm tracking-wide">
                          {f.title}
                        </span>
                      </div>
                      <p className="font-body text-sm text-ink/70">{f.fix_description}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {gatedFindings.length > 0 && (
              <div className="relative border-3 border-ink bg-paper p-6 overflow-hidden">
                <div className="blur-sm select-none pointer-events-none space-y-4">
                  {gatedFindings.map((f, i) => (
                    <div key={i}>
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="ink">{f.impact}</Badge>
                        <span className="font-display uppercase text-sm tracking-wide">
                          {f.title}
                        </span>
                      </div>
                      <p className="font-body text-sm text-ink/70">{f.fix_description}</p>
                    </div>
                  ))}
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-paper/80">
                  <div className="font-display uppercase text-2xl tracking-wide text-center">
                    {gatedFindings.length} more findings
                  </div>
                  <Link href="/register" className="btn-yellow mt-4">
                    Fix these automatically — from ₹499/mo
                  </Link>
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
