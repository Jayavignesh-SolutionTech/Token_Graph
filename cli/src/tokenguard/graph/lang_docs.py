"""Markdown docs: one node per section, linked to code by exact names (no LLM)."""

from __future__ import annotations

import re

from tokenguard.graph.facts import FileFacts, Symbol, symbol_id
from tokenguard.graph.model import DOC

EXTENSIONS = (".md", ".mdx", ".rst")

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_CODE_SPAN = re.compile(r"`([^`\n]{2,120})`")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "section"


def extract(path: str, source: str) -> FileFacts:
    facts = FileFacts(path=path, lang="docs")
    lines = source.splitlines()
    sections: list[tuple[int, str]] = []  # (start line index, title)
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        m = None if in_fence else _HEADING.match(line)
        if m:
            sections.append((i, m.group(2).strip()))
    if not sections or sections[0][0] != 0:
        sections.insert(0, (0, path.rsplit("/", 1)[-1]))

    seen: set[str] = set()
    for idx, (start, title) in enumerate(sections):
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines)
        body = "\n".join(lines[start:end])
        if not body.strip():
            continue
        qual = _slug(title)
        while qual in seen:
            qual += "-1"
        seen.add(qual)
        first_text = next((ln.strip() for ln in lines[start + 1:end] if ln.strip() and not ln.startswith("#")), "")
        sec = Symbol(
            id=symbol_id(path, f"#{qual}"), kind=DOC, name=title[:120], qualname=f"#{qual}",
            line=start + 1, end_line=end, parent="", doc=first_text[:200],
        )
        facts.docs.append(sec)
        for span in _CODE_SPAN.findall(body):
            facts.mentions.append((sec.id, span.strip()))
    return facts
