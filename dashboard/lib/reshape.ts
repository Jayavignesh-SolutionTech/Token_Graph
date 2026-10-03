/** Shared between the /api/reshape route and the reshaper UI. */

export type ReshapeMode = "balanced" | "concise";

export const MAX_PROMPT_CHARS = 12_000;

export interface ReshapeResult {
  rewritten_prompt: string;
  changes: string[];
  missing_info: string[];
  tokens_before: number;
  tokens_after: number;
  model: string;
  /** What this rewrite itself cost, at list price. */
  reshape_cost_usd: number;
}

export interface ReshapeError {
  error: string;
}

/** USD per million tokens for the models the reshaper may run on (list prices, checked 2026-10-03). */
export const RESHAPE_PRICES: Record<string, { input: number; output: number }> = {
  "claude-opus-5-5": { input: 4, output: 20 },
  "claude-sonnet-5-5": { input: 2, output: 10 },
  "claude-haiku-4-5": { input: 1, output: 5 },
};
