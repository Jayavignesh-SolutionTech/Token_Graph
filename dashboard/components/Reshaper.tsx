"use client";

import { useState } from "react";
import { usd } from "@/lib/format";
import { MAX_PROMPT_CHARS, type ReshapeError, type ReshapeMode, type ReshapeResult } from "@/lib/reshape";

const EXAMPLE = `Hi! I hope you're doing well. I was wondering if you could maybe help me out with something. So basically I have this Python function that is supposed to read a CSV file and then calculate the average of a column, but it's not really working the way I want it to and I'm not totally sure why. Could you please take a look at it and tell me what might be wrong with it and also maybe fix it for me if possible? Thanks so much in advance, I really appreciate it!

def avg(path, col):
    rows = open(path).read().split("\\n")
    vals = [float(r.split(",")[col]) for r in rows]
    return sum(vals) / len(vals)`;

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

  const delta = result ? result.tokens_after - result.tokens_before : 0;
  const deltaPct = result && result.tokens_before ? delta / result.tokens_before : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Prompt reshaper</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-2">
          Paste a prompt. TokenGuard rewrites it to be clearer and shorter, keeps every requirement, and asks for an
          answer format that avoids wasted output.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <label htmlFor="prompt" className="font-medium">
            Your prompt
          </label>
          <button type="button" onClick={() => setPrompt(EXAMPLE)} className="text-sm text-accent hover:underline">
            Use an example
          </button>
        </div>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          maxLength={MAX_PROMPT_CHARS}
          rows={10}
          placeholder="Paste the prompt you were about to send to Claude, ChatGPT, Codex or another model…"
          className="w-full resize-y rounded-md border border-border bg-bg p-3 font-mono text-sm leading-relaxed outline-none focus:border-series"
        />
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <fieldset className="flex gap-1 rounded-md border border-border p-1 text-sm">
            <legend className="sr-only">Mode</legend>
            {(["balanced", "concise"] as const).map((m) => (
              <label
                key={m}
                className={`cursor-pointer rounded px-3 py-1 ${mode === m ? "bg-series-track font-medium" : "text-text-2"}`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  className="sr-only"
                />
                {m === "balanced" ? "Balanced: best answer" : "Concise: fewest tokens"}
              </label>
            ))}
          </fieldset>
          <input
            type="password"
            value={accessCode}
            onChange={(e) => setAccessCode(e.target.value)}
            placeholder="Access code (if required)"
            aria-label="Access code"
            className="w-56 rounded-md border border-border bg-bg px-3 py-1.5 text-sm outline-none focus:border-series"
          />
          <span className="text-xs text-muted">
            {prompt.length.toLocaleString("en-US")} / {MAX_PROMPT_CHARS.toLocaleString("en-US")}
          </span>
          <button
            type="button"
            onClick={reshape}
            disabled={loading || !prompt.trim()}
            className="ml-auto rounded-md bg-accent px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Reshaping…" : "Reshape prompt"}
          </button>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </section>

      {result && (
        <section className="space-y-5 rounded-xl border border-border bg-surface p-5">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            <Figure label="Before" value={`${result.tokens_before.toLocaleString("en-US")} tokens`} />
            <Figure label="After" value={`${result.tokens_after.toLocaleString("en-US")} tokens`} />
            <Figure
              label="Change"
              value={`${delta > 0 ? "+" : ""}${Math.round(deltaPct * 100)}%`}
              tone={delta < 0 ? "good" : delta > 0 ? "warn" : undefined}
            />
            <button
              type="button"
              onClick={copy}
              className="ml-auto rounded-md border border-border px-4 py-2 text-sm hover:bg-bg"
            >
              {copied ? "Copied" : "Copy prompt"}
            </button>
          </div>
          {delta > 0 && (
            <p className="text-sm text-text-2">
              The rewrite is longer because it adds structure, such as the answer format. That usually shortens the
              reply, which costs more per token than the prompt.
            </p>
          )}

          <pre className="whitespace-pre-wrap rounded-md bg-bg p-4 font-mono text-sm leading-relaxed">
            {result.rewritten_prompt}
          </pre>

          <div className="grid gap-6 md:grid-cols-2">
            <List title="What changed" items={result.changes} />
            {result.missing_info.length > 0 && (
              <List title="Consider adding" items={result.missing_info} />
            )}
          </div>

          <p className="text-xs text-muted">
            Token counts use Claude&apos;s tokenizer ({result.model}). This rewrite cost {usd(result.reshape_cost_usd)}{" "}
            at list price.
          </p>
        </section>
      )}
    </div>
  );
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  const color = tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : "text-text";
  return (
    <div>
      <div className="text-sm text-text-2">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm font-medium">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-2">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
