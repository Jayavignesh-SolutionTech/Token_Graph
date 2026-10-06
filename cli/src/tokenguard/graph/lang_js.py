"""JavaScript / TypeScript extractor using tree-sitter."""

from __future__ import annotations

from functools import lru_cache

from tree_sitter import Language, Node as TSNode, Parser

from tokenguard.graph.facts import BaseFact, CallFact, FileFacts, ImportFact, Symbol, file_id, symbol_id
from tokenguard.graph.model import CLASS, FUNCTION, INTERFACE, METHOD

EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")

_CLASS_TYPES = {"class_declaration", "abstract_class_declaration", "class"}
_FUNCTION_TYPES = {"function_declaration", "generator_function_declaration"}
_FUNCTION_VALUE_TYPES = {"arrow_function", "function_expression", "function", "generator_function"}


@lru_cache(maxsize=None)
def _parser(dialect: str) -> Parser:
    if dialect in ("ts", "tsx"):
        import tree_sitter_typescript as tsts

        lang = tsts.language_tsx() if dialect == "tsx" else tsts.language_typescript()
    else:
        import tree_sitter_javascript as tsjs

        lang = tsjs.language()
    return Parser(Language(lang))


def _dialect(path: str) -> tuple[str, str]:
    lower = path.lower()
    if lower.endswith(".tsx"):
        return "tsx", "typescript"
    if lower.endswith((".ts", ".mts", ".cts")):
        return "ts", "typescript"
    return "js", "javascript"  # the JS grammar also parses JSX


def extract(path: str, source: str) -> FileFacts:
    dialect, lang = _dialect(path)
    facts = FileFacts(path=path, lang=lang)
    tree = _parser(dialect).parse(source.encode("utf-8", errors="replace"))
    _Walker(facts).walk(tree.root_node, scope=None)
    return facts


def _text(node: TSNode | None) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None and node.text is not None else ""


def _expr_text(node: TSNode | None) -> str | None:
    """Dotted text for identifiers and member chains: ``foo``, ``this.save``, ``api.auth.login``."""
    if node is None:
        return None
    if node.type in ("identifier", "type_identifier", "property_identifier", "this", "super"):
        return _text(node)
    if node.type == "member_expression":
        obj = _expr_text(node.child_by_field_name("object"))
        prop = node.child_by_field_name("property")
        if obj and prop is not None:
            return f"{obj}.{_text(prop)}"
    return None


def _string_value(node: TSNode | None) -> str | None:
    if node is None or node.type not in ("string", "template_string"):
        return None
    return _text(node).strip("'\"`")


def _leading_comment(node: TSNode) -> str:
    prev = node.prev_named_sibling
    if prev is None and node.parent is not None and node.parent.type == "export_statement":
        prev = node.parent.prev_named_sibling
    if prev is None or prev.type != "comment":
        return ""
    lines = [ln.strip().lstrip("/*").strip() for ln in _text(prev).splitlines()]
    return next((ln for ln in lines if ln and not ln.startswith("@")), "")[:200]


