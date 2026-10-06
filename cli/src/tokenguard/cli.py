"""``tokenguard`` command-line interface."""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tokenguard import __version__, cli_graph
from tokenguard.models import ToolOutput, UsageRecord
from tokenguard.pricing import USER_PRICING_PATH, PriceTable
from tokenguard.report import summarize, summarize_tools
from tokenguard.sources import claude_code, codex

app = typer.Typer(
    help="TokenGuard: see where your AI coding agents spend tokens and money.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

SOURCES = {"claude-code": claude_code, "codex": codex}
COST_NOTE = (
    "Costs are API-equivalent at list prices. On a subscription plan "
    "(Claude Pro/Max, ChatGPT Plus/Pro) this is not your bill."
)


class Source(str, Enum):
    all = "all"
    claude_code = "claude-code"
    codex = "codex"


class GroupBy(str, Enum):
    source = "source"
    model = "model"
    project = "project"
    day = "day"
    session = "session"


class Format(str, Enum):
    table = "table"
    json = "json"
    csv = "csv"


SinceOpt = Annotated[str | None, typer.Option(help="Only include usage newer than this, e.g. 24h, 7d, 4w, or 2026-09-01.")]
SourceOpt = Annotated[Source, typer.Option(help="Which agent's logs to read.")]
ProjectOpt = Annotated[str | None, typer.Option(help="Only include this project (working-directory name).")]


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    m = re.fullmatch(r"(\d+)([hdw])", value.strip().lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]
        return datetime.now(timezone.utc) - delta
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f"can't read {value!r}; use 24h, 7d, 4w or YYYY-MM-DD") from None
    return ts if ts.tzinfo else ts.astimezone()


def _load(source: Source, since: str | None, project: str | None) -> tuple[list[UsageRecord], list[ToolOutput]]:
    cutoff = _parse_since(since)
    names = SOURCES if source is Source.all else {source.value: SOURCES[source.value]}
    records: list[UsageRecord] = []
    outputs: list[ToolOutput] = []
    for module in names.values():
        recs, outs = module.parse(module.find_files())
        records.extend(recs)
        outputs.extend(outs)
    if cutoff:
        records = [r for r in records if r.timestamp >= cutoff]
        kept_sessions = {r.session_id for r in records}
        outputs = [o for o in outputs if o.session_id in kept_sessions]
    if project:
        records = [r for r in records if r.project.lower() == project.lower()]
        outputs = [o for o in outputs if o.project.lower() == project.lower()]
    return records, outputs


def _usd(value: float) -> str:
    return f"${value:,.2f}" if value >= 0.01 or value == 0 else f"${value:,.4f}"


def _tok(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 10_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:,}"


