"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { DailyColumns, HBarChart, type BarDatum } from "@/components/charts";
import {
  ArrowRightIcon,
  BoltIcon,
  CoinsIcon,
  GaugeIcon,
  LayersIcon,
  ScissorsIcon,
  ShieldIcon,
  SparklesIcon,
  TerminalIcon,
  UploadIcon,
} from "@/components/icons";
import { parseExport, type Bucket, type TokenGuardExport } from "@/lib/export";
import { pct, tokens, usd } from "@/lib/format";
import { buildInsights, type InsightKind } from "@/lib/insights";
import { SAMPLE_EXPORT } from "@/lib/sample";

function bars(buckets: Bucket[], limit = 8): BarDatum[] {
  return buckets.slice(0, limit).map((b) => ({
    label: b.key,
    value: b.cost_usd,
    detail: [
      `${usd(b.cost_usd)}${b.unpriced_calls ? " (some calls unpriced)" : ""}`,
      `${b.calls.toLocaleString("en-US")} calls`,
      `${tokens(b.total_tokens)} tokens`,
      `${pct(b.cache_hit_rate)} cache hit`,
    ],
  }));
}

export function UsageDashboard() {
  const startWithSample = useSearchParams().get("sample") === "1";
  const [data, setData] = useState<TokenGuardExport | null>(startWithSample ? SAMPLE_EXPORT : null);
  const [isSample, setIsSample] = useState(startWithSample);
  const [error, setError] = useState<string | null>(null);

  async function loadFile(file: File | undefined) {
    if (!file) return;
    try {
      setData(parseExport(await file.text()));
      setIsSample(false);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function loadSample() {
    setData(SAMPLE_EXPORT);
    setIsSample(true);
    setError(null);
  }

  if (!data) return <Landing onFile={loadFile} onSample={loadSample} error={error} />;
  return <Dashboard data={data} isSample={isSample} onReset={() => setData(null)} />;
}

/* ------------------------------------------------------------------------- */
/* Landing: hero, upload, how it works                                        */
/* ------------------------------------------------------------------------- */

function Landing({
  onFile,
  onSample,
  error,
}: {
  onFile: (f: File | undefined) => void;
  onSample: () => void;
  error: string | null;
}) {
  return (
    <div className="space-y-20">
      <section className="grid items-center gap-12 pt-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <span className="eyebrow">
            <SparklesIcon className="size-4" />
            Token &amp; cost intelligence for AI coding teams
          </span>
          <h1 className="headline mt-6 text-5xl sm:text-6xl lg:text-7xl">
            Know what every <span className="text-gradient">AI token</span> costs your team.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-text-2">
            TokenGuard reads Claude Code and Codex session logs, prices every call, and shows where the spend goes:
            by model, project, day and tool. Then it helps you cut it.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button type="button" onClick={onSample} className="btn btn-primary">
              View live demo
              <ArrowRightIcon className="size-4" />
            </button>
            <a href="#upload" className="btn btn-ghost">
              <UploadIcon className="size-4" />
              Upload your export
            </a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <span className="inline-flex items-center gap-1.5">
              <ShieldIcon className="size-4 text-good" /> Runs in your browser
            </span>
            <span className="inline-flex items-center gap-1.5">
              <LayersIcon className="size-4 text-accent" /> Claude Code + Codex
            </span>
          </div>
        </div>
        <HeroVisual />
      </section>

      <UploadCard onFile={onFile} onSample={onSample} error={error} />

      <section>
        <div className="max-w-2xl">
          <span className="eyebrow">How it works</span>
          <h2 className="headline mt-4 text-3xl sm:text-4xl">From raw logs to savings in three steps</h2>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          <Step
            n={1}
            icon={<TerminalIcon />}
            title="Export"
            body="Run the TokenGuard CLI. It reads your agents' local session logs and prices every call."
          />
          <Step
            n={2}
            icon={<UploadIcon />}
            title="Drop the file here"
            body="The JSON is parsed in your browser. Nothing is uploaded to a server."
          />
          <Step
            n={3}
            icon={<ScissorsIcon />}
            title="Cut the waste"
            body="See which models, projects and tools cost the most, with concrete places to save."
          />
        </div>
      </section>
    </div>
  );
}

function HeroVisual() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[480px]" aria-hidden="true">
      <div className="orbit inset-0" />
      <div className="orbit inset-[14%]" />
      <div className="orbit inset-[30%] bg-[radial-gradient(circle,var(--accent-soft),transparent_70%)]" />
      <div className="absolute inset-[38%] grid place-items-center rounded-[28px] bg-gradient-to-br from-[#2d5bff] to-[#14b88a] shadow-[0_24px_60px_#2d5bff59]">
        <CoinsIcon className="size-1/2 text-white" />
      </div>
      <Chip className="left-0 top-[12%]" label="Spend, last 14 days" value="$395.00" />
      <Chip className="right-0 top-[30%]" label="Served from cache" value="94%" tone="good" />
      <Chip className="bottom-[14%] left-[4%]" label="Bash tool output" value="38% of context" />
      <Chip className="bottom-[2%] right-[8%]" label="Prompt reshaper" value="Same intent, fewer tokens" tone="good" />
    </div>
  );
}

