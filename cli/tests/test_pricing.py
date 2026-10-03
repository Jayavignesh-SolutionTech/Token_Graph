from datetime import datetime, timezone

import pytest

from tokenguard.models import UsageRecord
from tokenguard.pricing import PriceTable, normalize_model
from tokenguard.report import summarize

TS = datetime(2026, 10, 1, tzinfo=timezone.utc)


def rec(**kw):
    base = dict(source="claude-code", provider="anthropic", model="claude-opus-5-5",
                session_id="s", timestamp=TS, project="p")
    base.update(kw)
    return UsageRecord(**base)


@pytest.fixture
def prices():
    return PriceTable.load(user_path=None)


@pytest.mark.parametrize("raw,expected", [
    ("claude-opus-4-5-20251101", "claude-opus-4-5"),
    ("claude-opus-5-5[1m]", "claude-opus-5-5"),
    ("us.anthropic.claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),
    ("claude-opus-4-5@20251101", "claude-opus-4-5"),
    ("GPT-5.5", "gpt-5.5"),
])
def test_normalize_model(raw, expected):
    assert normalize_model(raw) == expected


def test_opus_5_5_cost_uses_every_rate(prices):
    r = rec(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000,
            cache_write_5m_tokens=1_000_000, cache_write_1h_tokens=1_000_000)
    # 4 + 20 + 0.20 + 5 + 8
    assert prices.cost(r).usd == pytest.approx(37.20)


def test_modifiers_fast_geo_and_web_search(prices):
    r = rec(input_tokens=1_000_000, speed="fast", inference_geo="us", web_search_requests=3)
    assert prices.cost(r).usd == pytest.approx(4.0 * 2.0 * 1.1 + 0.03)


def test_openai_cached_input(prices):
    r = rec(provider="openai", model="gpt-5.5", input_tokens=1_000_000, cache_read_tokens=1_000_000,
            output_tokens=1_000_000)
    assert prices.cost(r).usd == pytest.approx(5.0 + 0.5 + 30.0)


def test_unknown_model_is_flagged_not_guessed(prices):
    c = prices.cost(rec(provider="openai", model="codex-auto-review", input_tokens=1000))
    assert c.priced is False and c.usd == 0.0


def test_user_override_file(tmp_path):
    override = tmp_path / "pricing.toml"
    override.write_text('[openai."codex-auto-review"]\ninput = 1.0\ncache_read = 0.1\noutput = 2.0\n')
    table = PriceTable.load(user_path=override)
    assert table.cost(rec(provider="openai", model="codex-auto-review", input_tokens=1_000_000)).usd == 1.0
    assert table.get("anthropic", "claude-opus-5-5") is not None  # bundled prices kept


def test_summarize_groups_and_cache_hit_rate(prices):
    records = [
        rec(model="claude-opus-5-5", input_tokens=100, cache_read_tokens=900),
        rec(model="claude-haiku-4-5", input_tokens=1000),
    ]
    buckets, total = summarize(records, prices, "model")
    assert {b.key for b in buckets} == {"claude-opus-5-5", "claude-haiku-4-5"}
    assert total.calls == 2
    opus = next(b for b in buckets if b.key == "claude-opus-5-5")
    assert opus.cache_hit_rate == pytest.approx(0.9)
