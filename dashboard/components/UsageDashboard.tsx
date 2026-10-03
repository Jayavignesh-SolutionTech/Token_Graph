"use client";

import { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { DailyColumns, HBarChart, type BarDatum } from "@/components/charts";
import { parseExport, type Bucket, type TokenGuardExport } from "@/lib/export";
import { pct, tokens, usd } from "@/lib/format";
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
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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

  if (!data) {
    return (
      <div className="space-y-6">
        <Intro />
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            loadFile(e.dataTransfer.files[0]);
          }}
          className={`rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            dragging ? "border-series bg-series-track" : "border-border bg-surface"
          }`}
        >
          <p className="text-text">Drop your <code className="font-mono text-sm">tokenguard.json</code> here</p>
          <p className="mt-1 text-sm text-muted">It is read in your browser and never uploaded.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Choose file
            </button>
            <button
              type="button"
              onClick={() => {
                setData(SAMPLE_EXPORT);
                setIsSample(true);
                setError(null);
              }}
              className="rounded-md border border-border px-4 py-2 text-sm text-text hover:bg-bg"
            >
              View sample data
            </button>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => loadFile(e.target.files?.[0])}
          />
          {error && <p className="mt-4 text-sm text-danger">{error}</p>}
        </div>
        <HowTo />
      </div>
    );
  }

  const t = data.total;
  const unpriced = data.total.unpriced_calls;
  const toolTotal = data.tools.reduce((acc, r) => acc + r.est_tokens, 0) || 1;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Usage &amp; cost</h1>
          <p className="mt-1 text-sm text-muted">
            {isSample ? "Sample data, fictional team" : `Exported ${new Date(data.generated_at).toLocaleString()}`}
            {data.since ? ` · last ${data.since}` : " · all time"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setData(null)}
          className="rounded-md border border-border px-3 py-1.5 text-sm text-text-2 hover:text-text"
        >
          Load another file
        </button>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="API-equivalent cost" value={usd(t.cost_usd)} hero />
        <Stat label="Model calls" value={t.calls.toLocaleString("en-US")} />
        <Stat label="Tokens processed" value={tokens(t.total_tokens)} />
        <Stat label="Served from cache" value={pct(t.cache_hit_rate)} hint="Share of input tokens read from cache" />
      </section>

      {data.by_day.length > 1 && (
        <Card title="Cost per day">
          <DailyColumns
            data={data.by_day.map((b) => ({
              label: b.key,
              value: b.cost_usd,
              detail: [usd(b.cost_usd), `${b.calls.toLocaleString("en-US")} calls`, `${tokens(b.total_tokens)} tokens`],
            }))}
            format={usd}
          />
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Cost by model">
          <HBarChart data={bars(data.by_model)} format={usd} />
        </Card>
        <Card title="Cost by project">
          <HBarChart data={bars(data.by_project)} format={usd} />
        </Card>
      </div>

      <Card
        title="Tool output fed back into context"
        subtitle="Large tool results are re-read on every later turn. These are the best targets for trimming."
      >
        {data.tools.length === 0 ? (
          <p className="text-sm text-muted">No tool results in this export.</p>
        ) : (
          <Table
            head={["Tool", "Results", "Est. tokens", "Share", "Largest result"]}
            rows={data.tools.slice(0, 10).map((r) => [
              r.tool,
              r.results.toLocaleString("en-US"),
              tokens(r.est_tokens),
              pct(r.est_tokens / toolTotal),
              tokens(r.largest_est_tokens),
            ])}
          />
        )}
      </Card>

      <Card title="Details by model">
        <Table
          head={["Model", "Calls", "Input", "Cache write", "Cache read", "Output", "Cache hit", "Cost"]}
          rows={data.by_model.map((b) => [
            b.key,
            b.calls.toLocaleString("en-US"),
            tokens(b.input_tokens),
            tokens(b.cache_write_tokens),
            tokens(b.cache_read_tokens),
            tokens(b.output_tokens),
            pct(b.cache_hit_rate),
            `${usd(b.cost_usd)}${b.unpriced_calls ? " *" : ""}`,
          ])}
        />
      </Card>

      <p className="text-xs text-muted">
        {unpriced > 0 &&
          `* ${unpriced} calls use models with no known price (${t.unpriced_models.join(", ")}) and count as $0. `}
        {data.note}
      </p>
    </div>
  );
}

function Intro() {
  return (
    <div>
      <h1 className="text-xl font-semibold">Usage &amp; cost</h1>
      <p className="mt-1 max-w-2xl text-sm text-text-2">
        See what your AI coding agents cost, by model, project and day, and which tools flood the context window.
      </p>
    </div>
  );
}

function HowTo() {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 text-sm">
      <h2 className="font-medium">Create your export (PowerShell)</h2>
      <pre className="mt-3 overflow-x-auto rounded-md bg-bg p-3 font-mono text-xs leading-relaxed text-text-2">
{`cd Token_Graph\\cli
.\\.venv\\Scripts\\Activate.ps1
tokenguard export --since 30d -o tokenguard.json`}
      </pre>
      <p className="mt-3 text-muted">Reads Claude Code and Codex logs on your machine. Nothing is sent anywhere.</p>
    </div>
  );
}

function Stat({ label, value, hint, hero = false }: { label: string; value: string; hint?: string; hero?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5" title={hint}>
      <div className="text-sm text-text-2">{label}</div>
      <div className={`mt-2 font-semibold tracking-tight ${hero ? "text-4xl" : "text-2xl"}`}>{value}</div>
    </div>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="min-w-0 rounded-xl border border-border bg-surface p-5">
      <h2 className="font-medium">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-2">
            {head.map((h, i) => (
              <th key={h} className={`pb-2 pr-4 font-medium ${i > 0 ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]} className="border-b border-grid last:border-0">
              {row.map((cell, i) => (
                <td key={i} className={`py-2 pr-4 ${i > 0 ? "text-right tabular-nums" : "text-text"}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
