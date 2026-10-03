from tokenguard.sources import claude_code

USAGE = {
    "input_tokens": 10,
    "cache_creation_input_tokens": 3000,
    "cache_read_input_tokens": 20000,
    "output_tokens": 500,
    "output_tokens_details": {"thinking_tokens": 120},
    "server_tool_use": {"web_search_requests": 1},
    "cache_creation": {"ephemeral_1h_input_tokens": 2000, "ephemeral_5m_input_tokens": 1000},
    "speed": "standard",
}


def assistant(msg_id, content, usage=USAGE, model="claude-opus-5-5", ts="2026-10-01T10:00:00Z"):
    return {
        "type": "assistant",
        "sessionId": "sess-1",
        "cwd": "C:\\Users\\dev\\repos\\my-app",
        "timestamp": ts,
        "message": {"id": msg_id, "model": model, "role": "assistant", "content": content, "usage": usage},
    }


def tool_result(tool_id, text):
    return {
        "type": "user",
        "sessionId": "sess-1",
        "cwd": "C:\\Users\\dev\\repos\\my-app",
        "timestamp": "2026-10-01T10:00:05Z",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text}]},
    }


def test_split_entries_count_usage_once(write_jsonl):
    path = write_jsonl("p/s.jsonl", [
        assistant("msg_1", [{"type": "thinking", "thinking": ""}]),
        assistant("msg_1", [{"type": "text", "text": "Running it."}]),
        assistant("msg_1", [{"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}]),
    ])
    records, _ = claude_code.parse([path])

    assert len(records) == 1
    rec = records[0]
    assert rec.input_tokens == 10
    assert rec.cache_write_1h_tokens == 2000
    assert rec.cache_write_5m_tokens == 1000
    assert rec.cache_read_tokens == 20000
    assert rec.output_tokens == 500
    assert rec.reasoning_tokens == 120
    assert rec.web_search_requests == 1
    assert rec.project == "my-app"
    assert rec.tool_calls == ["Bash"]


def test_resumed_session_in_second_file_is_not_double_counted(write_jsonl):
    first = write_jsonl("p/a.jsonl", [assistant("msg_1", [])])
    second = write_jsonl("p/b.jsonl", [assistant("msg_1", []), assistant("msg_2", [])])
    records, _ = claude_code.parse([first, second])
    assert sorted(r.model for r in records) == ["claude-opus-5-5", "claude-opus-5-5"]
    assert len(records) == 2


def test_tool_results_are_attributed_to_tool_name(write_jsonl):
    path = write_jsonl("p/s.jsonl", [
        assistant("msg_1", [{"type": "tool_use", "id": "tu_1", "name": "Read", "input": {}}]),
        tool_result("tu_1", "x" * 4000),
        tool_result("tu_1", "x" * 4000),  # replayed in a resumed file
    ])
    _, outputs = claude_code.parse([path])
    assert len(outputs) == 1
    assert outputs[0].tool == "Read"
    assert outputs[0].est_tokens == 1000


def test_synthetic_and_zero_usage_messages_are_skipped(write_jsonl):
    zero = {"input_tokens": 0, "output_tokens": 0}
    path = write_jsonl("p/s.jsonl", [
        assistant("msg_1", [], model="<synthetic>"),
        assistant("msg_2", [], usage=zero),
    ])
    records, _ = claude_code.parse([path])
    assert records == []


def test_cache_writes_without_split_count_as_5m(write_jsonl):
    usage = {"input_tokens": 5, "cache_creation_input_tokens": 800, "output_tokens": 50}
    path = write_jsonl("p/s.jsonl", [assistant("msg_1", [], usage=usage)])
    (rec,), _ = claude_code.parse([path])
    assert rec.cache_write_5m_tokens == 800
    assert rec.cache_write_1h_tokens == 0
