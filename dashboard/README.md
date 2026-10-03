# TokenGuard dashboard

Next.js app with two tools:

- **Usage & cost** (`/`): drop a `tokenguard export` JSON file to see cost by model, project and day, and which tools flood the context. The file is read in the browser and never uploaded. `/?sample=1` opens demo data.
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
