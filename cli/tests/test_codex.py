from tokenguard.sources import codex


def meta(session="s-1", cwd="/home/dev/api-server"):
    return {"type": "session_meta", "timestamp": "2026-10-01T09:00:00Z",
            "payload": {"id": session, "cwd": cwd, "model_provider": "openai"}}


def turn(model):
    return {"type": "turn_context", "timestamp": "2026-10-01T09:00:01Z", "payload": {"model": model}}


def tokens(inp, cached, out, reasoning=0, ts="2026-10-01T09:00:10Z"):
    total = {"input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out,
             "reasoning_output_tokens": reasoning, "total_tokens": inp + out}
    return {"type": "event_msg", "timestamp": ts,
            "payload": {"type": "token_count", "info": {"total_token_usage": total, "last_token_usage": total}}}


def test_running_totals_become_deltas(write_jsonl):
    path = write_jsonl("2026/10/01/rollout-a.jsonl", [
        meta(), turn("gpt-5.5"),
        tokens(9000, 7000, 100, 40),
        tokens(9000, 7000, 100, 40),  # same total emitted twice
        tokens(15000, 12000, 300, 90),
    ])
    records, _ = codex.parse([path])

    assert len(records) == 2
    first, second = records
    assert (first.input_tokens, first.cache_read_tokens, first.output_tokens) == (2000, 7000, 100)
    assert (second.input_tokens, second.cache_read_tokens, second.output_tokens) == (1000, 5000, 200)
    assert second.reasoning_tokens == 50
    assert first.project == "api-server"
    assert first.session_id == "s-1"


def test_model_switch_is_attributed_per_turn(write_jsonl):
    path = write_jsonl("r.jsonl", [
        meta(), turn("gpt-5.5"), tokens(1000, 0, 10),
        turn("gpt-5.4-mini"), tokens(3000, 0, 30),
    ])
    records, _ = codex.parse([path])
    assert [r.model for r in records] == ["gpt-5.5", "gpt-5.4-mini"]


def test_null_info_is_ignored(write_jsonl):
    path = write_jsonl("r.jsonl", [
        meta(), turn("gpt-5.5"),
        {"type": "event_msg", "timestamp": "2026-10-01T09:00:02Z", "payload": {"type": "token_count", "info": None}},
    ])
    records, _ = codex.parse([path])
    assert records == []


def test_resumed_session_replay_not_double_counted(write_jsonl):
    a = write_jsonl("a.jsonl", [meta(), turn("gpt-5.5"), tokens(1000, 0, 10)])
    b = write_jsonl("b.jsonl", [meta(), turn("gpt-5.5"), tokens(1000, 0, 10), tokens(2500, 0, 25)])
    records, _ = codex.parse([a, b])
    assert sum(r.input_tokens for r in records) == 2500


def test_tool_calls_and_outputs(write_jsonl):
    path = write_jsonl("r.jsonl", [
        meta(), turn("gpt-5.5"),
        {"type": "response_item", "timestamp": "t", "payload": {"type": "function_call", "name": "shell", "call_id": "c1"}},
        {"type": "response_item", "timestamp": "t", "payload": {"type": "function_call_output", "call_id": "c1",
                                                                "output": "y" * 800}},
        tokens(1000, 0, 10),
    ])
    records, outputs = codex.parse([path])
    assert records[0].tool_calls == ["shell"]
    assert outputs[0].tool == "shell"
    assert outputs[0].est_tokens == 200