function Chip({
  className,
  label,
  value,
  tone,
}: {
  className: string;
  label: string;
  value: string;
  tone?: "good";
}) {
  return (
    <div className={`float-chip card absolute px-4 py-3 ${className}`}>
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-lg font-bold tracking-tight ${tone === "good" ? "text-good" : "text-text"}`}>{value}</div>
    </div>
  );
}

function UploadCard({
  onFile,
  onSample,
  error,
}: {
  onFile: (f: File | undefined) => void;
  onSample: () => void;
  error: string | null;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <section id="upload" className="card grid scroll-mt-24 gap-8 p-6 sm:p-8 lg:grid-cols-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          onFile(e.dataTransfer.files[0]);
        }}
        className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? "border-accent bg-accent-soft" : "border-border bg-surface-2"
        }`}
      >
        <div className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent">
          <UploadIcon className="size-7" />
        </div>
        <p className="mt-4 font-semibold">
          Drop <code className="font-mono text-sm">tokenguard.json</code> here
        </p>
        <p className="mt-1 text-sm text-muted">Read in your browser, never uploaded.</p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <button type="button" onClick={() => inputRef.current?.click()} className="btn btn-primary">
            Choose file
          </button>
          <button type="button" onClick={onSample} className="btn btn-ghost">
            Use sample data
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      </div>
      <div className="flex min-w-0 flex-col justify-center">
        <h2 className="text-xl font-bold tracking-tight">Create your export</h2>
        <p className="mt-2 text-sm text-text-2">In PowerShell, from the repository folder:</p>
        <pre className="code-card mt-4 overflow-x-auto p-5 font-mono text-[13px] leading-relaxed">
          <span className="text-[#7aa2ff]">PS&gt;</span> cd Token_Graph\cli{"\n"}
          <span className="text-[#7aa2ff]">PS&gt;</span> .\.venv\Scripts\Activate.ps1{"\n"}
          <span className="text-[#7aa2ff]">PS&gt;</span> tokenguard export --since 30d -o tokenguard.json
        </pre>
        <p className="mt-4 text-sm text-muted">
          Reads Claude Code and Codex logs on your machine. Nothing is sent anywhere.
        </p>
      </div>
    </section>
  );
}

