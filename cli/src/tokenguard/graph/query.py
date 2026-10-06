"""Query the code map. Every function returns compact text meant to be read by an AI assistant."""

from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from tokenguard.graph.model import (
    CALLS, CLASS, CONTAINS, DOC, FILE, IMPORTS, INFERRED, INHERITS, MENTIONS, SYMBOL_KINDS, Graph, Node,
)
from tokenguard.graph.tokens import estimate_tokens

_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*")
_WORD_SPLIT = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_STOP = set(
    "a an and are as at be by can could do does doing for from get got has have how i if in into is it its "
    "me my of on or our should so that the their then there these this to use used uses using was what "
    "when where which who why will with work works would you your code file files function functions class "
    "method methods module call calls called explain show find tell about whole entire project repo".split()
)
MAX_LIST = 12


def words(text: str) -> set[str]:
    """Lower-case words from identifiers and prose: ``getUserById`` -> {get, user, by, id}."""
    out: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+", text):
        for w in _WORD_SPLIT.findall(token):
            w = w.lower()
            if len(w) > 2 and w not in _STOP:
                out.add(w)
    return out


def identifiers(text: str) -> list[str]:
    """Identifier-like tokens a developer would grep for (snake_case, camelCase, dotted)."""
    found = []
    for ident in _IDENT.findall(text):
        last = ident.rsplit(".", 1)[-1]
        looks_like_code = "." in ident or "_" in last or any(c.isupper() for c in last[1:]) or ident.endswith("()")
        if len(last) >= 3 and (looks_like_code or last.lower() not in _STOP) and last.lower() not in _STOP:
            found.append(ident)
    return list(dict.fromkeys(found))


# --- lookup -----------------------------------------------------------------------

def find(graph: Graph, term: str, limit: int = 10, kinds: set[str] | None = None) -> list[Node]:
    """Rank nodes whose name, qualname or path matches ``term``."""
    t = term.strip().lower().rstrip("()")
    scored: list[tuple[float, Node]] = []
    for n in graph.nodes.values():
        if kinds and n.kind not in kinds:
            continue
        name, qual, path = n.name.lower(), (n.qualname or "").lower(), n.file.lower()
        if t in (name, qual, n.id.lower(), path):
            score = 100.0
        elif qual.endswith("." + t) or path.endswith("/" + t):
            score = 80.0
        elif name.startswith(t):
            score = 50.0
        elif t in name or t in qual:
            score = 30.0
        elif t in path:
            score = 10.0
        else:
            continue
        if n.kind in SYMBOL_KINDS:
            score += 5
        scored.append((score + math.log1p(graph.degree(n.id)), n))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return [n for _, n in scored[:limit]]


def resolve(graph: Graph, ref: str) -> Node | None:
    if ref in graph.nodes:
        return graph.nodes[ref]
    if f"file:{ref}" in graph.nodes:
        return graph.nodes[f"file:{ref}"]
    hits = find(graph, ref, limit=1)
    return hits[0] if hits else None


def _label(graph: Graph, node_id: str) -> str:
    n = graph.nodes.get(node_id)
    if n is None:
        return node_id
    if n.kind == FILE:
        return n.file
    if n.kind == DOC:
        return f"{n.file}{n.qualname}"
    return f"{n.qualname or n.name} ({n.file}:{n.line})"


def _names(graph: Graph, ids: list[str], inferred: set[str] | None = None) -> str:
    ids = list(dict.fromkeys(ids))
    shown = [(_label(graph, i) + (" ~" if inferred and i in inferred else "")) for i in ids[:MAX_LIST]]
    more = f" (+{len(ids) - MAX_LIST} more)" if len(ids) > MAX_LIST else ""
    return ", ".join(shown) + more if shown else "none"


def _add(lines: list[str], label: str, value: str) -> None:
    """Append ``label: value`` unless there is nothing to say (saves tokens)."""
    if value and value != "none":
        lines.append(f"{label}: {value}")


