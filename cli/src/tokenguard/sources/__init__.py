"""Readers that turn each coding agent's local logs into UsageRecords."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield JSON objects from a JSONL file, skipping blank or malformed lines."""
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def parse_ts(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def project_name(cwd: object) -> str:
    """Name of the git repository containing ``cwd``, else the directory's own name."""
    if not isinstance(cwd, str) or not cwd:
        return "unknown"
    return _project_name(cwd)


@lru_cache(maxsize=1024)
def _project_name(cwd: str) -> str:
    path = Path(cwd.replace("\\", "/"))
    try:
        for candidate in (path, *path.parents):
            if (candidate / ".git").exists():
                return candidate.name or cwd
    except OSError:
        pass
    return path.name or cwd


def content_chars(content: object) -> int:
    """Character length of a tool result's content (string or list of blocks)."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    total += len(block["text"])
                elif isinstance(block.get("content"), (str, list)):
                    total += content_chars(block["content"])
            elif isinstance(block, str):
                total += len(block)
        return total
    if isinstance(content, dict):
        return content_chars(content.get("content") or content.get("output") or "")
    return 0
