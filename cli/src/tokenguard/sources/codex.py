"""OpenAI Codex session logs: ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``.

Codex emits ``token_count`` events carrying a running ``total_token_usage`` for
the session; the same total can be emitted more than once. Each record is the
increase over the previous total, attributed to the model from the latest
``turn_context``. OpenAI's ``input_tokens`` includes ``cached_input_tokens`` and
``output_tokens`` includes ``reasoning_output_tokens``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from tokenguard.models import ToolOutput, UsageRecord
from tokenguard.sources import content_chars, iter_jsonl, parse_ts, project_name

SOURCE = "codex"
_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def default_root() -> Path:
    base = os.environ.get("CODEX_HOME")
    return (Path(base) if base else Path.home() / ".codex") / "sessions"


def find_files(root: Path | None = None) -> list[Path]:
    root = root or default_root()
    return sorted(root.rglob("*.jsonl")) if root.is_dir() else []


def parse(files: Iterable[Path]) -> tuple[list[UsageRecord], list[ToolOutput]]:
    records: list[UsageRecord] = []
    outputs: list[ToolOutput] = []
    # Last seen running total per session, shared across files so a resumed
    # session that replays earlier events is not counted twice.
    last_totals: dict[str, dict[str, int]] = {}

    for path in files:
        session_id = path.stem
        project = "unknown"
        model = "unknown"
        call_names: dict[str, str] = {}
        pending_calls: list[str] = []

        for entry in iter_jsonl(path):
            kind = entry.get("type")
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue
            ptype = payload.get("type")

            if kind == "session_meta":
                session_id = payload.get("id") or payload.get("session_id") or session_id
                project = project_name(payload.get("cwd"))
            elif kind == "turn_context":
                model = payload.get("model") or model
                if payload.get("cwd"):
                    project = project_name(payload.get("cwd"))
            elif kind == "response_item" and isinstance(ptype, str):
                if ptype.endswith("_call") and payload.get("call_id"):
                    name = payload.get("name") or ptype.removesuffix("_call")
                    call_names[payload["call_id"]] = name
                    pending_calls.append(name)
                elif ptype.endswith("_call_output") and payload.get("call_id"):
                    outputs.append(
                        ToolOutput(
                            source=SOURCE,
                            session_id=session_id,
                            project=project,
                            tool=call_names.get(payload["call_id"], "unknown"),
                            chars=content_chars(payload.get("output")),
                        )
                    )
            elif kind == "event_msg" and ptype == "token_count":
                info = payload.get("info")
                total = info.get("total_token_usage") if isinstance(info, dict) else None
                ts = parse_ts(entry.get("timestamp"))
                if not isinstance(total, dict) or ts is None:
                    continue
                current = {k: int(total.get(k) or 0) for k in _FIELDS}
                prev = last_totals.get(session_id, dict.fromkeys(_FIELDS, 0))
                delta = {k: current[k] - prev[k] for k in _FIELDS}
                if delta["input_tokens"] <= 0 and delta["output_tokens"] <= 0:
                    continue  # repeated or replayed total
                last_totals[session_id] = current

                cached = max(delta["cached_input_tokens"], 0)
                records.append(
                    UsageRecord(
                        source=SOURCE,
                        provider="openai",
                        model=model,
                        session_id=session_id,
                        timestamp=ts,
                        project=project,
                        input_tokens=max(delta["input_tokens"] - cached, 0),
                        cache_read_tokens=cached,
                        output_tokens=max(delta["output_tokens"], 0),
                        reasoning_tokens=max(delta["reasoning_output_tokens"], 0),
                        tool_calls=pending_calls,
                    )
                )
                pending_calls = []

    return records, outputs
