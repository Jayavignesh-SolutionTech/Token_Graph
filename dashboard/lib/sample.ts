import type { Bucket, TokenGuardExport } from "./export";

/** Synthetic demo data for a small team, so the dashboard can be explored without an export. */

type Row = [key: string, calls: number, input: number, cacheWrite: number, cacheRead: number, output: number, cost: number];

function bucket([key, calls, input, cacheWrite, cacheRead, output, cost]: Row): Bucket {
  const inputSide = input + cacheWrite + cacheRead;
  return {
    key,
    calls,
    input_tokens: input,
    output_tokens: output,
    cache_write_tokens: cacheWrite,
    cache_read_tokens: cacheRead,
    total_tokens: inputSide + output,
    cache_hit_rate: inputSide ? cacheRead / inputSide : 0,
    cost_usd: cost,
    unpriced_calls: 0,
    unpriced_models: [],
  };
}

const days: Row[] = [
  ["2026-09-20", 410, 61_000, 1_310_000, 21_400_000, 352_000, 22.4],
  ["2026-09-21", 120, 18_000, 402_000, 6_100_000, 98_000, 6.3],
  ["2026-09-22", 640, 95_000, 2_010_000, 34_800_000, 561_000, 35.9],
  ["2026-09-23", 712, 104_000, 2_260_000, 38_100_000, 604_000, 39.8],
  ["2026-09-24", 688, 99_000, 2_150_000, 36_900_000, 590_000, 38.1],
  ["2026-09-25", 731, 110_000, 2_330_000, 40_200_000, 633_000, 41.7],
  ["2026-09-26", 590, 87_000, 1_870_000, 31_600_000, 502_000, 32.6],
  ["2026-09-27", 140, 21_000, 455_000, 7_000_000, 112_000, 7.2],
  ["2026-09-28", 96, 14_000, 301_000, 4_800_000, 77_000, 4.9],
  ["2026-09-29", 702, 103_000, 2_220_000, 37_700_000, 598_000, 39.0],
  ["2026-09-30", 845, 128_000, 2_690_000, 46_300_000, 721_000, 47.6],
  ["2026-10-01", 790, 117_000, 2_480_000, 42_800_000, 668_000, 44.1],
  ["2026-10-02", 756, 112_000, 2_400_000, 41_000_000, 645_000, 42.3],
  ["2026-10-03", 380, 56_000, 1_190_000, 20_300_000, 321_000, 21.1],
];

const sum = (i: number) => days.reduce((acc, row) => acc + (row[i] as number), 0);
const TOTAL_COST = 395; // matches the by_model / by_project / by_source breakdowns below
const dayScale = TOTAL_COST / sum(6);

export const SAMPLE_EXPORT: TokenGuardExport = {
  schema: "tokenguard.export/v1",
  version: "sample",
  generated_at: "2026-10-03T12:00:00+00:00",
  since: "14d",
  note: "Sample data for a fictional five-person team. Costs are API-equivalent at list prices.",
  total: bucket(["TOTAL", sum(1), sum(2), sum(3), sum(4), sum(5), TOTAL_COST]),
  by_day: days.map((row) => bucket([...row.slice(0, 6), Math.round(row[6] * dayScale * 100) / 100] as Row)),
  by_model: [
    bucket(["claude-opus-5-5", 3910, 512_000, 17_900_000, 251_000_000, 3_920_000, 254.6]),
    bucket(["gpt-5.5", 2140, 431_000, 0, 98_600_000, 1_610_000, 100.8]),
    bucket(["claude-sonnet-5-5", 1050, 140_000, 5_340_000, 59_400_000, 900_000, 37.1]),
    bucket(["claude-haiku-4-5", 500, 42_000, 820_000, 20_000_000, 152_000, 2.5]),
  ],
  by_project: [
    bucket(["web-app", 3120, 431_000, 10_800_000, 158_000_000, 2_480_000, 151.2]),
    bucket(["api-server", 2460, 352_000, 8_100_000, 131_000_000, 2_050_000, 124.9]),
    bucket(["mobile", 1290, 198_000, 3_700_000, 82_400_000, 1_210_000, 71.3]),
    bucket(["infra", 730, 144_000, 1_460_000, 57_600_000, 842_000, 47.6]),
  ],
  by_source: [
    bucket(["claude-code", 5460, 694_000, 24_060_000, 330_400_000, 4_972_000, 294.2]),
    bucket(["codex", 2140, 431_000, 0, 98_600_000, 1_610_000, 100.8]),
  ],
  tools: [
    { tool: "Bash", results: 2810, est_tokens: 6_420_000, largest_est_tokens: 48_000 },
    { tool: "Read", results: 3390, est_tokens: 5_110_000, largest_est_tokens: 25_000 },
    { tool: "exec", results: 1460, est_tokens: 3_380_000, largest_est_tokens: 31_000 },
    { tool: "Grep", results: 1720, est_tokens: 1_240_000, largest_est_tokens: 12_000 },
    { tool: "WebFetch", results: 140, est_tokens: 840_000, largest_est_tokens: 24_000 },
    { tool: "Edit", results: 2050, est_tokens: 96_000, largest_est_tokens: 300 },
  ],
};
