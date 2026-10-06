"""Graph data model and the graph.json format."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA = "tokenguard.graph/v1"
GRAPH_DIR = ".tokenguard"
GRAPH_FILE = "graph.json"

# Node kinds
FILE, CLASS, FUNCTION, METHOD, INTERFACE, DOC = "file", "class", "function", "method", "interface", "doc"
SYMBOL_KINDS = frozenset({CLASS, FUNCTION, METHOD, INTERFACE})

# Edge kinds
CONTAINS, IMPORTS, CALLS, INHERITS, MENTIONS = "contains", "imports", "calls", "inherits", "mentions"

# Edge confidence: resolved through scope/imports, or matched by a unique name.
EXACT, INFERRED = "exact", "inferred"


@dataclass
class Node:
    id: str
    kind: str
    name: str
    file: str
    lang: str
    qualname: str = ""
    line: int = 0
    end_line: int = 0
    signature: str = ""
    doc: str = ""


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    confidence: str = EXACT


@dataclass
class Graph:
    root: str
    generated_at: str = ""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    # --- indexes (built lazily) ---------------------------------------------
    _out: dict[str, list[Edge]] | None = field(default=None, repr=False)
    _in: dict[str, list[Edge]] | None = field(default=None, repr=False)

    def add_node(self, node: Node) -> None:
        self.nodes.setdefault(node.id, node)

    def add_edge(self, edge: Edge) -> None:
        if edge.src != edge.dst:
            self.edges.append(edge)

    def dedupe_edges(self) -> None:
        best: dict[tuple[str, str, str], Edge] = {}
        for e in self.edges:
            key = (e.src, e.dst, e.kind)
            if key not in best or (best[key].confidence == INFERRED and e.confidence == EXACT):
                best[key] = e
        self.edges = list(best.values())
        self._out = self._in = None

    def _index(self) -> None:
        out: dict[str, list[Edge]] = defaultdict(list)
        inc: dict[str, list[Edge]] = defaultdict(list)
        for e in self.edges:
            out[e.src].append(e)
            inc[e.dst].append(e)
        self._out, self._in = out, inc

    def out_edges(self, node_id: str, kind: str | None = None) -> list[Edge]:
        if self._out is None:
            self._index()
        edges = self._out.get(node_id, [])  # type: ignore[union-attr]
        return [e for e in edges if kind is None or e.kind == kind]

    def in_edges(self, node_id: str, kind: str | None = None) -> list[Edge]:
        if self._in is None:
            self._index()
        edges = self._in.get(node_id, [])  # type: ignore[union-attr]
        return [e for e in edges if kind is None or e.kind == kind]

    def degree(self, node_id: str) -> int:
        return len(self.out_edges(node_id)) + len(self.in_edges(node_id))

    # --- persistence ----------------------------------------------------------
    def to_json(self) -> dict:
        return {
            "schema": SCHEMA,
            "root": self.root,
            "generated_at": self.generated_at,
            "stats": self.stats,
            "nodes": [{k: v for k, v in asdict(n).items() if v not in ("", 0) or k in ("id", "kind")}
                      for n in self.nodes.values()],
            "edges": [[e.src, e.dst, e.kind, e.confidence] for e in self.edges],
        }

    @classmethod
    def from_json(cls, data: dict) -> Graph:
        if data.get("schema") != SCHEMA:
            raise ValueError(f"not a TokenGuard graph (schema {data.get('schema')!r})")
        g = cls(root=data["root"], generated_at=data.get("generated_at", ""), stats=data.get("stats", {}))
        for raw in data["nodes"]:
            g.nodes[raw["id"]] = Node(**{"name": "", "file": "", "lang": "", **raw})
        g.edges = [Edge(*e) for e in data["edges"]]
        return g

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), separators=(",", ":")), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Graph:
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))


def default_graph_path(repo: Path) -> Path:
    return repo / GRAPH_DIR / GRAPH_FILE
