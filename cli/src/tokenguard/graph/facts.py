"""Per-file facts produced by the language extractors, before cross-file resolution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Symbol:
    id: str
    kind: str  # class | function | method | interface
    name: str
    qualname: str
    line: int
    end_line: int
    parent: str  # id of the enclosing symbol or the file
    signature: str = ""
    doc: str = ""


@dataclass
class ImportFact:
    """One imported binding.

    ``module`` is the raw specifier ("os.path", "..utils", "./auth", "react").
    ``name`` is the imported member, or None for "import the module itself".
    ``local`` is the name it is bound to in this file.
    """

    module: str
    name: str | None
    local: str
    level: int = 0  # Python relative-import level


@dataclass
class CallFact:
    caller: str  # symbol id, or the file id for module-level code
    target: str  # callee expression text: "foo", "self.save", "auth.login", "User"


@dataclass
class BaseFact:
    cls: str  # class symbol id
    target: str  # base expression text


@dataclass
class FileFacts:
    path: str  # repo-relative, forward slashes
    lang: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportFact] = field(default_factory=list)
    calls: list[CallFact] = field(default_factory=list)
    bases: list[BaseFact] = field(default_factory=list)
    mentions: list[tuple[str, str]] = field(default_factory=list)  # (doc node id, mentioned text)
    docs: list[Symbol] = field(default_factory=list)  # doc sections (kind "doc")
    shadows: set[str] = field(default_factory=set)  # local non-function names (vars, package imports)


def file_id(path: str) -> str:
    return f"file:{path}"


def symbol_id(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"
