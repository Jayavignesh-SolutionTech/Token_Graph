# TokenGuard dashboard

Next.js app with two tools:

- **Usage & cost** (`/`): drop a `tokenguard bench` file to compare tokens per question with vs without the code map (with a team savings calculator), or a `tokenguard export` file for session costs. Files are read in the browser and never uploaded. Demos: `/?sample=1` (Flask benchmark), `/?sample=usage` (session costs).
- **Prompt reshaper** (`/reshape`): rewrites a prompt to be clearer and use fewer tokens, via `POST /api/reshape`.

## Environment variables

| Name | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | For the reshaper | Server-side key used by `/api/reshape` |
| `RESHAPE_ACCESS_CODE` | Recommended on public deployments | Visitors must enter this code, so strangers can't spend your API credit |
| `RESHAPE_MODEL` | No | Defaults to `claude-opus-5-5` |

## Develop (PowerShell)

```powershell
cd dashboard
npm install
$env:ANTHROPIC_API_KEY = "<your key>"   # only needed for the reshaper
npm run dev
```

Open http://localhost:3000.
