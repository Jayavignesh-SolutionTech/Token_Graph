/** Shape of `tokenguard export` output (schema tokenguard.export/v1). */

export interface Bucket {
  key: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
  total_tokens: number;
  cache_hit_rate: number;
  cost_usd: number;
  unpriced_calls: number;
  unpriced_models: string[];
}

export interface ToolRow {
  tool: string;
  results: number;
  est_tokens: number;
  largest_est_tokens: number;
}

export interface TokenGuardExport {
  schema: "tokenguard.export/v1";
  version: string;
  generated_at: string;
  since: string | null;
  note: string;
  total: Bucket;
  by_model: Bucket[];
  by_project: Bucket[];
  by_day: Bucket[];
  by_source: Bucket[];
  tools: ToolRow[];
}

const BUCKET_LISTS = ["by_model", "by_project", "by_day", "by_source"] as const;

/** Parse and sanity-check an export file. Throws an Error with a readable message. */
export function parseExport(text: string): TokenGuardExport {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("That file isn't valid JSON. Create it with: tokenguard export -o tokenguard.json");
  }
  if (!data || typeof data !== "object" || (data as { schema?: unknown }).schema !== "tokenguard.export/v1") {
    throw new Error("That file isn't a TokenGuard export. Create one with: tokenguard export -o tokenguard.json");
  }
  const d = data as Record<string, unknown>;
  for (const key of BUCKET_LISTS) {
    if (!Array.isArray(d[key])) throw new Error(`The export is missing "${key}".`);
  }
  if (!d.total || typeof d.total !== "object") throw new Error('The export is missing "total".');
  if (!Array.isArray(d.tools)) d.tools = [];
  return d as unknown as TokenGuardExport;
}
