"""MCP server exposing the code map to AI coding assistants (Claude Code, Cursor, Codex, ...)."""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from tokenguard.graph import query
from tokenguard.graph.store import LiveGraph

INSTRUCTIONS = """\
TokenGuard keeps a map of this repository: files, classes, functions, docs, and how they call,
import and inherit from each other. Ask the map before searching or reading files:
1. tokenguard_ask("how does X work?") answers most questions about the code in one call.
2. tokenguard_explain / tokenguard_deps / tokenguard_path give exact details for one symbol or file.
Only open a file when the map's answer is not enough, and then read just the line range it gives you.
Edges marked "~" were matched by name and may be wrong."""


def create_server(repo: Path) -> MCPServer:
    live = LiveGraph(repo)
    root = live.repo
    server = MCPServer(name="tokenguard", instructions=INSTRUCTIONS)

    @server.tool()
    def tokenguard_ask(question: str) -> str:
        """Answer a question about this codebase from the code map: the most relevant functions,
        classes and docs with their callers, callees and locations, plus source for the top matches.
        Use this first, before grep or reading files."""
        return query.context(live.get(), question, root=root).text

    @server.tool()
    def tokenguard_search(term: str, limit: int = 15) -> str:
        """Find functions, classes, methods, files or doc sections by (partial) name."""
        hits = query.find(live.get(), term, limit=limit)
        if not hits:
            return f"Nothing in the code map matches {term!r}."
        return "\n".join(f"{n.kind:9} {n.qualname or n.name}  [{n.file}:{n.line}]" if n.line else f"{n.kind:9} {n.file}"
                         for n in hits)

    @server.tool()
    def tokenguard_explain(symbol: str, include_source: bool = False) -> str:
        """Details for one symbol or file: signature, docstring, location, callers, callees,
        inheritance and docs that mention it. Set include_source to also get its code (up to 80 lines)."""
        graph = live.get()
        node = query.resolve(graph, symbol)
        if node is None:
            return f"Nothing in the code map matches {symbol!r}. Try tokenguard_search."
        return query.explain(graph, node, root=root, source_lines=80 if include_source else 0)

    @server.tool()
    def tokenguard_deps(file: str) -> str:
        """Which repository files this file imports, and which files import it."""
        graph = live.get()
        node = query.resolve(graph, file)
        return query.deps(graph, node) if node else f"No file matches {file!r}."

    @server.tool()
    def tokenguard_path(source: str, target: str) -> str:
        """Shortest chain of calls / imports / inheritance connecting two symbols or files."""
        graph = live.get()
        a, b = query.resolve(graph, source), query.resolve(graph, target)
        if a is None or b is None:
            missing = source if a is None else target
            return f"Couldn't find {missing!r} in the code map."
        return query.path(graph, a, b)

    return server


def serve(repo: Path) -> None:
    create_server(repo).run("stdio")
