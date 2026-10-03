import json
from pathlib import Path

import pytest


@pytest.fixture
def write_jsonl(tmp_path: Path):
    def _write(name: str, entries: list[dict]) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        return path

    return _write
