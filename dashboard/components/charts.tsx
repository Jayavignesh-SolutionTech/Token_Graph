"use client";

import { useState } from "react";

export interface BarDatum {
  label: string;
  value: number;
  /** Lines shown in the hover tooltip. */
  detail?: string[];
}

/** Single-series horizontal bars: one hue, value at the bar tip, tooltip on hover/focus. */
export function HBarChart({ data, format }: { data: BarDatum[]; format: (v: number) => string }) {
  const max = Math.max(...data.map((d) => d.value), 0) || 1;
  return (
    <ul className="space-y-3">
      {data.map((d) => (
        <li
          key={d.label}
          tabIndex={0}
          className="group relative grid grid-cols-[minmax(7rem,11rem)_1fr] items-center gap-3 rounded outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <span className="truncate text-sm text-text-2" title={d.label}>
            {d.label}
          </span>
          <div className="flex items-center gap-2">
            <div
              className="h-4 min-w-[2px] rounded-r-[4px] bg-series"
              style={{ width: `${(d.value / max) * 85}%` }}
            />
            <span className="text-sm tabular-nums text-text">{format(d.value)}</span>
          </div>
          {d.detail && <Tooltip lines={[d.label, ...d.detail]} className="left-[11rem] top-6" />}
        </li>
      ))}
    </ul>
  );
}

/** Daily columns with hairline gridlines and a hover tooltip per column. */
export function DailyColumns({ data, format }: { data: BarDatum[]; format: (v: number) => string }) {
  const [active, setActive] = useState<number | null>(null);
  const max = niceMax(Math.max(...data.map((d) => d.value), 0));
  const ticks = [max, max / 2, 0];

  return (
    <div className="relative">
      <div className="relative ml-12 h-48">
        {ticks.map((t) => (
          <div key={t} className="absolute inset-x-0 border-t border-grid" style={{ bottom: `${(t / max) * 100}%` }}>
            <span className="absolute -left-12 -translate-y-1/2 text-xs tabular-nums text-muted">{format(t)}</span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end gap-[2px]" onMouseLeave={() => setActive(null)}>
          {data.map((d, i) => (
            <button
              key={d.label}
              type="button"
              aria-label={`${d.label}: ${format(d.value)}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="flex h-full flex-1 items-end justify-center outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <span
                className={`block w-full max-w-6 rounded-t-[4px] bg-series transition-opacity ${
                  active !== null && active !== i ? "opacity-50" : ""
                }`}
                style={{ height: `${Math.max((d.value / max) * 100, d.value > 0 ? 1 : 0)}%` }}
              />
            </button>
          ))}
        </div>
        {active !== null && (
          <Tooltip
            lines={[data[active].label, ...(data[active].detail ?? [format(data[active].value)])]}
            className="top-0"
            style={{ left: `${((active + 0.5) / data.length) * 100}%`, transform: "translateX(-50%)" }}
            visible
          />
        )}
      </div>
      <div className="ml-12 mt-2 flex justify-between text-xs text-muted">
        <span>{shortDate(data[0]?.label)}</span>
        <span>{shortDate(data[data.length - 1]?.label)}</span>
      </div>
    </div>
  );
}

function Tooltip({
  lines,
  className = "",
  style,
  visible = false,
}: {
  lines: string[];
  className?: string;
  style?: React.CSSProperties;
  visible?: boolean;
}) {
  return (
    <div
      role="tooltip"
      style={style}
      className={`pointer-events-none absolute z-10 min-w-40 rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-lg ${
        visible ? "block" : "hidden group-hover:block group-focus:block"
      } ${className}`}
    >
      <div className="mb-1 font-medium text-text">{lines[0]}</div>
      {lines.slice(1).map((line) => (
        <div key={line} className="tabular-nums text-text-2">
          {line}
        </div>
      ))}
    </div>
  );
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= value) ?? 10;
  return step * magnitude;
}

function shortDate(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