def _location(n: Node) -> str:
    return f"{n.file}:{n.line}-{n.end_line}" if n.line else n.file


# --- views ------------------------------------------------------------------------

def callers(graph: Graph, node: Node) -> list[str]:
    return [e.src for e in graph.in_edges(node.id, CALLS)]


def callees(graph: Graph, node: Node) -> list[str]:
    return [e.dst for e in graph.out_edges(node.id, CALLS)]


def explain(graph: Graph, node: Node, root: Path | None = None, source_lines: int = 0) -> str:
    """Everything the map knows about one node, plus optionally its source."""
    lines = [f"## {node.kind} {node.qualname or node.name}  [{_location(node)}]"]
    if node.signature:
        lines.append(node.signature)
    if node.doc:
        lines.append(f"doc: {node.doc}")
    if node.kind == FILE:
        defs = [e.dst for e in graph.out_edges(node.id, CONTAINS)]
        lines.append(f"defines: {_names(graph, defs)}")
        lines.append(f"imports: {_names(graph, [e.dst for e in graph.out_edges(node.id, IMPORTS)])}")
        lines.append(f"imported by: {_names(graph, [e.src for e in graph.in_edges(node.id, IMPORTS)])}")
    else:
        parent = [e.src for e in graph.in_edges(node.id, CONTAINS)]
        if parent:
            lines.append(f"in: {_label(graph, parent[0])}")
        inferred = {e.dst for e in graph.out_edges(node.id) if e.confidence == INFERRED}
        inferred |= {e.src for e in graph.in_edges(node.id) if e.confidence == INFERRED}
        if node.kind == CLASS:
            members = [graph.nodes[e.dst].name for e in graph.out_edges(node.id, CONTAINS)]
            _add(lines, "members", ", ".join(members[:30]) + (f" (+{len(members) - 30} more)" if len(members) > 30 else ""))
            _add(lines, "inherits", _names(graph, [e.dst for e in graph.out_edges(node.id, INHERITS)], inferred))
            _add(lines, "subclassed by", _names(graph, [e.src for e in graph.in_edges(node.id, INHERITS)], inferred))
        _add(lines, "calls", _names(graph, callees(graph, node), inferred))
        lines.append(f"called by: {_names(graph, callers(graph, node), inferred)}")
    docs = [e.src for e in graph.in_edges(node.id, MENTIONS)]
    if docs:
        lines.append(f"mentioned in: {_names(graph, docs)}")
    if source_lines and root is not None and node.line:
        snippet = read_lines(root, node.file, node.line, min(node.end_line, node.line + source_lines - 1))
        if snippet:
            truncated = node.end_line > node.line + source_lines - 1
            lines.append(f"```\n{snippet}\n```" + (f"\n(source truncated; full range {_location(node)})" if truncated else ""))
    return "\n".join(lines)


def deps(graph: Graph, node: Node) -> str:
    file_node = node if node.kind == FILE else graph.nodes.get(f"file:{node.file}")
    if file_node is None:
        return f"No file node for {node.file}"
    return "\n".join([
        f"## {file_node.file}",
        f"imports: {_names(graph, [e.dst for e in graph.out_edges(file_node.id, IMPORTS)])}",
        f"imported by: {_names(graph, [e.src for e in graph.in_edges(file_node.id, IMPORTS)])}",
    ])


def path(graph: Graph, a: Node, b: Node, max_depth: int = 8) -> str:
    """Shortest chain of calls/imports/inheritance from a to b (directed first, then any direction)."""
    for directed in (True, False):
        prev: dict[str, tuple[str, str]] = {a.id: ("", "")}
        queue = deque([(a.id, 0)])
        while queue:
            cur, depth = queue.popleft()
            if cur == b.id:
                chain = [cur]
                while prev[chain[-1]][0]:
                    chain.append(prev[chain[-1]][0])
                chain.reverse()
                steps = [_label(graph, chain[0])]
                for node_id in chain[1:]:
                    steps.append(f"  --{prev[node_id][1]}--> {_label(graph, node_id)}")
                return "\n".join(steps)
            if depth >= max_depth:
                continue
            nxt = [(e.dst, e.kind) for e in graph.out_edges(cur) if e.kind in (CALLS, IMPORTS, INHERITS, CONTAINS)]
            if not directed:
                nxt += [(e.src, f"{e.kind} (reverse)") for e in graph.in_edges(cur) if e.kind in (CALLS, IMPORTS, INHERITS, CONTAINS)]
            for node_id, kind in nxt:
                if node_id not in prev:
                    prev[node_id] = (cur, kind)
                    queue.append((node_id, depth + 1))
    return f"No connection found between {_label(graph, a.id)} and {_label(graph, b.id)}."


