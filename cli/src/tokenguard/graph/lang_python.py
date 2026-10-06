"""Python extractor using the standard-library ``ast`` module (exact, no dependencies)."""

from __future__ import annotations

import ast

from tokenguard.graph.facts import BaseFact, CallFact, FileFacts, ImportFact, Symbol, file_id, symbol_id
from tokenguard.graph.model import CLASS, FUNCTION, METHOD

EXTENSIONS = (".py", ".pyi")


def extract(path: str, source: str) -> FileFacts:
    facts = FileFacts(path=path, lang="python")
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError):
        return facts
    _Visitor(facts).visit(tree)
    return facts


def _expr_text(node: ast.AST) -> str | None:
    """Dotted text for Name / Attribute chains (``a.b.c``); None for anything dynamic."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):  # super().method -> "super.method"
        inner = _expr_text(node.func)
        if inner == "super":
            parts.append("super")
            return ".".join(reversed(parts))
    return None


def _first_line(doc: str | None) -> str:
    if not doc:
        return ""
    for line in doc.strip().splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


class _Visitor(ast.NodeVisitor):
    def __init__(self, facts: FileFacts):
        self.f = facts
        self.fid = file_id(facts.path)
        self.stack: list[Symbol] = []  # enclosing classes/functions

    @property
    def scope(self) -> str:
        return self.stack[-1].id if self.stack else self.fid

    def _qual(self, name: str) -> str:
        return ".".join([s.name for s in self.stack] + [name])

    # --- definitions ------------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qual = self._qual(node.name)
        sym = Symbol(
            id=symbol_id(self.f.path, qual), kind=CLASS, name=node.name, qualname=qual,
            line=node.lineno, end_line=node.end_lineno or node.lineno, parent=self.scope,
            signature=f"class {node.name}({', '.join(filter(None, (_expr_text(b) for b in node.bases)))})",
            doc=_first_line(ast.get_docstring(node)),
        )
        self.f.symbols.append(sym)
        for base in node.bases:
            text = _expr_text(base)
            if text and text != "object":
                self.f.bases.append(BaseFact(cls=sym.id, target=text))
        for deco in node.decorator_list:
            self.visit(deco)
        self.stack.append(sym)
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qual = self._qual(node.name)
        in_class = bool(self.stack) and self.stack[-1].kind == CLASS
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        try:
            args = ast.unparse(node.args)
        except Exception:  # pragma: no cover - very old/odd syntax
            args = "..."
        sym = Symbol(
            id=symbol_id(self.f.path, qual), kind=METHOD if in_class else FUNCTION, name=node.name,
            qualname=qual, line=node.lineno, end_line=node.end_lineno or node.lineno, parent=self.scope,
            signature=f"{prefix} {node.name}({args})"[:240], doc=_first_line(ast.get_docstring(node)),
        )
        self.f.symbols.append(sym)
        for deco in node.decorator_list:
            self.visit(deco)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        self.stack.append(sym)
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    # --- references -------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        text = _expr_text(node.func)
        if text:
            self.f.calls.append(CallFact(caller=self.scope, target=text))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            module = alias.name if alias.asname else alias.name.split(".")[0]
            self.f.imports.append(ImportFact(module=module, name=None, local=local))
            if not alias.asname and "." in alias.name:
                # "import a.b" also makes the submodule reachable as a.b
                self.f.imports.append(ImportFact(module=alias.name, name=None, local=alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            self.f.imports.append(
                ImportFact(module=node.module or "", name=alias.name, local=alias.asname or alias.name, level=node.level)
            )
