"""With/without benchmark.

WITHOUT the map, a coding assistant typically greps the repo for the names in the
question and then reads the matching files. WITH the map, it calls
``tokenguard_ask`` and receives a compact answer plus only the source it needs.
Both sides are measured with the same token estimate, on the same questions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from tokenguard import __version__
from tokenguard.graph import lang_docs
from tokenguard.graph.build import list_files
from tokenguard.graph.model import CALLS, CLASS, METHOD, SYMBOL_KINDS, Graph, Node
from tokenguard.graph.query import _is_test, context, identifiers
from tokenguard.graph.tokens import estimate_tokens

SCHEMA = "tokenguard.bench/v1"
BASELINE_FILES = 5  # files an assistant opens after searching
GREP_LINE_CAP = 100  # matching lines it reads from the search output


@dataclass
class QuestionResult:
    question: str
    target: str | None
    without_tokens: int
    without_files: int
    without_found: bool | None
    with_tokens: int
    with_found: bool | None

    @property
    def saved_pct(self) -> float:
        return 1 - self.with_tokens / self.without_tokens if self.without_tokens else 0.0


def auto_questions(graph: Graph, n: int) -> list[tuple[str, str]]:
    """Pick well-connected, non-test symbols and phrase a typical question about each."""
    candidates: list[tuple[int, Node]] = []
    for node in graph.nodes.values():
        if node.kind not in SYMBOL_KINDS or _is_test(node.file) or node.name.startswith("__"):
            continue
        ins = len(graph.in_edges(node.id, CALLS))
        outs = len(graph.out_edges(node.id, CALLS))
        if ins >= 1 and (outs >= 1 or node.kind == CLASS):
            candidates.append((ins * 2 + outs, node))
    candidates.sort(key=lambda x: (-x[0], x[1].id))
    picked: list[tuple[str, str]] = []
    per_file: dict[str, int] = {}
    for _, node in candidates:
        if per_file.get(node.file, 0) >= 2:
            continue
        per_file[node.file] = per_file.get(node.file, 0) + 1
        label = node.qualname if node.kind == METHOD else node.name
        if node.kind == CLASS:
            q = f"What is the {label} class responsible for, and what depends on it?"
        elif len(picked) % 2:
            q = f"Where is {label} used, and what does it call?"
        else:
            q = f"How does {label} work, and what calls it?"
        picked.append((q, node.id))
        if len(picked) >= n:
            break
    return picked


class Baseline:
    """Simulates search-then-read: grep for the question's identifiers, open the top matching files."""

    def __init__(self, root: Path):
        self.root = root
        self.texts: dict[str, str] = {}
        for rel in list_files(root):
            if rel.lower().endswith(lang_docs.EXTENSIONS):
                continue
            try:
                self.texts[rel] = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

    def run(self, question: str) -> tuple[int, list[str]]:
        terms = {i.rsplit(".", 1)[-1].rstrip("()") for i in identifiers(question)}
        terms = {t for t in terms if len(t) >= 3}
        if not terms:
            return 0, []
        pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(terms)) + r")\b")
        grep_lines: list[str] = []
        hits: dict[str, int] = {}
        for rel, text in self.texts.items():
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits[rel] = hits.get(rel, 0) + 1
                    if len(grep_lines) < GREP_LINE_CAP:
                        grep_lines.append(f"{rel}:{lineno}:{line.strip()[:160]}")
        opened = sorted(hits, key=lambda r: (-hits[r], r))[:BASELINE_FILES]
        tokens = estimate_tokens("\n".join(grep_lines)) + sum(estimate_tokens(self.texts[r]) for r in opened)
        return tokens, opened


def run_bench(graph: Graph, root: Path, questions: list[tuple[str, str | None]]) -> dict:
    baseline = Baseline(root)
    results: list[QuestionResult] = []
    for question, target in questions:
        without_tokens, opened = baseline.run(question)
        ctx = context(graph, question, root=root)
        target_file = graph.nodes[target].file if target and target in graph.nodes else None
        results.append(QuestionResult(
            question=question,
            target=target,
            without_tokens=without_tokens,
            without_files=len(opened),
            without_found=(target_file in opened) if target_file else None,
            with_tokens=ctx.tokens,
            with_found=(target in ctx.seeds) if target else None,
        ))

    total_without = sum(r.without_tokens for r in results)
    total_with = sum(r.with_tokens for r in results)
    judged = [r for r in results if r.with_found is not None]
    return {
        "schema": SCHEMA,
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": Path(graph.root).name,
        "graph": {
            "files": graph.stats.get("files", {}),
            "nodes": sum(graph.stats.get("nodes", {}).values()),
            "edges": sum(graph.stats.get("edges", {}).values()),
            "edges_by_kind": graph.stats.get("edges", {}),
            "scan_seconds": graph.stats.get("scan_seconds"),
            "build_llm_tokens": graph.stats.get("llm_tokens", 0),
            "source_tokens": graph.stats.get("source_tokens", 0),
        },
        "method": {
            "without": f"grep the repo for identifiers in the question (first {GREP_LINE_CAP} matching lines), "
                       f"then read the {BASELINE_FILES} files with the most matches",
            "with": "one tokenguard_ask call: matching symbols with callers, callees and docs, "
                    "plus source for the top matches within a 1,500-token budget",
            "tokens": "estimated at ~4 characters per token, identically for both sides",
        },
        "questions": [{**asdict(r), "saved_pct": round(r.saved_pct, 4)} for r in results],
        "totals": {
            "questions": len(results),
            "without_tokens": total_without,
            "with_tokens": total_with,
            "saved_tokens": total_without - total_with,
            "saved_pct": round(1 - total_with / total_without, 4) if total_without else 0.0,
            "ratio": round(total_without / total_with, 2) if total_with else None,
            "with_found": sum(1 for r in judged if r.with_found),
            "without_found": sum(1 for r in judged if r.without_found),
            "judged": len(judged),
        },
    }
