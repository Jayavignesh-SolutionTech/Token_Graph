"""Per-model price table and cost calculation."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from tokenguard.models import UsageRecord

USER_PRICING_PATH = Path.home() / ".tokenguard" / "pricing.toml"

_DATE_SUFFIX = re.compile(r"-\d{8}$")
_BRACKET_SUFFIX = re.compile(r"\[.*\]$")
_PROVIDER_PREFIX = re.compile(r"^(?:[a-z]{2,4}\.)?anthropic\.")  # Bedrock: us.anthropic.claude-...


@dataclass(frozen=True)
class ModelPrice:
    input: float
    output: float
    cache_read: float
    cache_write_5m: float = 0.0
    cache_write_1h: float = 0.0


@dataclass(frozen=True)
class Cost:
    usd: float
    priced: bool  # False when the model is missing from the price table


def normalize_model(model: str) -> str:
    """Map variants like ``claude-opus-4-5-20251101`` or ``claude-opus-5-5[1m]`` to a table key."""
    m = model.strip().lower()
    m = _BRACKET_SUFFIX.sub("", m)
    m = _PROVIDER_PREFIX.sub("", m)
    m = m.split("@", 1)[0]  # Vertex: claude-opus-4-5@20251101
    m = _DATE_SUFFIX.sub("", m)
    return m


class PriceTable:
    def __init__(self, data: dict):
        self._modifiers = data.get("modifiers", {})
        self._prices: dict[tuple[str, str], ModelPrice] = {}
        for provider, models in data.items():
            if provider == "modifiers" or not isinstance(models, dict):
                continue
            for model, p in models.items():
                self._prices[(provider, model)] = ModelPrice(
                    input=p["input"],
                    output=p["output"],
                    cache_read=p.get("cache_read", p["input"]),
                    cache_write_5m=p.get("cache_write_5m", p["input"]),
                    cache_write_1h=p.get("cache_write_1h", p["input"]),
                )

    @classmethod
    def load(cls, user_path: Path | None = USER_PRICING_PATH) -> PriceTable:
        bundled = resources.files("tokenguard.data").joinpath("pricing.toml").read_text(encoding="utf-8")
        data = tomllib.loads(bundled)
        if user_path is not None and user_path.is_file():
            _deep_merge(data, tomllib.loads(user_path.read_text(encoding="utf-8")))
        return cls(data)

    def get(self, provider: str, model: str) -> ModelPrice | None:
        return self._prices.get((provider, normalize_model(model)))

    def cost(self, rec: UsageRecord) -> Cost:
        price = self.get(rec.provider, rec.model)
        if price is None:
            return Cost(0.0, priced=False)
        usd = (
            rec.input_tokens * price.input
            + rec.output_tokens * price.output
            + rec.cache_read_tokens * price.cache_read
            + rec.cache_write_5m_tokens * price.cache_write_5m
            + rec.cache_write_1h_tokens * price.cache_write_1h
        ) / 1_000_000
        mods = self._modifiers.get(rec.provider, {})
        if rec.speed == "fast":
            usd *= mods.get("fast_multiplier", 1.0)
        if rec.inference_geo == "us":
            usd *= mods.get("us_geo_multiplier", 1.0)
        usd += rec.web_search_requests * mods.get("web_search_per_request", 0.0)
        return Cost(usd, priced=True)


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
