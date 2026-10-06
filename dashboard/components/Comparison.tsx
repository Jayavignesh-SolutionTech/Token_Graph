"use client";

import { useState } from "react";
import Link from "next/link";
import { BoltIcon, CoinsIcon, LayersIcon, ShieldIcon, SparklesIcon, UploadIcon } from "@/components/icons";
import { INPUT_PRICES, type BenchResult } from "@/lib/bench";
import { pct, tokens, usd } from "@/lib/format";

const WORKDAYS_PER_MONTH = 21;

export function Comparison({ data, isSample, onReset }: { data: BenchResult; isSample: boolean; onReset: () => void }) {
  const t = data.totals;
  const n = Math.max(t.questions, 1);
  const avgWithout = t.without_tokens / n;
  const avgWith = t.with_tokens / n;
  const ratio = t.ratio ?? (avgWith ? avgWithout / avgWith : 0);
  const files = Object.values(data.graph.files).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-8">
      <section className="card relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-[radial-gradient(circle,var(--glow-1),transparent_70%)]" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <span className="eyebrow">{isSample ? "Live demo · open-source Flask repo" : "Your benchmark"}</span>
            <h1 className="headline mt-4 text-4xl sm:text-5xl">
              With vs without <span className="text-gradient">TokenGuard</span>
            </h1>
            <p className="mt-3 text-sm text-text-2">
              {data.repo} · {t.questions} questions · {new Date(data.generated_at).toLocaleDateString()}
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

      {/* Headline comparison */}
      <section className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <div className="card p-6 sm:p-8">
          <h2 className="text-lg font-bold tracking-tight">Tokens the AI reads per question</h2>
          <p className="mt-1 text-sm text-muted">Average over {t.questions} questions about this codebase</p>
          <div className="mt-8 space-y-6">
            <BigBar
              label="Without TokenGuard"
              hint="search the repo, then read the matching files"
              value={avgWithout}
              max={avgWithout}
              muted
            />
            <BigBar
              label="With TokenGuard"
              hint="ask the code map, read only what it returns"
              value={avgWith}
              max={avgWithout}
            />
          </div>
        </div>
        <div className="card flex flex-col justify-center bg-gradient-to-br from-[#2d5bff] to-[#14b88a] p-8 text-white">
          <div className="text-sm font-medium text-white/80">Saved on every question</div>
          <div className="headline mt-2 text-7xl">{pct(t.saved_pct)}</div>
          <div className="mt-2 text-lg font-semibold">{ratio ? `${ratio.toFixed(1)}× fewer tokens` : ""}</div>
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-white/25 pt-5 text-sm">
            <div>
              <div className="text-white/75">Answer found</div>
              <div className="text-xl font-bold">
                {t.with_found}/{t.judged} <span className="text-sm font-medium text-white/75">with</span>
              </div>
              <div className="text-white/75">
                {t.without_found}/{t.judged} without
              </div>
            </div>
            <div>
              <div className="text-white/75">Cost to build the map</div>
              <div className="text-xl font-bold">{data.graph.build_llm_tokens} LLM tokens</div>
              <div className="text-white/75">{data.graph.scan_seconds}s local scan</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<LayersIcon />} label="Files mapped" value={files.toLocaleString("en-US")} />
        <Stat icon={<BoltIcon />} label="Relationships" value={data.graph.edges.toLocaleString("en-US")} />
        <Stat icon={<CoinsIcon />} label="Tokens saved in this run" value={tokens(t.saved_tokens)} />
        <Stat icon={<ShieldIcon />} label="Whole codebase" value={`${tokens(data.graph.source_tokens)} tokens`} />
      </section>

      <SavingsCalculator avgWithout={avgWithout} avgWith={avgWith} />

      <section className="card min-w-0 p-6">
        <h2 className="text-lg font-bold tracking-tight">Question by question</h2>
        <p className="mt-1 text-sm text-muted">
          ✓ means the answer included the code that was asked about.
        </p>
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-text-2">
                <th className="pb-3 pr-4 font-medium">Question</th>
                <th className="pb-3 pr-4 text-right font-medium">Without</th>
                <th className="pb-3 pr-4 text-right font-medium">With</th>
                <th className="w-[26%] pb-3 pr-4 font-medium">Tokens read</th>
                <th className="pb-3 text-right font-medium">Saved</th>
              </tr>
            </thead>
            <tbody>
              {data.questions.map((q, i) => {
                const max = Math.max(q.without_tokens, q.with_tokens, 1);
                return (
                  <tr key={i} className="border-b border-grid align-middle last:border-0">
                    <td className="py-3 pr-4">{q.question}</td>
                    <td className="py-3 pr-4 text-right tabular-nums text-text-2">
                      {q.without_tokens.toLocaleString("en-US")}
                      <Found value={q.without_found} />
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums font-medium">
                      {q.with_tokens.toLocaleString("en-US")}
                      <Found value={q.with_found} />
                    </td>
                    <td className="py-3 pr-4">
                      <div className="space-y-1">
                        <div className="h-1.5 rounded-full bg-muted/40" style={{ width: `${(q.without_tokens / max) * 100}%` }} />
                        <div className="h-1.5 rounded-full bg-series" style={{ width: `${Math.max((q.with_tokens / max) * 100, 1)}%` }} />
                      </div>
                    </td>
                    <td className="py-3 text-right font-semibold tabular-nums text-good">{pct(q.saved_pct)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex gap-5 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-full bg-muted/40" /> Without
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-full bg-series" /> With TokenGuard
          </span>
        </div>
      </section>

      <section className="card p-6">
        <h2 className="text-lg font-bold tracking-tight">How this was measured</h2>
        <dl className="mt-4 grid gap-4 text-sm md:grid-cols-3">
          <div>
            <dt className="font-semibold">Without TokenGuard</dt>
            <dd className="mt-1 text-text-2">{capitalize(data.method.without)}.</dd>
          </div>
          <div>
            <dt className="font-semibold">With TokenGuard</dt>
            <dd className="mt-1 text-text-2">{capitalize(data.method.with)}.</dd>
          </div>
          <div>
            <dt className="font-semibold">Counting</dt>
            <dd className="mt-1 text-text-2">
              Tokens {data.method.tokens}. The map is built by local parsing, so building it costs no LLM tokens.
              Results depend on the codebase and the questions.
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function SavingsCalculator({ avgWithout, avgWith }: { avgWithout: number; avgWith: number }) {
  const [model, setModel] = useState(INPUT_PRICES[0].id);
  const [devs, setDevs] = useState(5);
  const [perDay, setPerDay] = useState(20);
  const price = INPUT_PRICES.find((p) => p.id === model) ?? INPUT_PRICES[0];
  const questions = devs * perDay * WORKDAYS_PER_MONTH;
  const without = (avgWithout * questions * price.perMTok) / 1_000_000;
  const withMap = (avgWith * questions * price.perMTok) / 1_000_000;

  return (
    <section className="card p-6 sm:p-8">
      <div className="flex items-center gap-2">
        <CoinsIcon className="size-5 text-accent" />
        <h2 className="text-lg font-bold tracking-tight">What this means for your team</h2>
      </div>
      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-5">
          <label className="block text-sm">
            <span className="font-medium">Model</span>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="mt-2 w-full rounded-xl border border-border bg-surface px-3 py-2.5 outline-none focus:border-accent"
            >
              {INPUT_PRICES.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} (${p.perMTok} / M input tokens)
                </option>
              ))}
            </select>
          </label>
          <Slider label="Developers" value={devs} min={1} max={200} onChange={setDevs} />
          <Slider label="Codebase questions per developer per day" value={perDay} min={1} max={200} onChange={setPerDay} />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Money label="Without TokenGuard" value={without} sub="per month" />
          <Money label="With TokenGuard" value={withMap} sub="per month" />
          <Money label="You save" value={without - withMap} sub={`${(questions * 12).toLocaleString("en-US")} questions / year`} accent />
        </div>
      </div>
      <p className="mt-6 text-xs text-muted">
        Context tokens priced at list input rates, {WORKDAYS_PER_MONTH} workdays a month. Prompt caching lowers both
        sides; the share saved stays similar.
      </p>
    </section>
  );
}

function Slider({ label, value, min, max, onChange }: {
  label: string; value: number; min: number; max: number; onChange: (v: number) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="flex justify-between font-medium">
        {label}
        <span className="tabular-nums text-accent">{value}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-3 w-full accent-[var(--accent)]"
      />
    </label>
  );
}

function Money({ label, value, sub, accent = false }: { label: string; value: number; sub: string; accent?: boolean }) {
  return (
    <div className={`rounded-2xl border p-5 ${accent ? "border-good/40 bg-good/10" : "border-border bg-surface-2"}`}>
      <div className="text-sm text-text-2">{label}</div>
      <div className={`mt-2 text-3xl font-extrabold tracking-tight ${accent ? "text-good" : ""}`}>{usd(value)}</div>
      <div className="mt-1 text-xs text-muted">{sub}</div>
    </div>
  );
}

function BigBar({ label, hint, value, max, muted = false }: {
  label: string; hint: string; value: number; max: number; muted?: boolean;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <span className="font-semibold">{label}</span>
          <span className="ml-2 text-xs text-muted">{hint}</span>
        </div>
        <span className="text-2xl font-extrabold tabular-nums tracking-tight">{tokens(Math.round(value))}</span>
      </div>
      <div className="mt-2 h-6 rounded-r-[6px] bg-transparent">
        <div
          className={`h-6 rounded-r-[6px] ${muted ? "bg-muted/45" : "bg-series"}`}
          style={{ width: `${Math.max((value / Math.max(max, 1)) * 100, 1.5)}%` }}
        />
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card card-lift p-5">
      <div className="flex items-center gap-3">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">{icon}</div>
        <div className="text-sm text-text-2">{label}</div>
      </div>
      <div className="mt-4 text-3xl font-extrabold tracking-tight">{value}</div>
    </div>
  );
}

function Found({ value }: { value: boolean | null }) {
  if (value === null) return null;
  return value ? (
    <span className="ml-1.5 text-good" aria-label="answer found">✓</span>
  ) : (
    <span className="ml-1.5 text-warn" aria-label="answer missed">✗</span>
  );
}

function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
