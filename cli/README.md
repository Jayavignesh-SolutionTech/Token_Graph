# TokenGuard CLI

TokenGuard turns your project into a searchable map of files, functions, classes,
docs and how they connect. Your AI coding assistant asks the map first and opens
only the code it needs, instead of grepping and reading whole files.

It also profiles what your coding agents (Claude Code, OpenAI Codex) spend, from
the session logs they already write on your machine. Nothing is uploaded.

## Install (development)

```powershell
cd cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Code map

```powershell
cd C:\path\to\your-repo
tokenguard scan                                   # build .tokenguard/graph.json (local, 0 LLM tokens)
tokenguard ask "how does login work?"             # what an AI assistant receives
tokenguard explain User.login --source            # callers, callees, inheritance, docs, code
tokenguard search session                         # find symbols, files and doc sections
tokenguard deps app/auth.py                       # imports and imported-by
tokenguard path login_view Database               # how two pieces of code connect
tokenguard bench -n 20 -o bench.json              # tokens WITH the map vs WITHOUT it
```

What goes into the map (Python, JavaScript, TypeScript, Markdown/RST docs):

| Nodes | Edges |
|---|---|
| files, classes, functions, methods, interfaces, doc sections | `calls`, `imports`, `inherits`, `contains`, `mentions` (doc → code) |

Edges are found by parsing (Python's `ast`, tree-sitter for JS/TS), not by an LLM
or embeddings. Edges resolved through imports, `self`/`this` or inheritance are
exact; edges matched only by a unique name are marked `~` in answers.
`.gitignore` is respected, and the map rebuilds itself when files change.

### Connect your AI assistant (MCP)

`tokenguard serve` is an MCP server with five tools: `tokenguard_ask`,
`tokenguard_search`, `tokenguard_explain`, `tokenguard_deps` and `tokenguard_path`.

Claude Code, from your repository folder:

```powershell
claude mcp add tokenguard -- "C:\path\to\Token_Graph\cli\.venv\Scripts\tokenguard.exe" serve --repo "C:\path\to\your-repo"
```

Any other MCP client (Cursor, Codex, ...) uses the same command and arguments.

### Measuring the savings

`tokenguard bench` asks the same questions two ways:

- **Without:** grep the repo for the identifiers in the question (first 100
  matching lines), then read the 5 files with the most matches.
- **With:** one `tokenguard_ask` call, capped at 1,500 tokens.

Both sides use the same token estimate (~4 characters per token). It also reports
whether each answer contained the code that was asked about. Drop `bench.json` on
the TokenGuard dashboard to see the comparison.

Example runs on open-source repos (15 questions each):

| Repo | Without | With | Saved |
|---|---|---|---|
| pallets/flask | 250,452 | 20,561 | 92% (12×) |
| expressjs/express | 127,037 | 4,087 | 97% (31×) |

Savings depend on the codebase and the questions; bigger repos save more.

## Session costs

```powershell
tokenguard sources                      # where logs are read from
tokenguard report                       # cost by model (all time)
tokenguard report --by project --since 7d
tokenguard report --by day --source claude-code
tokenguard report --by session --format csv > sessions.csv
tokenguard tools --since 7d             # which tools flood the context
tokenguard export --since 30d -o tokenguard.json   # for the dashboard
```

`--by` accepts `model`, `project`, `day`, `session` or `source`.
`--since` accepts `24h`, `7d`, `4w` or a date such as `2026-09-01`.

| Source | Log location | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` (or `$CLAUDE_CONFIG_DIR`) | One record per API response, de-duplicated by message id |
| Codex | `~/.codex/sessions/**/*.jsonl` (or `$CODEX_HOME`) | Increases in the running `token_count` total |

Costs are **API-equivalent at list prices**. If you use a subscription plan
(Claude Pro/Max, ChatGPT Plus/Pro), the figure shows what the same usage would
cost on the API, not what you were billed.

### Prices

Bundled prices live in `src/tokenguard/data/pricing.toml`, with the source URL
and the date they were checked. Models without a known price are reported as
unpriced rather than guessed. To add or override prices, create
`~/.tokenguard/pricing.toml` in the same format:

```toml
[openai."codex-auto-review"]
input = 1.25
cache_read = 0.125
output = 10.0
```

## Tests

```powershell
pytest
```