def read_lines(root: Path, rel: str, start: int, end: int) -> str:
    try:
        text = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(text[max(start - 1, 0):end])


# --- the main entry point: answer a question from the map ------------------------------

@dataclass
class ContextResult:
    text: str
    seeds: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


def _is_test(path_: str) -> bool:
    p = path_.lower()
    return "/test" in p or p.startswith("test") or ".test." in p or ".spec." in p or "_test." in p


def rank(graph: Graph, question: str, limit: int = 5) -> list[tuple[float, Node]]:
    q_words = words(question)
    q_idents = {i.lower().rstrip("()") for i in identifiers(question)}
    q_tails = {i.rsplit(".", 1)[-1] for i in q_idents}
    scored: list[tuple[float, Node]] = []
    for n in graph.nodes.values():
        if n.kind not in SYMBOL_KINDS and n.kind != DOC:
            continue
        name = n.name.lower()
        qual = (n.qualname or "").lower()
        score = 0.0
        if qual in q_idents or (name in q_tails and name in q_idents):
            score += 12
        elif name in q_tails:
            score += 8
        name_words = words(n.name)
        score += 3 * len(name_words & q_words)
        score += 1.0 * len(words(n.qualname or "") - name_words & q_words)
        score += 0.5 * len(words(n.file) & q_words)
        score += 1.0 * len(words(n.doc) & q_words)
        if score <= 0:
            continue
        score += 0.4 * math.log1p(graph.degree(n.id))
        if _is_test(n.file):
            score *= 0.5
        if n.kind == DOC:
            score *= 0.6
        scored.append((score, n))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return scored[:limit]


def context(graph: Graph, question: str, root: Path | None = None, budget: int = 1500,
            max_seeds: int = 5, snippet_lines: int = 40) -> ContextResult:
    """Answer a question with a small, relevant slice of the map instead of whole files."""
    ranked = rank(graph, question, limit=max_seeds)
    if not ranked:
        return ContextResult(text=f"No symbols in the code map match: {question}\n"
                                  "Try tokenguard_search with a function, class or file name.")
    parts = [f"# Code map: {question}"]
    seeds = [n.id for _, n in ranked]
    files: list[str] = []
    for _, n in ranked:
        parts.append(explain(graph, n))
        if n.file not in files:
            files.append(n.file)
    text = "\n\n".join(parts)

    # Add source for the strongest matches, keeping whole lines while they fit the budget.
    if root is not None:
        for _, n in ranked[:3]:
            if n.kind not in SYMBOL_KINDS or not n.line:
                continue
            room = budget - estimate_tokens(text) - 40
            if room < 80:
                break
            src = read_lines(root, n.file, n.line, min(n.end_line, n.line + snippet_lines - 1)).splitlines()
            kept: list[str] = []
            for line in src:
                if estimate_tokens("\n".join([*kept, line])) > room:
                    break
                kept.append(line)
            if not kept:
                continue
            end = n.line + len(kept) - 1
            more = f"\n(continues to line {n.end_line})" if end < n.end_line else ""
            text += f"\n\n### source: {n.qualname} [{n.file}:{n.line}-{end}]\n```\n" + "\n".join(kept) + f"\n```{more}"
    text += "\n\nOpen these files only if you need more detail: " + ", ".join(files)
    return ContextResult(text=text, seeds=seeds, files=files)
