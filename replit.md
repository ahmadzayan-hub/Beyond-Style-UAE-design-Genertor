# Beyond Style backend on Replit — 10-minute go-live

The backend must run from THIS repository. A Repl created by Replit's AI
Agent from a description is a different application and will not serve
`/health` or `/api/*` — the production monitor detects that case
explicitly ("URL answers 200 but is NOT the Beyond Style backend").

## One-click import
Open: https://replit.com/github/ahmadzayan-hub/Beyond-Style-UAE-design-Genertor
(or: Create Repl → Import from GitHub → paste the repository URL).
The default branch already contains the deployment config (`.replit`).

## Steps
1. Tools → Database → **PostgreSQL** → create. Replit injects `DATABASE_URL`.
2. (Optional) Secrets: `ALLOWED_ORIGINS` for extra origins — first-party
   origins (the Vercel site, beyondstyle.ae) are already built in.
   `ADMIN_API_TOKEN` to enable the staff screens.
3. Press **Run** once; the webview shows the API. Add `/health` to its
   URL → expect `{"status":"ok","schema_version":"..."}`.
4. **Deploy → Publish** (Reserved VM recommended). Accept the pre-filled
   build/run commands (they come from `.replit`: pip install, alembic
   upgrade head, uvicorn on `$PORT`). Link the PostgreSQL database.
5. Name the deployment subdomain `beyond-style-uae-design-genertor` so the
   URL in `deploy/production.json` stays valid — or update that file and
   push; the Production Monitor workflow re-verifies on every push.

## Verify
GitHub → Actions → **Production Monitor** → latest run must be green:
frontend loads, `/health` is ours, `/ready` reports the database, CORS
allows the frontend origin, and the seven-name Arabic scenario round-trips
byte-for-byte.
