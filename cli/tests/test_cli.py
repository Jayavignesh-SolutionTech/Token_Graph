import json

from typer.testing import CliRunner

from tokenguard.cli import app


def test_export_writes_every_breakdown(tmp_path, monkeypatch, write_jsonl):
    claude_root = tmp_path / "claude"
    write_jsonl("claude/projects/p/s.jsonl", [{
        "type": "assistant", "sessionId": "s1", "cwd": "/x/my-app", "timestamp": "2026-10-01T10:00:00Z",
        "message": {"id": "m1", "model": "claude-opus-5-5", "content": [],
                    "usage": {"input_tokens": 1_000_000, "output_tokens": 0}},
    }])
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_root))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))

    out = tmp_path / "export.json"
    result = CliRunner().invoke(app, ["export", "-o", str(out)])
    assert result.exit_code == 0, result.output

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == "tokenguard.export/v1"
    assert data["total"]["cost_usd"] == 4.0
    assert data["by_model"][0]["key"] == "claude-opus-5-5"
    assert data["by_project"][0]["key"] == "my-app"
    assert len(data["by_day"]) == 1  # key is the local date, so it depends on the machine's timezone
    assert data["by_source"][0]["key"] == "claude-code"
    assert data["tools"] == []
