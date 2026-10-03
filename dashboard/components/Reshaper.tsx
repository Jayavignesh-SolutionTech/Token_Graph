"use client";

import { useState } from "react";
import { CopyIcon, ShieldIcon, SparklesIcon } from "@/components/icons";
import { usd } from "@/lib/format";
import { MAX_PROMPT_CHARS, type ReshapeError, type ReshapeMode, type ReshapeResult } from "@/lib/reshape";

const EXAMPLE = `Hi! I hope you're doing well. I was wondering if you could maybe help me out with something. So basically I have this Python function that is supposed to read a CSV file and then calculate the average of a column, but it's not really working the way I want it to and I'm not totally sure why. Could you please take a look at it and tell me what might be wrong with it and also maybe fix it for me if possible? Thanks so much in advance, I really appreciate it!

def avg(path, col):
    rows = open(path).read().split("\\n")
    vals = [float(r.split(",")[col]) for r in rows]
    return sum(vals) / len(vals)`;

const MODES: { value: ReshapeMode; title: string; hint: string }[] = [
  { value: "balanced", title: "Balanced", hint: "Best answer quality" },
  { value: "concise", title: "Concise", hint: "Fewest tokens" },
];

export function Reshaper() {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<ReshapeMode>("balanced");
  const [accessCode, setAccessCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReshapeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function reshape() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/reshape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, mode, accessCode: accessCode || undefined }),
      });
      const data: ReshapeResult | ReshapeError = await res.json();
      if (!res.ok || "error" in data) {
        setError("error" in data ? data.error : `Request failed (${res.status}).`);
      } else {
        setResult(data);
      }
    } catch {
      setError("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function copy() {
    if (!result) return;
    await navigator.clipboard.writeText(result.rewritten_prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-10">
      <section className="max-w-3xl">
        <span className="eyebrow">
          <SparklesIcon className="size-4" />
          Prompt reshaper
        </span>
        <h1 className="headline mt-6 text-5xl sm:text-6xl">
          Better answers from <span className="text-gradient">fewer tokens.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-text-2">
          Paste a prompt for Claude, ChatGPT, Codex or any model. TokenGuard keeps every requirement, cuts the filler,
          and asks for an answer format that avoids wasted output.
        </p>
      </section>

      <section className="card p-6 sm:p-8">
        <div className="flex items-center justify-between">
          <label htmlFor="prompt" className="text-lg font-bold tracking-tight">
            Your prompt
          </label>
          <button type="button" onClick={() => setPrompt(EXAMPLE)} className="text-sm font-medium text-accent hover:underline">
            Try an example
          </button>
        </div>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          maxLength={MAX_PROMPT_CHARS}
          rows={10}
          placeholder="Paste the prompt you were about to send…"
          className="mt-4 w-full resize-y rounded-2xl border border-border bg-surface-2 p-4 font-mono text-sm leading-relaxed outline-none transition-shadow focus:border-accent focus:shadow-[0_0_0_4px_var(--accent-soft)]"
        />
        <div className="mt-2 text-right text-xs text-muted">
          {prompt.length.toLocaleString("en-US")} / {MAX_PROMPT_CHARS.toLocaleString("en-US")} characters
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[auto_1fr_auto] lg:items-center">
          <fieldset className="grid grid-cols-2 gap-2">
            <legend className="sr-only">Mode</legend>
            {MODES.map((m) => (
              <label
                key={m.value}
                className={`cursor-pointer rounded-xl border px-4 py-2.5 transition-colors ${
                  mode === m.value
                    ? "border-accent bg-accent-soft"
                    : "border-border bg-surface hover:border-accent/50"
                }`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m.value}
                  checked={mode === m.value}
                  onChange={() => setMode(m.value)}
                  className="sr-only"
                />
                <div className={`text-sm font-semibold ${mode === m.value ? "text-accent" : "text-text"}`}>{m.title}</div>
                <div className="text-xs text-muted">{m.hint}</div>
              </label>
            ))}
          </fieldset>
          <div className="relative">
            <ShieldIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <input
              type="password"
              value={accessCode}
              onChange={(e) => setAccessCode(e.target.value)}
              placeholder="Access code (if required)"
              aria-label="Access code"
              className="w-full rounded-xl border border-border bg-surface py-3 pl-9 pr-3 text-sm outline-none focus:border-accent lg:max-w-xs"
            />
          </div>
          <button type="button" onClick={reshape} disabled={loading || !prompt.trim()} className="btn btn-primary">
            <SparklesIcon className="size-4" />
            {loading ? "Reshaping…" : "Reshape prompt"}
          </button>
        </div>
        {error && (
          <p className="mt-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</p>
        )}
      </section>

      {result && <Result result={result} copied={copied} onCopy={copy} />}
    </div>
  );
}

function Result({ result, copied, onCopy }: { result: ReshapeResult; copied: boolean; onCopy: () => void }) {
  const delta = result.tokens_after - result.tokens_before;
  const deltaPct = result.tokens_before ? delta / result.tokens_before : 0;
  const max = Math.max(result.tokens_before, result.tokens_after, 1);

  return (
    <section className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
      <div className="card p-6">
        <h2 className="text-lg font-bold tracking-tight">Token comparison</h2>
        <div
          className={`mt-5 inline-flex items-baseline gap-2 rounded-2xl px-4 py-2 ${
            delta <= 0 ? "bg-good/10 text-good" : "bg-warn/10 text-warn"
          }`}
        >
          <span className="text-4xl font-extrabold tracking-tight">
            {delta > 0 ? "+" : ""}
            {Math.round(deltaPct * 100)}%
          </span>
          <span className="text-sm font-medium">{delta <= 0 ? "fewer tokens" : "more tokens"}</span>
        </div>
        <div className="mt-6 space-y-4">
          <CompareBar label="Original" value={result.tokens_before} max={max} muted />
          <CompareBar label="Reshaped" value={result.tokens_after} max={max} />
        </div>
        {delta > 0 && (
          <p className="mt-5 text-sm leading-relaxed text-text-2">
            The rewrite adds structure, such as the answer format. That usually shortens the reply, and output tokens
            cost more than input tokens.
          </p>
        )}
        <p className="mt-5 border-t border-border pt-4 text-xs text-muted">
          Counted with Claude&apos;s tokenizer ({result.model}). This rewrite cost {usd(result.reshape_cost_usd)} at list
          price.
        </p>
      </div>

      <div className="card min-w-0 p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold tracking-tight">Reshaped prompt</h2>
          <button type="button" onClick={onCopy} className="btn btn-ghost !py-2 text-sm">
            <CopyIcon className="size-4" />
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <pre className="code-card mt-4 max-h-[420px] overflow-auto whitespace-pre-wrap p-5 font-mono text-sm leading-relaxed">
          {result.rewritten_prompt}
        </pre>
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <List title="What changed" items={result.changes} />
          <List title="Consider adding" items={result.missing_info} />
        </div>
      </div>
    </section>
  );
}

function CompareBar({ label, value, max, muted = false }: { label: string; value: number; max: number; muted?: boolean }) {
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-sm">
        <span className="text-text-2">{label}</span>
        <span className="font-semibold tabular-nums">{value.toLocaleString("en-US")} tokens</span>
      </div>
      <div className="h-3 rounded-full bg-series-track">
        <div
          className={`h-3 rounded-full ${muted ? "bg-muted/60" : "bg-series"}`}
          style={{ width: `${(value / max) * 100}%` }}
        />
      </div>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm text-text-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
