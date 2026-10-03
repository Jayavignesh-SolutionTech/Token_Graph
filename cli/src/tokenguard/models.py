"""Normalized usage records shared by every log source."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UsageRecord:
    """One billable model call, normalized across tools and providers.

    Token fields are disjoint: ``input_tokens`` never includes cached tokens,
    so cost is a straight sum of each field times its rate.
    """

    source: str  # "claude-code" | "codex"
    provider: str  # "anthropic" | "openai"
    model: str
    session_id: str
    timestamp: datetime
    project: str  # basename of the working directory
    input_tokens: int = 0  # uncached input
    output_tokens: int = 0  # includes thinking / reasoning tokens
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_read_tokens: int = 0
    reasoning_tokens: int = 0  # informational subset of output_tokens
    web_search_requests: int = 0
    speed: str = "standard"  # "standard" | "fast"
    inference_geo: str | None = None
    tool_calls: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_5m_tokens
            + self.cache_write_1h_tokens
            + self.cache_read_tokens
        )


@dataclass
class ToolOutput:
    """Size of one tool result fed back into the model's context."""

    source: str
    session_id: str
    project: str
    tool: str
    chars: int

    @property
    def est_tokens(self) -> int:
        # ~4 characters per token for English text and code; an estimate only.
        return self.chars // 4
