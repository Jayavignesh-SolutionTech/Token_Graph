import type { TokenGuardExport } from "./export";
import { pct, tokens, usd } from "./format";

export type InsightKind = "tools" | "model" | "cache" | "project";

export interface Insight {
  kind: InsightKind;
  title: string;
  body: string;
  /** The headline figure for the card, e.g. "38%". */
  figure: string;
}

/** Turn an export into a short, ranked list of places to look for savings. */
export function buildInsights(data: TokenGuardExport): Insight[] {
  const out: Insight[] = [];
  const total = data.total.cost_usd || 0;

  const toolTotal = data.tools.reduce((acc, t) => acc + t.est_tokens, 0);
  const topTool = data.tools[0];
  if (topTool && toolTotal > 0) {
    const share = topTool.est_tokens / toolTotal;
    out.push({
      kind: "tools",
      figure: pct(share),
      title: `Trim ${topTool.tool} output`,
      body: `${topTool.tool} results put ~${tokens(topTool.est_tokens)} tokens into context (largest single result ~${tokens(
        topTool.largest_est_tokens,
      )}). Truncating long output or filtering it before the agent reads it cuts every later turn too.`,
    });
  }

  const topModel = data.by_model[0];
  if (topModel && total > 0 && data.by_model.length > 0) {
    const share = topModel.cost_usd / total;
    out.push({
      kind: "model",
      figure: pct(share),
      title: `${topModel.key} drives most spend`,
      body: `${usd(topModel.cost_usd)} of ${usd(total)}. Routing routine edits and lookups to a smaller model, or a lower effort setting, is usually the biggest single lever.`,
    });
  }

  const hit = data.total.cache_hit_rate;
  out.push(
    hit < 0.8
      ? {
          kind: "cache",
          figure: pct(hit),
          title: "Cache hit rate is low",
          body: "Less than 80% of input is served from cache. Keep system prompts and tool lists stable between turns so the cached prefix is reused.",
        }
      : {
          kind: "cache",
          figure: pct(hit),
          title: "Caching is working",
          body: `${pct(hit)} of input tokens come from cache, so the remaining cost sits mostly in cache writes and output. Shorter answers and fewer re-reads matter more than prompt trimming here.`,
        },
  );

  const topProject = data.by_project[0];
  if (topProject && total > 0 && data.by_project.length > 1) {
    out.push({
      kind: "project",
      figure: usd(topProject.cost_usd),
      title: `${topProject.key} is the costliest project`,
      body: `${pct(topProject.cost_usd / total)} of spend across ${topProject.calls.toLocaleString(
        "en-US",
      )} calls. Start reviews and budgets here.`,
    });
  }

  return out;
}
