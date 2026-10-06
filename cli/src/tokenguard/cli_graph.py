"""Code-map commands: scan, ask, explain, search, deps, path, bench, serve."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

RepoOpt = Annotated[Path, typer.Option("--repo", "-r", help="Repository root (default: current folder).")]


def _load(repo: Path):
    from tokenguard.graph.store import load

    return load(repo)


def register(app: typer.Typer, console: Console) -> None:
    @app.command(rich_help_panel="Code map")
    def scan(
        repo: Annotated[Path, typer.Argument(help="Repository to scan.")] = Path("."),
        output: Annotated[Path | None, typer.Option("--output", "-o", help="Where to write graph.json.")] = None,
    ) -> None:
        """Build the code map for a repository (local parsing, no LLM tokens)."""
        from tokenguard.graph.store import scan as do_scan

        graph, out = do_scan(repo, output)
        s = graph.stats
        table = Table(title=f"Code map for {Path(graph.root).name}", title_justify="left", header_style="bold")
        table.add_column("What")
        table.add_column("Count", justify="right")
        for lang, n in sorted(s["files"].items()):
            table.add_row(f"{lang} files", f"{n:,}")
        for kind, n in sorted(s["nodes"].items()):
            if kind != "file":
                table.add_row(f"{kind} nodes", f"{n:,}")
        for kind, n in sorted(s["edges"].items()):
            table.add_row(f"{kind} edges", f"{n:,}")
        console.print(table)
        console.print(f"Built in {s['scan_seconds']}s with 0 LLM tokens. "
                      f"{s['edges_inferred']:,} edges were matched by name only (marked ~).")
        console.print(f"Saved to [bold]{out}[/]")

    @app.command(rich_help_panel="Code map")
    def ask(
        question: Annotated[str, typer.Argument(help='e.g. "how does login work?"')],
        repo: RepoOpt = Path("."),
        budget: Annotated[int, typer.Option(help="Max tokens in the answer.")] = 1500,
    ) -> None:
        """Answer a question from the code map, the way an AI assistant would see it."""
        from tokenguard.graph.query import context

        result = context(_load(repo), question, root=repo.resolve(), budget=budget)
        console.print(escape(result.text), highlight=False)
        console.print(f"[dim]~{result.tokens:,} tokens[/]")

    @app.command(rich_help_panel="Code map")
    def explain(
        symbol: Annotated[str, typer.Argument(help="Function, class, method or file.")],
        repo: RepoOpt = Path("."),
        source: Annotated[bool, typer.Option("--source", help="Include the code.")] = False,
    ) -> None:
        """Callers, callees, inheritance and docs for one symbol or file."""
        from tokenguard.graph import query

        graph = _load(repo)
        node = query.resolve(graph, symbol)
        if node is None:
            console.print(f"[yellow]Nothing matches {symbol!r}.[/] Try [bold]tokenguard search[/].")
            raise typer.Exit(1)
        console.print(escape(query.explain(graph, node, root=repo.resolve(), source_lines=80 if source else 0)),
                      highlight=False)

    @app.command(rich_help_panel="Code map")
    def search(term: str, repo: RepoOpt = Path("."), limit: int = 15) -> None:
        """Find symbols, files and doc sections by name."""
        from tokenguard.graph import query

        hits = query.find(_load(repo), term, limit=limit)
        if not hits:
            console.print(f"[yellow]Nothing matches {term!r}.[/]")
            return
        for n in hits:
            where = f"{n.file}:{n.line}" if n.line else n.file
            console.print(f"[dim]{n.kind:9}[/] {escape(n.qualname or n.name)}  [dim]{escape(where)}[/]")

    @app.command(rich_help_panel="Code map")
    def deps(file: str, repo: RepoOpt = Path(".")) -> None:
        """Files this file imports, and files that import it."""
        from tokenguard.graph import query

        graph = _load(repo)
        node = query.resolve(graph, file)
        console.print(escape(query.deps(graph, node)) if node else f"[yellow]No file matches {file!r}.[/]")

    @app.command(rich_help_panel="Code map")
    def path(source: str, target: str, repo: RepoOpt = Path(".")) -> None:
        """Shortest chain of calls/imports/inheritance between two symbols."""
        from tokenguard.graph import query

        graph = _load(repo)
        a, b = query.resolve(graph, source), query.resolve(graph, target)
        if a is None or b is None:
            console.print(f"[yellow]Couldn't find {source if a is None else target!r}.[/]")
            raise typer.Exit(1)
        console.print(escape(query.path(graph, a, b)), highlight=False)

    @app.command(rich_help_panel="Code map")
    def bench(
        repo: Annotated[Path, typer.Argument(help="Repository to benchmark.")] = Path("."),
        questions: Annotated[int, typer.Option("--questions", "-n", help="Auto-generated questions.")] = 20,
        questions_file: Annotated[Path | None, typer.Option("--questions-file", help="One question per line.")] = None,
        output: Annotated[Path | None, typer.Option("--output", "-o", help="Write results JSON for the dashboard.")] = None,
    ) -> None:
        """Measure tokens per question WITH the code map vs WITHOUT it (grep + read files)."""
        from tokenguard.graph.bench import auto_questions, run_bench

        repo = repo.resolve()
        graph = _load(repo)
        qs: list[tuple[str, str | None]] = []
        if questions_file:
            qs = [(line.strip(), None) for line in questions_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            qs = list(auto_questions(graph, questions))
        if not qs:
            console.print("[yellow]No questions to run: the map has too few connected symbols.[/]")
            raise typer.Exit(1)
        data = run_bench(graph, repo, qs)
        t = data["totals"]

        table = Table(title=f"With vs without TokenGuard: {data['repo']}", title_justify="left", header_style="bold")
        table.add_column("Question", overflow="fold", max_width=60)
        table.add_column("Without", justify="right")
        table.add_column("With", justify="right")
        table.add_column("Saved", justify="right")
        for q in data["questions"]:
            found = "" if q["with_found"] is None else (" [green]✓[/]" if q["with_found"] else " [yellow]✗[/]")
            table.add_row(escape(q["question"]), f"{q['without_tokens']:,}", f"{q['with_tokens']:,}{found}",
                          f"{q['saved_pct']:.0%}")
        table.add_section()
        ratio = f"{t['ratio']}x fewer" if t["ratio"] else "-"
        table.add_row("[bold]Total[/]", f"{t['without_tokens']:,}", f"{t['with_tokens']:,}",
                      f"[bold]{t['saved_pct']:.0%}[/] ({ratio})")
        console.print(table)
        if t["judged"]:
            console.print(f"Map answer contained the asked-about symbol in {t['with_found']}/{t['judged']} questions; "
                          f"the files read without the map contained it in {t['without_found']}/{t['judged']}.")
        console.print(f"[dim]Without: {data['method']['without']}.\nWith: {data['method']['with']}.\n"
                      f"Tokens {data['method']['tokens']}. Building the map used 0 LLM tokens.[/]")
        if output:
            output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            console.print(f"Wrote {output}. Drop it on the TokenGuard dashboard to see the comparison.")

    @app.command(rich_help_panel="Code map")
    def serve(repo: RepoOpt = Path(".")) -> None:
        """Run the MCP server so AI assistants can query the code map (stdio)."""
        from tokenguard.graph.mcp_server import serve as run

        run(repo)
