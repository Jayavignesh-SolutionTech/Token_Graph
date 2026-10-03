# TokenGuard CLI

See where your AI coding agents spend tokens and money. TokenGuard reads the
session logs that Claude Code and OpenAI Codex already write on your machine.
Nothing is uploaded.

## Install (development)

```powershell
cd cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Usage

```powershell
tokenguard sources                      # where logs are read from
tokenguard report                       # cost by model (all time)
tokenguard report --by project --since 7d
tokenguard report --by day --source claude-code
tokenguard report --by session --format csv > sessions.csv
tokenguard tools --since 7d             # which tools flood the context
```

`--by` accepts `model`, `project`, `day`, `session` or `source`.
`--since` accepts `24h`, `7d`, `4w` or a date such as `2026-09-01`.

## What is counted

| Source | Log location | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` (or `$CLAUDE_CONFIG_DIR`) | One record per API response, de-duplicated by message id |
| Codex | `~/.codex/sessions/**/*.jsonl` (or `$CODEX_HOME`) | Increases in the running `token_count` total |

Costs are **API-equivalent at list prices**. If you use a subscription plan
(Claude Pro/Max, ChatGPT Plus/Pro), the figure shows what the same usage would
cost on the API, not what you were billed.

## Prices

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