function Step({ n, icon, title, body }: { n: number; icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="card card-lift p-6">
      <div className="flex items-center justify-between">
        <div className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent">{icon}</div>
        <span className="text-4xl font-extrabold tracking-tighter text-border">0{n}</span>
      </div>
      <h3 className="mt-5 text-lg font-bold tracking-tight">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-text-2">{body}</p>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Dashboard                                                                   */
/* ------------------------------------------------------------------------- */

const INSIGHT_ICON: Record<InsightKind, React.ReactNode> = {
  tools: <ScissorsIcon />,
  model: <BoltIcon />,
  cache: <LayersIcon />,
  project: <CoinsIcon />,
};

function Dashboard({ data, isSample, onReset }: { data: TokenGuardExport; isSample: boolean; onReset: () => void }) {
  const t = data.total;
  const toolTotal = data.tools.reduce((acc, r) => acc + r.est_tokens, 0) || 1;
  const insights = buildInsights(data);
  const days = data.by_day.length;

  return (
    <div className="space-y-8">
      <section className="card relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-[radial-gradient(circle,var(--glow-1),transparent_70%)]" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <span className="eyebrow">{isSample ? "Live demo · fictional team" : "Your export"}</span>
            <h1 className="headline mt-4 text-4xl sm:text-5xl">Usage &amp; cost</h1>
            <p className="mt-3 text-sm text-text-2">
              {isSample ? "Sample data" : `Exported ${new Date(data.generated_at).toLocaleString()}`}
              {data.since ? ` · last ${data.since}` : " · all time"}
              {days > 0 && ` · ${days} active day${days === 1 ? "" : "s"}`}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/reshape" className="btn btn-ghost">
              <SparklesIcon className="size-4" />
              Reshape a prompt
            </Link>
            <button type="button" onClick={onReset} className="btn btn-primary">
              <UploadIcon className="size-4" />
              Load another file
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<CoinsIcon />} label="API-equivalent cost" value={usd(t.cost_usd)} hero />
        <Stat icon={<BoltIcon />} label="Model calls" value={t.calls.toLocaleString("en-US")} />
        <Stat icon={<LayersIcon />} label="Tokens processed" value={tokens(t.total_tokens)} />
        <Stat icon={<GaugeIcon />} label="Served from cache" value={pct(t.cache_hit_rate)} meter={t.cache_hit_rate} />
      </section>

      {insights.length > 0 && (
        <section>
          <div className="mb-4 flex items-center gap-2">
            <SparklesIcon className="size-5 text-accent" />
            <h2 className="text-lg font-bold tracking-tight">Where to save</h2>
          </div>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {insights.map((ins) => (
              <div key={ins.kind} className="card card-lift flex flex-col p-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
                    {INSIGHT_ICON[ins.kind]}
                  </div>
                  <span className="text-2xl font-extrabold tracking-tight">{ins.figure}</span>
                </div>
                <h3 className="mt-4 font-semibold">{ins.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-text-2">{ins.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {days > 1 && (
        <Panel title="Cost per day" subtitle="Hover a column for calls and tokens">
          <DailyColumns
            data={data.by_day.map((b) => ({
              label: b.key,
              value: b.cost_usd,
              detail: [usd(b.cost_usd), `${b.calls.toLocaleString("en-US")} calls`, `${tokens(b.total_tokens)} tokens`],
            }))}
            format={usd}
          />
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Cost by model">
          <HBarChart data={bars(data.by_model)} format={usd} />
        </Panel>
        <Panel title="Cost by project">
          <HBarChart data={bars(data.by_project)} format={usd} />
        </Panel>
      </div>

      <Panel
        title="Tool output fed back into context"
        subtitle="Large tool results are re-read on every later turn, so they are the best targets for trimming."
      >
        {data.tools.length === 0 ? (
          <p className="text-sm text-muted">No tool results in this export.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-2">
                  <th className="pb-3 pr-4 font-medium">Tool</th>
                  <th className="pb-3 pr-4 text-right font-medium">Results</th>
                  <th className="pb-3 pr-4 text-right font-medium">Est. tokens</th>
                  <th className="w-[34%] pb-3 pr-4 font-medium">Share of tool output</th>
                  <th className="pb-3 text-right font-medium">Largest</th>
                </tr>
              </thead>
              <tbody>
                {data.tools.slice(0, 10).map((r) => {
                  const share = r.est_tokens / toolTotal;
                  return (
                    <tr key={r.tool} className="border-b border-grid last:border-0">
                      <td className="py-3 pr-4 font-medium">{r.tool}</td>
                      <td className="py-3 pr-4 text-right tabular-nums">{r.results.toLocaleString("en-US")}</td>
                      <td className="py-3 pr-4 text-right tabular-nums">{tokens(r.est_tokens)}</td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 rounded-full bg-series-track">
                            <div className="h-2 rounded-full bg-series" style={{ width: `${share * 100}%` }} />
                          </div>
                          <span className="w-10 text-right tabular-nums text-text-2">{pct(share)}</span>
                        </div>
                      </td>
                      <td className="py-3 text-right tabular-nums">{tokens(r.largest_est_tokens)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Details by model">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-text-2">
                {["Model", "Calls", "Input", "Cache write", "Cache read", "Output", "Cache hit", "Cost"].map((h, i) => (
                  <th key={h} className={`pb-3 pr-4 font-medium ${i > 0 ? "text-right" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.by_model.map((b) => (
                <tr key={b.key} className="border-b border-grid last:border-0">
                  <td className="py-3 pr-4 font-medium">{b.key}</td>
                  {[
                    b.calls.toLocaleString("en-US"),
                    tokens(b.input_tokens),
                    tokens(b.cache_write_tokens),
                    tokens(b.cache_read_tokens),
                    tokens(b.output_tokens),
                    pct(b.cache_hit_rate),
                    `${usd(b.cost_usd)}${b.unpriced_calls ? " *" : ""}`,
                  ].map((cell, i) => (
                    <td key={i} className={`py-3 pr-4 text-right tabular-nums ${i === 6 ? "font-semibold" : ""}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <p className="text-xs text-muted">
        {t.unpriced_calls > 0 &&
          `* ${t.unpriced_calls} calls use models with no known price (${t.unpriced_models.join(", ")}) and count as $0. `}
        {data.note}
      </p>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  hero = false,
  meter,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hero?: boolean;
  meter?: number;
}) {
  return (
    <div className="card card-lift p-5">
      <div className="flex items-center gap-3">
        <div
          className={`grid size-10 shrink-0 place-items-center rounded-xl ${
            hero ? "bg-gradient-to-br from-[#2d5bff] to-[#14b88a] text-white" : "bg-accent-soft text-accent"
          }`}
        >
          {icon}
        </div>
        <div className="text-sm text-text-2">{label}</div>
      </div>
      <div className={`mt-4 font-extrabold tracking-tight ${hero ? "text-4xl" : "text-3xl"}`}>{value}</div>
      {meter !== undefined && (
        <div className="mt-3 h-1.5 rounded-full bg-series-track">
          <div className="h-1.5 rounded-full bg-series" style={{ width: `${Math.min(meter, 1) * 100}%` }} />
        </div>
      )}
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="card min-w-0 p-6">
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      <div className="mt-6">{children}</div>
    </section>
  );
}
