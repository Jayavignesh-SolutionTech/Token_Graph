"""Claude Code session logs: ``~/.claude/projects/<project>/<session>.jsonl``.

Claude Code writes one JSONL line per content block, so a single API response
appears on several lines that all carry the same ``message.id`` and the same
``usage``. Usage is counted once per message id, across all files, which also
covers resumed sessions that copy earlier history into a new file.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from tokenguard.models import ToolOutput, UsageRecord
from tokenguard.sources import content_chars, iter_jsonl, parse_ts, project_name

SOURCE = "claude-code"


def default_root() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "projects"


def find_files(root: Path | None = None) -> list[Path]:
    root = root or default_root()
    return sorted(root.rglob("*.jsonl")) if root.is_dir() else []


def parse(files: Iterable[Path]) -> tuple[list[UsageRecord], list[ToolOutput]]:
    records: dict[str, UsageRecord] = {}
    tool_names: dict[str, str] = {}  # tool_use id -> tool name
    seen_tool_ids: set[str] = set()
    seen_result_ids: set[str] = set()
    outputs: list[ToolOutput] = []

    for path in files:
        for entry in iter_jsonl(path):
            kind = entry.get("type")
            msg = entry.get("message")
            if not isinstance(msg, dict):
                continue
            session_id = entry.get("sessionId") or path.stem
            project = project_name(entry.get("cwd"))

            if kind == "assistant":
                _handle_assistant(entry, msg, session_id, project, records, tool_names, seen_tool_ids)
            elif kind == "user" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    tool_id = block.get("tool_use_id")
                    if not tool_id or tool_id in seen_result_ids:
                        continue
                    seen_result_ids.add(tool_id)
                    outputs.append(
                        ToolOutput(
                            source=SOURCE,
                            session_id=session_id,
                            project=project,
                            tool=tool_names.get(tool_id, "unknown"),
                            chars=content_chars(block.get("content")),
                        )
                    )

    return list(records.values()), outputs


def _handle_assistant(entry, msg, session_id, project, records, tool_names, seen_tool_ids) -> None:
    msg_id = msg.get("id") or entry.get("requestId") or entry.get("uuid")
    model = msg.get("model") or "unknown"
    usage = msg.get("usage")

    rec = records.get(msg_id)
    if rec is None and isinstance(usage, dict) and model != "<synthetic>":
        ts = parse_ts(entry.get("timestamp"))
        if ts is not None:
            rec = _record_from_usage(usage, model, session_id, project, ts)
            if rec.total_tokens > 0:
                records[msg_id] = rec
            else:
                rec = None

    for block in msg.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tool_id = block.get("id")
            name = block.get("name") or "unknown"
            if tool_id:
                tool_names[tool_id] = name
                if tool_id in seen_tool_ids:
                    continue
                seen_tool_ids.add(tool_id)
            if rec is not None:
                rec.tool_calls.append(name)


def _record_from_usage(usage: dict, model: str, session_id: str, project: str, ts) -> UsageRecord:
    cache_total = int(usage.get("cache_creation_input_tokens") or 0)
    split = usage.get("cache_creation") or {}
    write_1h = int(split.get("ephemeral_1h_input_tokens") or 0)
    write_5m = int(split.get("ephemeral_5m_input_tokens") or 0)
    if write_1h + write_5m != cache_total:
        # Older logs have no split; the 5-minute cache was the only option then.
        write_5m = cache_total - write_1h

    details = usage.get("output_tokens_details") or {}
    server_tools = usage.get("server_tool_use") or {}
    geo = usage.get("inference_geo")

    return UsageRecord(
        source=SOURCE,
        provider="anthropic",
        model=model,
        session_id=session_id,
        timestamp=ts,
        project=project,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_write_5m_tokens=max(write_5m, 0),
        cache_write_1h_tokens=write_1h,
        cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        reasoning_tokens=int(details.get("thinking_tokens") or 0),
        web_search_requests=int(server_tools.get("web_search_requests") or 0),
        speed=usage.get("speed") or "standard",
        inference_geo=geo if geo in ("us", "global") else None,
    )