class _Walker:
    def __init__(self, facts: FileFacts):
        self.f = facts
        self.fid = file_id(facts.path)
        self.stack: list[Symbol] = []

    def _scope(self) -> str:
        return self.stack[-1].id if self.stack else self.fid

    def _qual(self, name: str) -> str:
        return ".".join([s.name for s in self.stack] + [name])

    def _add_symbol(self, node: TSNode, kind: str, name: str, signature: str, qualname: str | None = None) -> Symbol:
        qual = qualname if qualname and not self.stack else self._qual(qualname or name)
        sym = Symbol(
            id=symbol_id(self.f.path, qual), kind=kind, name=name, qualname=qual,
            line=node.start_point[0] + 1, end_line=node.end_point[0] + 1, parent=self._scope(),
            signature=" ".join(signature.split())[:240], doc=_leading_comment(node),
        )
        self.f.symbols.append(sym)
        return sym

    def _body_walk(self, sym: Symbol, body: TSNode | None) -> None:
        if body is None:
            return
        self.stack.append(sym)
        self.walk(body, scope=sym)
        self.stack.pop()

    def walk(self, node: TSNode, scope: Symbol | None) -> None:
        t = node.type

        if t in _CLASS_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _text(name_node)
                sym = self._add_symbol(node, CLASS, name, f"class {name}")
                for child in node.children:
                    if child.type == "class_heritage":
                        self._heritage(sym, child)
                self._body_walk(sym, node.child_by_field_name("body"))
                return

        if t == "interface_declaration":
            name = _text(node.child_by_field_name("name"))
            if name:
                sym = self._add_symbol(node, INTERFACE, name, f"interface {name}")
                for child in node.children:
                    if child.type == "extends_type_clause":
                        for ident in child.named_children:
                            text = _expr_text(ident)
                            if text:
                                self.f.bases.append(BaseFact(cls=sym.id, target=text))
                return

        if t in _FUNCTION_TYPES:
            name = _text(node.child_by_field_name("name"))
            if name:
                params = _text(node.child_by_field_name("parameters"))
                sym = self._add_symbol(node, FUNCTION, name, f"function {name}{params}")
                self._body_walk(sym, node.child_by_field_name("body"))
                return

        if t == "method_definition":
            name = _text(node.child_by_field_name("name"))
            if name:
                params = _text(node.child_by_field_name("parameters"))
                kind = METHOD if self.stack and self.stack[-1].kind == CLASS else FUNCTION
                sym = self._add_symbol(node, kind, name, f"{name}{params}")
                self._body_walk(sym, node.child_by_field_name("body"))
                return

        if t == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if value is not None and name_node is not None and name_node.type == "identifier":
                if value.type in _FUNCTION_VALUE_TYPES:
                    name = _text(name_node)
                    params = _text(value.child_by_field_name("parameters") or value.child_by_field_name("parameter"))
                    sym = self._add_symbol(value, FUNCTION, name, f"const {name} = {params} =>")
                    self._body_walk(sym, value.child_by_field_name("body"))
                    return
                self.f.shadows.add(_text(name_node))
                if value.type == "call_expression" and _text(value.child_by_field_name("function")) == "require":
                    spec = _string_value(next(iter(value.child_by_field_name("arguments").named_children), None))
                    if spec:
                        self.f.imports.append(ImportFact(module=spec, name=None, local=_text(name_node)))
                    return

        if t == "assignment_expression":
            # app.use = function use() {} / Foo.prototype.bar = () => {} / module.exports = function () {}
            left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
            target = _expr_text(left)
            if target and right is not None and right.type in _FUNCTION_VALUE_TYPES:
                qual = target.replace(".prototype.", ".")
                if qual in ("module.exports", "exports"):
                    qual = _text(right.child_by_field_name("name")) or self.f.path.rsplit("/", 1)[-1].split(".")[0]
                elif qual.startswith(("module.exports.", "exports.")):
                    qual = qual.split(".", 2)[-1] if qual.startswith("module.") else qual.split(".", 1)[-1]
                name = qual.rsplit(".", 1)[-1]
                params = _text(right.child_by_field_name("parameters"))
                sym = self._add_symbol(right, FUNCTION, name, f"{qual} = function{params}", qualname=qual)
                self._body_walk(sym, right.child_by_field_name("body"))
                return

        if t == "pair":
            # { handle(req, res) {...} } is a method_definition; { handle: function () {...} } is a pair
            key, value = node.child_by_field_name("key"), node.child_by_field_name("value")
            if key is not None and value is not None and value.type in _FUNCTION_VALUE_TYPES:
                name = _text(key).strip("'\"")
                if name.isidentifier():
                    params = _text(value.child_by_field_name("parameters"))
                    sym = self._add_symbol(value, FUNCTION, name, f"{name}: function{params}")
                    self._body_walk(sym, value.child_by_field_name("body"))
                    return

        if t == "import_statement":
            self._import(node)
            return

        if t in ("call_expression", "new_expression"):
            fn = node.child_by_field_name("function" if t == "call_expression" else "constructor")
            text = _expr_text(fn)
            if text and text != "require":
                self.f.calls.append(CallFact(caller=self._scope(), target=text))

        for child in node.named_children:
            self.walk(child, scope)

    def _heritage(self, sym: Symbol, heritage: TSNode) -> None:
        for child in heritage.named_children:
            if child.type == "implements_clause":
                targets = child.named_children
            elif child.type == "extends_clause":
                targets = [child.child_by_field_name("value") or (child.named_children or [None])[0]]
            else:  # plain JS: class_heritage holds the expression directly
                targets = [child]
            for target in targets:
                text = _expr_text(target)
                if text:
                    self.f.bases.append(BaseFact(cls=sym.id, target=text))

    def _import(self, node: TSNode) -> None:
        spec = _string_value(node.child_by_field_name("source"))
        if not spec:
            return
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        if clause is None:
            self.f.imports.append(ImportFact(module=spec, name=None, local=""))
            return
        for part in clause.named_children:
            if part.type == "identifier":
                self.f.imports.append(ImportFact(module=spec, name="default", local=_text(part)))
            elif part.type == "namespace_import":
                ident = next((c for c in part.named_children if c.type == "identifier"), None)
                if ident is not None:
                    self.f.imports.append(ImportFact(module=spec, name=None, local=_text(ident)))
            elif part.type == "named_imports":
                for spec_node in part.named_children:
                    if spec_node.type != "import_specifier":
                        continue
                    name = _text(spec_node.child_by_field_name("name"))
                    alias = _text(spec_node.child_by_field_name("alias")) or name
                    if name:
                        self.f.imports.append(ImportFact(module=spec, name=name, local=alias))
