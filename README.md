# TokenGuard

A code map for AI coding assistants. TokenGuard turns your project into a
searchable map of files, functions and how they connect, so your assistant asks
the map first and opens only the code it needs, using a fraction of the tokens.

| Folder | What it is |
|---|---|
| [`cli/`](cli/) | Python CLI: `scan` builds the code map, `serve` exposes it over MCP, `bench` measures tokens with vs without it, `report` profiles Claude Code / Codex session costs |
| [`dashboard/`](dashboard/) | Next.js app on Vercel: the with/without comparison, session costs, and the prompt reshaper |

Start with [cli/README.md](cli/README.md).
