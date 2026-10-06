"""Scan a repository and build its code map. Runs locally; uses no LLM tokens."""

from __future__ import annotations

import os
import posixpath
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tokenguard.graph import lang_docs, lang_js, lang_python
from tokenguard.graph.facts import FileFacts, Symbol, file_id
from tokenguard.graph.model import (
    CALLS, CLASS, CONTAINS, DOC, EXACT, FILE, IMPORTS, INFERRED, INHERITS, MENTIONS, METHOD, SYMBOL_KINDS,
    Edge, Graph, Node,
)
from tokenguard.graph.tokens import estimate_tokens

MAX_FILE_BYTES = 1_000_000
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", "out",
    ".next", ".nuxt", ".svelte-kit", "coverage", ".tokenguard", "site-packages", ".mypy_cache",
    ".pytest_cache", ".tox", ".ruff_cache", "vendor", "target", ".turbo", ".vercel", ".idea", ".vscode",
}
# Method names so common on built-in types that a unique-name match would be a guess.
_COMMON_METHODS = set(
    "get set add pop put push map filter reduce then catch finally log error warn info debug append extend "
    "insert remove delete update clear copy keys values items join split strip replace format lower upper "
    "read write close open send emit on off once find findall match search test exec has includes index "
    "indexof slice splice sort reverse count next tostring tojson json text call apply bind foreach some "
    "every startswith endswith encode decode load loads dump dumps parse run start stop init setup".split()
)

_EXTRACTORS = [(lang_python.EXTENSIONS, lang_python.extract), (lang_js.EXTENSIONS, lang_js.extract),
               (lang_docs.EXTENSIONS, lang_docs.extract)]


def _extractor_for(path: str):
    lower = path.lower()
    if lower.endswith((".min.js", ".d.ts", ".bundle.js")):
        return None
    for exts, fn in _EXTRACTORS:
        if lower.endswith(exts):
            return fn
    return None


def list_files(root: Path) -> list[str]:
    """Repo-relative paths (forward slashes) of files we can parse. Honours .gitignore when in git."""
    paths: list[str] = []
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True, check=True, timeout=60,
        ).stdout.decode("utf-8", errors="replace")
        paths = [p for p in out.split("\0") if p]
    except (OSError, subprocess.SubprocessError):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
            rel = Path(dirpath).relative_to(root)
            paths.extend((rel / f).as_posix() for f in filenames)
    result = []
    for p in paths:
        if any(part in EXCLUDED_DIRS for part in p.split("/")[:-1]):
            continue
        if _extractor_for(p) is None:
            continue
        full = root / p
        try:
            if full.is_file() and full.stat().st_size <= MAX_FILE_BYTES:
                result.append(p)
        except OSError:
            continue
    return sorted(set(result))


