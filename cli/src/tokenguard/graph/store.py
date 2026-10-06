"""Load the code map from disk, rebuilding it when the repository has changed."""

from __future__ import annotations

import time
from pathlib import Path

from tokenguard.graph.build import build_graph, list_files
from tokenguard.graph.model import Graph, default_graph_path


def is_stale(repo: Path, graph_path: Path) -> bool:
    if not graph_path.is_file():
        return True
    built = graph_path.stat().st_mtime
    for rel in list_files(repo):
        try:
            if (repo / rel).stat().st_mtime > built:
                return True
        except OSError:
            continue
    return False


def scan(repo: Path, out: Path | None = None) -> tuple[Graph, Path]:
    repo = repo.resolve()
    out = out or default_graph_path(repo)
    graph = build_graph(repo)
    graph.save(out)
    _ensure_gitignore(out.parent)
    return graph, out


def load(repo: Path, rebuild_if_stale: bool = True) -> Graph:
    repo = repo.resolve()
    path = default_graph_path(repo)
    if rebuild_if_stale and is_stale(repo, path):
        graph, _ = scan(repo, path)
        return graph
    return Graph.load(path)


def _ensure_gitignore(directory: Path) -> None:
    """Keep the generated map out of version control by default."""
    marker = directory / ".gitignore"
    if not marker.exists():
        marker.write_text("*\n", encoding="utf-8")


class LiveGraph:
    """Graph that re-checks for changes at most every ``interval`` seconds (used by the MCP server)."""

    def __init__(self, repo: Path, interval: float = 30.0):
        self.repo = repo.resolve()
        self.interval = interval
        self._graph: Graph | None = None
        self._checked = 0.0

    def get(self) -> Graph:
        now = time.monotonic()
        if self._graph is None or now - self._checked > self.interval:
            self._graph = load(self.repo, rebuild_if_stale=True)
            self._checked = now
        return self._graph
