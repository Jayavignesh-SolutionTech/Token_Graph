"""Aggregate usage records into cost summaries."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from tokenguard.models import ToolOutput, UsageRecord
from tokenguard.pricing import PriceTable

GROUP_KEYS: dict[str, Callable[[UsageRecord], str]] = {
    "source": lambda r: r.source,
    "model": lambda r: r.model,
    "project": lambda r: r.project,
    "day": lambda r: r.timestamp.astimezone().strftime("%Y-%m-%d"),
    "session": lambda r: f"{r.project} / {r.session_id[:8]}",
}


@dataclass
class Bucket:
    key: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    unpriced_calls: int = 0
    unpriced_models: set[str] = field(default_factory=set)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_write_tokens + self.cache_read_tokens

    @property
    def cache_hit_rate(self) -> float:
        """Share of input-side tokens served from cache."""
        input_side = self.input_tokens + self.cache_write_tokens + self.cache_read_tokens
        return self.cache_read_tokens / input_side if input_side else 0.0

    def add(self, rec: UsageRecord, prices: PriceTable) -> None:
        self.calls += 1
        self.input_tokens += rec.input_tokens
        self.output_tokens += rec.output_tokens
        self.cache_write_tokens += rec.cache_write_5m_tokens + rec.cache_write_1h_tokens
        self.cache_read_tokens += rec.cache_read_tokens
        cost = prices.cost(rec)
        self.cost_usd += cost.usd
        if not cost.priced:
            self.unpriced_calls += 1
            self.unpriced_models.add(rec.model)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "cost_usd": round(self.cost_usd, 6),
            "unpriced_calls": self.unpriced_calls,
            "unpriced_models": sorted(self.unpriced_models),
        }


def summarize(records: Iterable[UsageRecord], prices: PriceTable, by: str) -> tuple[list[Bucket], Bucket]:
    key_fn = GROUP_KEYS[by]
    buckets: dict[str, Bucket] = {}
    total = Bucket("TOTAL")
    for rec in records:
        key = key_fn(rec)
        buckets.setdefault(key, Bucket(key)).add(rec, prices)
        total.add(rec, prices)
    ordered = sorted(buckets.values(), key=lambda b: (b.key if by == "day" else -b.cost_usd, b.key))
    return ordered, total


@dataclass
class ToolBucket:
    tool: str
    results: int = 0
    chars: int = 0
    largest_chars: int = 0

    @property
    def est_tokens(self) -> int:
        return self.chars // 4


def summarize_tools(outputs: Iterable[ToolOutput]) -> list[ToolBucket]:
    buckets: dict[str, ToolBucket] = defaultdict(lambda: ToolBucket(""))
    for out in outputs:
        b = buckets[out.tool]
        b.tool = out.tool
        b.results += 1
        b.chars += out.chars
        b.largest_chars = max(b.largest_chars, out.chars)
    return sorted(buckets.values(), key=lambda b: -b.chars)


def tool_call_counts(records: Iterable[UsageRecord]) -> Counter[str]:
    return Counter(name for rec in records for name in rec.tool_calls)
