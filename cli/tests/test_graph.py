"""Code map: extraction, resolution, queries and the with/without benchmark on a tiny mixed repo."""

from pathlib import Path

import pytest

from tokenguard.graph import query
from tokenguard.graph.bench import auto_questions, run_bench
from tokenguard.graph.build import build_graph
from tokenguard.graph.model import CALLS, IMPORTS, INHERITS, MENTIONS, Graph

FILES = {
    "app/auth.py": '''
"""Authentication helpers."""
from app.db import Database


class BaseUser:
    def save(self):
        return Database().write(self)


class User(BaseUser):
    """A registered user."""

    def login(self, password):
        if self.check_password(password):
            self.save()
            return create_session(self)
        return None

    def check_password(self, password):
        return password == "secret"


def create_session(user):
    return {"user": user}
''',
    "app/db.py": '''
class Database:
    def write(self, obj):
        return True
''',
    "app/views.py": '''
from .auth import User


def login_view(request):
    user = User()
    return user.login(request["password"])
''',
    "web/api.ts": '''
import { fetchJson } from "./http";

export class ApiClient extends BaseClient {
  getUser(id: string) {
    return this.request(`/users/${id}`);
  }
  request(path: string) {
    return fetchJson(path);
  }
}

class BaseClient {}
''',
    "web/http.ts": '''
export function fetchJson(path: string) {
  return fetch(path).then((r) => r.json());
}
''',
    "web/legacy.js": '''
var app = exports = module.exports = {};
app.init = function init() { this.boot(); };
app.boot = function boot() { return 1; };
''',
    "README.md": '''
# Demo

Users log in through `User.login`, which calls `create_session`.
See `app/db.py` for storage.
''',
}


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def graph(repo) -> Graph:
    return build_graph(repo)


def edge(graph: Graph, src: str, dst: str, kind: str) -> bool:
    return any(e.dst == dst for e in graph.out_edges(src, kind))


def test_symbols_from_python_ts_js_and_docs(graph):
    ids = set(graph.nodes)
    assert "app/auth.py::User.login" in ids
    assert "app/auth.py::create_session" in ids
    assert "web/api.ts::ApiClient.getUser" in ids
    assert "web/http.ts::fetchJson" in ids
    assert "web/legacy.js::app.init" in ids
    assert any(i.startswith("README.md::#") for i in ids)
    assert graph.stats["llm_tokens"] == 0


def test_python_calls_resolve_through_self_imports_and_inheritance(graph):
    login = "app/auth.py::User.login"
    assert edge(graph, login, "app/auth.py::User.check_password", CALLS)  # self.method
    assert edge(graph, login, "app/auth.py::BaseUser.save", CALLS)  # inherited method
    assert edge(graph, login, "app/auth.py::create_session", CALLS)  # module function
    assert edge(graph, "app/auth.py::User", "app/auth.py::BaseUser", INHERITS)
    assert edge(graph, "app/auth.py::BaseUser.save", "app/db.py::Database", CALLS)  # imported class
    assert edge(graph, "app/views.py::login_view", "app/auth.py::User", CALLS)  # relative import
    assert edge(graph, "file:app/views.py", "file:app/auth.py", IMPORTS)


def test_typescript_and_js_calls(graph):
    assert edge(graph, "web/api.ts::ApiClient.getUser", "web/api.ts::ApiClient.request", CALLS)  # this.method
    assert edge(graph, "web/api.ts::ApiClient.request", "web/http.ts::fetchJson", CALLS)  # named import
    assert edge(graph, "web/api.ts::ApiClient", "web/api.ts::BaseClient", INHERITS)
    assert edge(graph, "web/legacy.js::app.init", "web/legacy.js::app.boot", CALLS)  # this.x on app object
    assert edge(graph, "file:web/api.ts", "file:web/http.ts", IMPORTS)


def test_docs_link_to_code_by_exact_name(graph):
    doc = next(i for i in graph.nodes if i.startswith("README.md::#"))
    assert edge(graph, doc, "app/auth.py::User.login", MENTIONS)
    assert edge(graph, doc, "app/auth.py::create_session", MENTIONS)
    assert edge(graph, doc, "file:app/db.py", MENTIONS)


def test_save_and_load_round_trip(graph, tmp_path):
    path = tmp_path / "graph.json"
    graph.save(path)
    loaded = Graph.load(path)
    assert set(loaded.nodes) == set(graph.nodes)
    assert len(loaded.edges) == len(graph.edges)


def test_context_answers_with_relevant_symbols_and_source(graph, repo):
    result = query.context(graph, "How does User.login work?", root=repo)
    assert result.seeds[0] == "app/auth.py::User.login"
    assert "called by: login_view" in result.text
    assert "def login(self, password)" in result.text  # source snippet included
    assert result.tokens < 1500


def test_explain_path_and_find(graph, repo):
    node = query.resolve(graph, "fetchJson")
    assert node is not None and node.id == "web/http.ts::fetchJson"
    assert "called by: ApiClient.request" in query.explain(graph, node)
    a, b = query.resolve(graph, "login_view"), query.resolve(graph, "Database")
    assert "Database" in query.path(graph, a, b)
    assert query.find(graph, "check_pass")[0].name == "check_password"


def test_bench_compares_with_and_without(graph, repo):
    questions = auto_questions(graph, 5)
    assert questions
    data = run_bench(graph, repo, questions)
    assert data["schema"] == "tokenguard.bench/v1"
    totals = data["totals"]
    assert totals["questions"] == len(questions)
    assert totals["without_tokens"] > 0 and totals["with_tokens"] > 0
    assert data["graph"]["build_llm_tokens"] == 0
    assert all("without_tokens" in q and "with_tokens" in q for q in data["questions"])
