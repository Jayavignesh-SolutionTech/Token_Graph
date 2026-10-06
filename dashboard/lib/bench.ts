/** Shape of `tokenguard bench` output (schema tokenguard.bench/v1). */

import { parseExport, type TokenGuardExport } from "./export";

export interface BenchQuestion {
  question: string;
  target: string | null;
  without_tokens: number;
  without_files: number;
  without_found: boolean | null;
  with_tokens: number;
  with_found: boolean | null;
  saved_pct: number;
}

export interface BenchResult {
  schema: "tokenguard.bench/v1";
  version: string;
  generated_at: string;
  repo: string;
  graph: {
    files: Record<string, number>;
    nodes: number;
    edges: number;
    edges_by_kind: Record<string, number>;
    scan_seconds: number;
    build_llm_tokens: number;
    source_tokens: number;
  };
  method: { without: string; with: string; tokens: string };
  questions: BenchQuestion[];
  totals: {
    questions: number;
    without_tokens: number;
    with_tokens: number;
    saved_tokens: number;
    saved_pct: number;
    ratio: number | null;
    with_found: number;
    without_found: number;
    judged: number;
  };
}

export type LoadedFile = { kind: "bench"; data: BenchResult } | { kind: "usage"; data: TokenGuardExport };

/** USD per million input tokens (list prices, checked 2026-10-03). Context is input to the model. */
export const INPUT_PRICES: { id: string; label: string; perMTok: number }[] = [
  { id: "claude-opus-5-5", label: "Claude Opus 5.5", perMTok: 4 },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5", perMTok: 2 },
  { id: "claude-haiku-4-5", label: "Claude Haiku 4.5", perMTok: 1 },
  { id: "gpt-5.5", label: "GPT-5.5", perMTok: 5 },
];

/** Accept either a `tokenguard bench` or a `tokenguard export` file. */
export function parseAnyFile(text: string): LoadedFile {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("That file isn't valid JSON. Create one with: tokenguard bench . -o bench.json");
  }
  const schema = (data as { schema?: unknown } | null)?.schema;
  if (schema === "tokenguard.bench/v1") {
    const d = data as BenchResult;
    if (!Array.isArray(d.questions) || !d.totals || !d.graph) throw new Error("The benchmark file is incomplete.");
    return { kind: "bench", data: d };
  }
  if (schema === "tokenguard.export/v1") return { kind: "usage", data: parseExport(text) };
  throw new Error("That isn't a TokenGuard file. Create one with: tokenguard bench . -o bench.json");
}