def build_graph(root: Path) -> Graph:
    started = time.perf_counter()
    root = root.resolve()
    facts: list[FileFacts] = []
    source_tokens = 0
    for rel in list_files(root):
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        extractor = _extractor_for(rel)
        if extractor is None:
            continue
        facts.append(extractor(rel, text))
        if not rel.lower().endswith(lang_docs.EXTENSIONS):
            source_tokens += estimate_tokens(text)

    graph = Graph(root=str(root), generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _Resolver(graph, facts).run()
    graph.dedupe_edges()

    graph.stats = {
        "files": Counter(f.lang for f in facts),
        "nodes": Counter(n.kind for n in graph.nodes.values()),
        "edges": Counter(e.kind for e in graph.edges),
        "edges_inferred": sum(1 for e in graph.edges if e.confidence == INFERRED),
        "source_tokens": source_tokens,
        "scan_seconds": round(time.perf_counter() - started, 2),
        "llm_tokens": 0,
    }
    graph.stats = {k: dict(v) if isinstance(v, Counter) else v for k, v in graph.stats.items()}
    return graph


class _Resolver:
    def __init__(self, graph: Graph, facts: list[FileFacts]):
        self.g = graph
        self.facts = facts
        self.symbols: dict[str, Symbol] = {}
        self.top_level: dict[str, dict[str, str]] = defaultdict(dict)  # file path -> name -> symbol id
        self.members: dict[str, dict[str, str]] = defaultdict(dict)  # class id -> member name -> symbol id
        self.by_name: dict[str, list[str]] = defaultdict(list)  # name -> symbol ids (all kinds)
        self.by_qual: dict[str, list[str]] = defaultdict(list)  # qualname -> symbol ids, e.g. "app.handle"
        self.py_modules: dict[str, str] = {}  # dotted module -> file path
        self.js_files: set[str] = set()
        self.bindings: dict[str, dict[str, str]] = defaultdict(dict)  # file path -> local name -> node id
        self.class_bases: dict[str, list[str]] = defaultdict(list)

    # --- phase 1: nodes ---------------------------------------------------------
    def run(self) -> None:
        for f in self.facts:
            self.g.add_node(Node(id=file_id(f.path), kind=FILE, name=f.path.rsplit("/", 1)[-1], file=f.path, lang=f.lang))
            if f.lang == "python":
                self._register_py_module(f.path)
            elif f.lang in ("javascript", "typescript"):
                self.js_files.add(f.path)
            for s in f.symbols:
                self.symbols[s.id] = s
                self.g.add_node(Node(id=s.id, kind=s.kind, name=s.name, file=f.path, lang=f.lang, qualname=s.qualname,
                                     line=s.line, end_line=s.end_line, signature=s.signature, doc=s.doc))
                self.g.add_edge(Edge(s.parent, s.id, CONTAINS))
                self.by_name[s.name].append(s.id)
                self.by_qual[s.qualname].append(s.id)
                if s.parent == file_id(f.path):
                    self.top_level[f.path].setdefault(s.name, s.id)
                elif s.parent in self.symbols and self.symbols[s.parent].kind == CLASS:
                    self.members[s.parent].setdefault(s.name, s.id)
            for d in f.docs:
                self.g.add_node(Node(id=d.id, kind=DOC, name=d.name, file=f.path, lang=f.lang, qualname=d.qualname,
                                     line=d.line, end_line=d.end_line, doc=d.doc))
                self.g.add_edge(Edge(file_id(f.path), d.id, CONTAINS))

        # --- phase 2: imports -> bindings and file->file edges -------------------
        for f in self.facts:
            for imp in f.imports:
                target_file, bound = self._resolve_import(f, imp)
                if target_file:
                    self.g.add_edge(Edge(file_id(f.path), file_id(target_file), IMPORTS))
                if bound and imp.local:
                    self.bindings[f.path][imp.local] = bound

        # --- phase 3: inheritance (needed before self/super resolution) ----------
        for f in self.facts:
            for b in f.bases:
                hit = self._resolve_ref(f, b.cls, b.target, want_class=True)
                if hit:
                    self.g.add_edge(Edge(b.cls, hit[0], INHERITS, hit[1]))
                    self.class_bases[b.cls].append(hit[0])

        # --- phase 4: calls --------------------------------------------------------
        for f in self.facts:
            for c in f.calls:
                hit = self._resolve_ref(f, c.caller, c.target)
                if hit and self.g.nodes[hit[0]].kind in SYMBOL_KINDS:
                    self.g.add_edge(Edge(c.caller, hit[0], CALLS, hit[1]))

        # --- phase 5: doc mentions ---------------------------------------------------
        for f in self.facts:
            for doc_id, span in f.mentions:
                for target, conf in self._resolve_mention(span):
                    self.g.add_edge(Edge(doc_id, target, MENTIONS, conf))

    # --- modules ------------------------------------------------------------------
    def _register_py_module(self, path: str) -> None:
        mod = path[:-3] if path.endswith(".py") else path[:-4]
        if mod.endswith("/__init__"):
            mod = mod[: -len("/__init__")]
        dotted = mod.replace("/", ".")
        self.py_modules.setdefault(dotted, path)
        for prefix in ("src.", "lib.", "python."):
            if dotted.startswith(prefix):
                self.py_modules.setdefault(dotted[len(prefix):], path)

    def _py_module_file(self, dotted: str) -> str | None:
        if dotted in self.py_modules:
            return self.py_modules[dotted]
        matches = [p for m, p in self.py_modules.items() if m.endswith("." + dotted)]
        return matches[0] if len(set(matches)) == 1 else None

    def _js_module_file(self, from_path: str, spec: str) -> str | None:
        if spec.startswith("."):
            base = posixpath.normpath(posixpath.join(posixpath.dirname(from_path), spec))
            candidates = [base] + [base + e for e in lang_js.EXTENSIONS] + [f"{base}/index{e}" for e in lang_js.EXTENSIONS]
            return next((c for c in candidates if c in self.js_files), None)
        if spec[:2] in ("@/", "~/"):  # common tsconfig path alias for the project root
            rest = spec[2:]
            suffixes = [rest + e for e in lang_js.EXTENSIONS] + [f"{rest}/index{e}" for e in lang_js.EXTENSIONS]
            matches = {p for p in self.js_files for s in suffixes if p == s or p.endswith("/" + s)}
            return next(iter(matches)) if len(matches) == 1 else None
        return None  # package import: outside the repo

    def _resolve_import(self, f: FileFacts, imp) -> tuple[str | None, str | None]:
        """Return (imported file, node bound to the local name)."""
        if f.lang == "python":
            dotted = imp.module
            if imp.level:
                pkg = f.path.rsplit("/", 1)[0].replace("/", ".") if "/" in f.path else ""
                if f.path.endswith("__init__.py"):
                    pkg = f.path[: -len("/__init__.py")].replace("/", ".")
                for _ in range(imp.level - 1):
                    pkg = pkg.rsplit(".", 1)[0] if "." in pkg else ""
                dotted = ".".join(p for p in (pkg, imp.module) if p)
            if imp.name is None:
                target = self._py_module_file(dotted)
                return target, file_id(target) if target else None
            module_file = self._py_module_file(dotted) if dotted else None
            if module_file and imp.name in self.top_level[module_file]:
                return module_file, self.top_level[module_file][imp.name]
            sub = self._py_module_file(f"{dotted}.{imp.name}" if dotted else imp.name)
            if sub:
                return sub, file_id(sub)
            return module_file, file_id(module_file) if module_file else None

        target = self._js_module_file(f.path, imp.module)
        if not target:
            return None, None
        if imp.name is None:
            return target, file_id(target)
        tops = self.top_level[target]
        if imp.name == "default":
            if imp.local in tops:
                return target, tops[imp.local]
            if len(tops) == 1:
                return target, next(iter(tops.values()))
            return target, file_id(target)
        return target, tops.get(imp.name, file_id(target))

    # --- references -----------------------------------------------------------------
    def _enclosing_class(self, scope: str) -> str | None:
        while scope in self.symbols:
            sym = self.symbols[scope]
            if sym.kind == CLASS:
                return sym.id
            scope = sym.parent
        return None

    def _member(self, class_id: str, name: str, seen: set[str] | None = None) -> str | None:
        seen = seen or set()
        if class_id in seen:
            return None
        seen.add(class_id)
        if name in self.members.get(class_id, {}):
            return self.members[class_id][name]
        for base in self.class_bases.get(class_id, []):
            hit = self._member(base, name, seen)
            if hit:
                return hit
        return None

    def _resolve_ref(self, f: FileFacts, scope: str, text: str, want_class: bool = False) -> tuple[str, str] | None:
        parts = text.split(".")
        head = parts[0]
        bindings = self.bindings.get(f.path, {})
        tops = self.top_level.get(f.path, {})

        if head in ("self", "this", "cls") and len(parts) == 2:
            cls = self._enclosing_class(scope)
            if cls:
                hit = self._member(cls, parts[1])
                return (hit, EXACT) if hit else None
            # JS objects built by assignment: inside app.use, this.handle means app.handle
            owner = self.symbols[scope].qualname.rsplit(".", 1)[0] if scope in self.symbols else ""
            if owner and owner != self.symbols[scope].qualname:
                return self._by_qualname(f"{owner}.{parts[1]}", f.path)
            return None
        if head == "super" and len(parts) == 2:
            cls = self._enclosing_class(scope)
            for base in self.class_bases.get(cls or "", []):
                hit = self._member(base, parts[1])
                if hit:
                    return hit, EXACT
            return None

        if len(parts) == 1:
            if head in tops:
                return tops[head], EXACT
            if head in bindings:
                return bindings[head], EXACT
            if head in f.shadows or any(i.local == head for i in f.imports):
                return None  # a local variable or a package import, not a repo symbol
            return self._unique(head, want_class)

        # dotted: a symbol defined under exactly this name (app.handle, res.send)
        hit = self._by_qualname(text.replace(".prototype.", "."), f.path)
        if hit:
            return hit
        # otherwise resolve the head, then walk members
        base = tops.get(head) or bindings.get(head)
        if base:
            node = self.g.nodes.get(base)
            if node and node.kind == FILE:
                target = self.top_level.get(node.file, {}).get(parts[1])
                if target and len(parts) == 2:
                    return target, EXACT
                if target and len(parts) == 3 and self.symbols.get(target, None) and self.symbols[target].kind == CLASS:
                    hit = self._member(target, parts[2])
                    return (hit, EXACT) if hit else None
            elif node and node.kind == CLASS and len(parts) == 2:
                hit = self._member(base, parts[1])
                return (hit, EXACT) if hit else None
            return None
        if want_class:
            return self._unique(parts[-1], want_class=True)
        last = parts[-1]
        if len(last) >= 4 and last.lower() not in _COMMON_METHODS:
            ids = [i for i in self.by_name.get(last, []) if self.symbols[i].kind == METHOD]
            if len(ids) == 1:
                return ids[0], INFERRED
        return None

    def _by_qualname(self, qual: str, from_path: str) -> tuple[str, str] | None:
        ids = self.by_qual.get(qual, [])
        local = [i for i in ids if i.startswith(from_path + "::")]
        if local:
            return local[0], EXACT
        return (ids[0], INFERRED) if len(ids) == 1 else None

    def _unique(self, name: str, want_class: bool = False) -> tuple[str, str] | None:
        kinds = {CLASS, "interface"} if want_class else {CLASS, "function"}
        ids = [i for i in self.by_name.get(name, []) if self.symbols[i].kind in kinds
               and self.symbols[i].parent.startswith("file:")]
        return (ids[0], INFERRED) if len(ids) == 1 else None

    def _resolve_mention(self, span: str) -> list[tuple[str, str]]:
        text = span.strip().rstrip("()").strip()
        if not text or " " in text or len(text) < 3:
            return []
        if "/" in text or text.lower().endswith((*lang_python.EXTENSIONS, *lang_js.EXTENSIONS)):
            norm = text.lstrip("./")
            hits = [n.id for n in self.g.nodes.values() if n.kind == FILE and (n.file == norm or n.file.endswith("/" + norm))]
            return [(h, EXACT) for h in hits[:3]]
        quals = [s.id for s in self.symbols.values() if s.qualname == text]
        if quals:
            return [(q, EXACT) for q in quals[:3]]
        name = text.rsplit(".", 1)[-1]
        if len(name) < 4:
            return []
        ids = self.by_name.get(name, [])
        if 0 < len(ids) <= 3:
            return [(i, EXACT if len(ids) == 1 else INFERRED) for i in ids]
        return []