@app.command()
def report(
    by: Annotated[GroupBy, typer.Option(help="How to group the rows.")] = GroupBy.model,
    since: SinceOpt = None,
    source: SourceOpt = Source.all,
    project: ProjectOpt = None,
    fmt: Annotated[Format, typer.Option("--format", help="Output format.")] = Format.table,
    limit: Annotated[int, typer.Option(help="Max rows in table output (0 = all).")] = 25,
) -> None:
    """Token usage and API-equivalent cost, grouped by model, project, day, session or source."""
    records, _ = _load(source, since, project)
    buckets, total = summarize(records, PriceTable.load(), by.value)

    if fmt is Format.json:
        json.dump({"group_by": by.value, "rows": [b.to_dict() for b in buckets], "total": total.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    if fmt is Format.csv:
        rows = [b.to_dict() for b in buckets]
        if rows:
            writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            for row in rows:
                row["unpriced_models"] = ";".join(row["unpriced_models"])
                writer.writerow(row)
        return

    if not records:
        console.print("[yellow]No usage found.[/] Run [bold]tokenguard sources[/] to see where TokenGuard looks.")
        return

    table = Table(title=f"Usage by {by.value}", title_justify="left", header_style="bold")
    table.add_column(by.value.capitalize(), overflow="fold")
    for col in ("Calls", "Input", "Cache write", "Cache read", "Output", "Cache hit", "Cost"):
        table.add_column(col, justify="right")
    shown = buckets if limit <= 0 else buckets[:limit]
    for b in shown:
        cost = _usd(b.cost_usd) + (" *" if b.unpriced_calls else "")
        table.add_row(b.key, f"{b.calls:,}", _tok(b.input_tokens), _tok(b.cache_write_tokens),
                      _tok(b.cache_read_tokens), _tok(b.output_tokens), f"{b.cache_hit_rate:.0%}", cost)
    table.add_section()
    table.add_row("[bold]Total[/]", f"{total.calls:,}", _tok(total.input_tokens), _tok(total.cache_write_tokens),
                  _tok(total.cache_read_tokens), _tok(total.output_tokens), f"{total.cache_hit_rate:.0%}",
                  f"[bold]{_usd(total.cost_usd)}[/]")
    console.print(table)
    if len(buckets) > len(shown):
        console.print(f"[dim]{len(buckets) - len(shown)} more rows hidden; use --limit 0 to show all.[/]")
    if total.unpriced_calls:
        console.print(f"[yellow]* {total.unpriced_calls} calls use models with no known price "
                      f"({', '.join(sorted(total.unpriced_models))}); they count as $0. "
                      f"Add prices in {USER_PRICING_PATH}.[/]")
    console.print(f"[dim]{COST_NOTE}[/]")


@app.command()
def tools(
    since: SinceOpt = None,
    source: SourceOpt = Source.all,
    project: ProjectOpt = None,
    limit: Annotated[int, typer.Option(help="Max rows (0 = all).")] = 15,
) -> None:
    """Which tools push the most output back into the model's context."""
    _, outputs = _load(source, since, project)
    buckets = summarize_tools(outputs)
    if not buckets:
        console.print("[yellow]No tool results found.[/]")
        return
    total_chars = sum(b.chars for b in buckets) or 1
    table = Table(title="Tool output fed back into context", title_justify="left", header_style="bold")
    for col, justify in (("Tool", "left"), ("Results", "right"), ("Est. tokens", "right"),
                         ("Share", "right"), ("Avg / result", "right"), ("Largest", "right")):
        table.add_column(col, justify=justify)
    for b in buckets if limit <= 0 else buckets[:limit]:
        table.add_row(b.tool, f"{b.results:,}", _tok(b.est_tokens), f"{b.chars / total_chars:.0%}",
                      _tok(b.est_tokens // max(b.results, 1)), _tok(b.largest_chars // 4))
    console.print(table)
    console.print("[dim]Token counts are estimated at ~4 characters per token. Each result is billed once "
                  "when first sent, then again (as cheaper cache reads) on every later turn.[/]")


@app.command()
def export(
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write to this file instead of stdout.")] = None,
    since: SinceOpt = None,
    source: SourceOpt = Source.all,
    project: ProjectOpt = None,
) -> None:
    """Export every breakdown as one JSON file for the TokenGuard dashboard."""
    records, outputs = _load(source, since, project)
    prices = PriceTable.load()
    data: dict = {
        "schema": "tokenguard.export/v1",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "since": since,
        "note": COST_NOTE,
    }
    for by in ("model", "project", "day", "source"):
        buckets, total = summarize(records, prices, by)
        data[f"by_{by}"] = [b.to_dict() for b in buckets]
    data["total"] = total.to_dict()
    data["tools"] = [
        {"tool": b.tool, "results": b.results, "est_tokens": b.est_tokens, "largest_est_tokens": b.largest_chars // 4}
        for b in summarize_tools(outputs)
    ]
    text = json.dumps(data, indent=2)
    if output is None:
        sys.stdout.write(text + "\n")
    else:
        output.write_text(text + "\n", encoding="utf-8")
        console.print(f"Wrote {output} ({total.calls:,} calls, {_usd(total.cost_usd)}). "
                      "Drop it on the TokenGuard dashboard to view it.")


@app.command()
def sources() -> None:
    """Show where TokenGuard looks for each agent's logs."""
    table = Table(header_style="bold")
    table.add_column("Source")
    table.add_column("Log directory", overflow="fold")
    table.add_column("Files", justify="right")
    for name, module in SOURCES.items():
        root: Path = module.default_root()
        table.add_row(name, str(root), str(len(module.find_files())) if root.is_dir() else "[dim]not found[/]")
    console.print(table)
    console.print(f"[dim]Price overrides: {USER_PRICING_PATH}"
                  f"{'' if USER_PRICING_PATH.is_file() else ' (not created)'}[/]")


@app.command()
def version() -> None:
    """Print the TokenGuard version."""
    console.print(f"tokenguard {__version__}")


cli_graph.register(app, console)


if __name__ == "__main__":
    app()
