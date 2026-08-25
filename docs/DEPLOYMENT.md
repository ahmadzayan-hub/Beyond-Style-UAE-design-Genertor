# Deployment — GitHub / Vercel / Replit

Topology: **Browser → Vercel (Next.js, static/SSR) → HTTPS → Replit
(FastAPI) → PostgreSQL → deterministic Arabic/geometry/manufacturing
engines → Claude/GPT-Image-2 when configured.** Vercel never runs a
duplicate backend; the browser talks to the Replit origin directly
(CORS), not through a Vercel-side proxy.

## Root cause of the reported "تعذر توليد التصاميم" production bug

The frontend's `lib/api.ts` called every backend endpoint with a
**relative** path (`fetch("/api/designs", ...)`). Locally that works
because `next.config.mjs` rewrites `/api/*` to `BACKEND_URL` (default
`http://localhost:8000`). On Vercel, no `NEXT_PUBLIC_API_URL` (nor a
`BACKEND_URL` rewrite target) was ever configured, so the request
either hit Vercel's own `/api/*` (no such Next.js route exists → 404)
or the rewrite resolved to a meaningless `localhost` inside Vercel's
serverless runtime. Every code path collapsed into the same generic
catch block and the customer saw one fixed Arabic sentence regardless
of the real cause — and no backend runtime error was ever produced
because the browser never reached a real backend.

Fixed this slice:
1. `lib/api.ts` now fetches `NEXT_PUBLIC_API_URL + path` directly
   (falls back to the old relative-path/rewrite behavior only when
   `NEXT_PUBLIC_API_URL` is unset — local dev is unaffected).
2. The backend previously had **no CORS middleware at all** — even
   with the URL fixed, a direct browser→backend fetch would have been
   blocked. `app/main.py` now adds `CORSMiddleware` with a configurable
   `ALLOWED_ORIGINS` allow-list.
3. Every response now carries a structured `error_code` +
   `request_id` (see `app/main.py`'s exception handlers and
   `app/observability.py`) so the frontend can distinguish "never
   reached the backend" (`CONNECTION_FAILED`) from a real backend
   error, instead of one generic message for everything.
4. A real, previously-undeclared runtime dependency gap was found and
   fixed: `app/security/uploads.py` imports Pillow at module level
   (so the whole app fails to even start without it), but `Pillow` was
   missing from `backend/requirements.txt`. A fresh `pip install -r
   requirements.txt` on Replit would have crashed the app at import
   time regardless of the CORS/URL fix. Now pinned (`pillow==10.4.0`).

**Verified locally** (not yet against the real Vercel/Replit URLs — see
"What remains unverified" below): with both fixes applied, a full
`scripts/production-smoke.py` run against local backend+frontend using
the exact reported input (`حامد حمد فاطمة سلطان خالد مهرة`, with a
reference upload) passes all 14 checks A–K, including CORS preflight
from the frontend's origin and exactly 10 candidates returned.

## Environment contract

### Replit backend secrets (set in Replit's Secrets pane — never in a
committed file)

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL 16. Never SQLite in production. |
| `ALLOWED_ORIGINS` | yes | Comma-separated exact origins, e.g. `https://www.beyondstyle.ae,https://beyondstyle.ae`. No `*` — see CORS below. |
| `APP_ENV` | recommended | `production` — informational; no code branches on it yet. |
| `SECRET_KEY` | reserved | Not yet consumed by any code path (anonymous session tokens are sha256-hashed, no signing secret in this slice) — set a random value now so nothing else needs to change when a future slice adds signed sessions/CSRF. |
| `AI_PROVIDER` | reserved | `anthropic` — informational; this app only supports the Claude provider (`ANTHROPIC_API_KEY`-gated), no other provider is wired. |
| `ANTHROPIC_API_KEY` | optional | Enables real Claude calls. Absent → honest `SKIPPED_EXTERNAL_MODEL`/`SKIPPED_NO_CREDENTIALS`, Golden Path unaffected. |
| `OPENAI_API_KEY` | optional | Enables real GPT-Image-2 calls (also needs `OPENAI_IMAGE_ENABLED=true`). |
| `OPENAI_IMAGE_ENABLED` | optional | `true` to turn on GPT-Image-2; default `false`. |
| `HERMES_MODE` | optional | `in_process` (default, no separate service needed) or `isolated` (needs `services/hermes/` deployed separately + `HERMES_URL`). |
| `INTERNAL_TOOL_TOKEN` | optional | Only needed if running Hermes isolated — shared secret with `services/hermes`'s `MAIN_APP_TOOL_TOKEN`. |
| `MAX_UPLOAD_BYTES`, `PRIVATE_STORAGE_DIR`, `UPLOAD_RATE_MAX`, `UPLOAD_RATE_WINDOW_S`, `GENERATE_RATE_MAX`, `GENERATE_RATE_WINDOW_S` | optional | Existing storage/session tuning — see `app/security/uploads.py` and `app/security/sessions.py`. Defaults are sane for a small deployment. |

Full list with local defaults: `backend/.env.example`.

### Vercel frontend

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | yes | The real Replit backend origin, e.g. `https://beyond-style-uae.your-username.repl.co`. Bundled into client JS — **never put a secret in a `NEXT_PUBLIC_*` variable.** |
| `NEXT_PUBLIC_APP_ENV` | recommended | `production` |

This app has **no Next.js API routes** — nothing on Vercel executes
server-side code that would need `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`.
Do not add them to the Vercel project.

### GitHub Actions secrets

- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — only consumed by the manual
  `external-ai-acceptance` workflow (never runs on every PR).
- `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` — only needed if
  automated Vercel deployment from CI is configured (not done in this
  slice — Vercel's own GitHub integration already auto-deploys pushes
  to the linked repo/branch without needing these).

## CORS

`ALLOWED_ORIGINS` is a comma-separated exact-origin list
(`app/main.py`). No wildcard is ever combined with credentials
(`allow_credentials=False` — the session token travels as an
`X-Session-Token` header, not a cookie, so credentialed CORS was never
needed). Local dev default (only used when `ALLOWED_ORIGINS` is unset):
`http://localhost:3000`.

Production example — the exact HTTPS origins required for the P1
release gate (see RELEASE_EVIDENCE.md): the current live Vercel
deployment origin (needed until the custom domain is attached) plus
the two target custom-domain origins:
```
ALLOWED_ORIGINS=https://frontend-sigma-sable-22.vercel.app,https://beyondstyle.ae,https://www.beyondstyle.ae
```
Drop the `frontend-sigma-sable-22.vercel.app` entry once
`beyondstyle.ae`/`www.beyondstyle.ae` is the site's only production
origin. Add a Vercel preview domain only if you explicitly want
previews to call the production backend (usually you don't).

## Health / readiness

- `GET /health` — process alive only, no dependency checks.
- `GET /ready` — checks database, Alembic migration head, font
  registry, Arabic shaping engine, geometry/manufacturing engine,
  storage, design generator. Returns `503` if any component is not
  `ok`, `200` with `status: "ready"` otherwise. Never leaks a DSN,
  password, or internal path — only `status`/`detail` (exception class
  name only).
- `GET /api/ai/status` — honest Claude/GPT-Image-2/Hermes/deterministic-
  fallback status (same vocabulary as `docs/STATUS.md`), plus the
  existing local Qwen/FLUX visual-stack status. Never a fabricated
  PASS; `deterministic_fallback` is always `always_available`.

## Frontend error UX

`lib/api.ts` throws a typed `ApiError` with a `code` from:
`CONNECTION_FAILED | REFERENCE_NOT_READY | GENERATION_FAILED |
NO_VALID_CANDIDATES | ARABIC_VALIDATION_FAILED | BACKEND_UNAVAILABLE |
SESSION_EXPIRED | RATE_LIMITED | UNKNOWN`, derived from the backend's
`error_code` field (added to every error response by
`app/main.py`'s exception handlers) or, for a request that never
reached the backend at all, `CONNECTION_FAILED`. `app/page.tsx` maps
each code to a friendly AR/EN message (`lib/i18n.ts:error_codes`) and
shows the `request_id` as a small support/debug detail — never a raw
stack trace.

Loading-state labels (`lib/i18n.ts`): جاري رفع الصورة / جاري تحليل
المرجع (upload+analyze substeps) → نُحضّر التصاميم / نراجع الكتابة
العربية / نراجع قابلية التصنيع (the actual candidate-generation call —
these three labels genuinely correspond to the deterministic pipeline's
real stages: generation, Arabic identity verification, manufacturing
validation).

## Provider fallback (critical)

Claude/GPT-Image-2/Hermes failure must never fail the core Generate
button — `svc.generate_and_persist_candidates` has no dependency on any
of them. GPT-Image-2 is only ever called for the customer's selected
design (`create_visual_preview`), never for all 10 candidates. This was
already true architecturally (ADR-0002/0003) and is re-verified by
`backend/scripts/external_ai_acceptance.py`'s
`provider_failure_deterministic_path` check and
`test_deployment_readiness.py`.

## GitHub CI (`.github/workflows/ci.yml`)

Runs on every push/PR: backend tests (PostgreSQL 16 service, Alembic
up/down/up, full pytest suite), frontend typecheck+build, browser E2E
(starts real backend+frontend, runs `e2e/golden_path_e2e.py` +
`e2e/copilot_e2e.py`), and a secret-leak scan
(`scripts/secret_scan.py`). CI fails on any of these.

`.github/workflows/external-ai-acceptance.yml` — **manual** dispatch
only, never on every PR (these are paid providers). Runs `make
external-ai-e2e` with `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` from repo
secrets. Missing credentials report `SKIPPED_NO_CREDENTIALS`, not a CI
failure.

`.github/workflows/deployment-smoke.yml` — manual dispatch with
`frontend_url`/`backend_url` inputs. Runs
`scripts/production-smoke.py` against the real deployed URLs.

## Vercel

Project already exists and is linked to this GitHub repo (Vercel's own
GitHub integration deploys pushes automatically — no `VERCEL_TOKEN`
needed for that). To finish production readiness:

1. In the Vercel project's Settings → Environment Variables, set
   `NEXT_PUBLIC_API_URL` to the real Replit backend origin and
   `NEXT_PUBLIC_APP_ENV=production` for the Production environment.
2. Redeploy (a new push, or "Redeploy" in the Vercel dashboard) so the
   build picks up the new env var (`NEXT_PUBLIC_*` values are baked in
   at build time).
3. Point the production domain (`www.beyondstyle.ae`) at this project
   once DNS is ready — no code changes needed, `ALLOWED_ORIGINS` on the
   backend must include the final domain(s).

This session has live Vercel API access to the linked project
(`frontend`, id `prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`) and confirmed its
latest production deployment is `READY` with **no runtime errors** in
the last 7 days — consistent with the root cause being a client-side
fetch that never reached any backend, not a Vercel/Next.js server
error. This session has **no tool to set Vercel environment
variables** — step 1 above is a manual action in the Vercel dashboard
(or `vercel env add NEXT_PUBLIC_API_URL production` via the Vercel CLI
with an authenticated account).

## Replit

`.replit` is configured (`deploymentTarget = "cloudrun"`): build
installs `backend/requirements.txt`, run applies `alembic upgrade
head` (forward-only, never destructive) then starts
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

**This session has no Replit access (no Replit MCP connector, no CLI
token) — the backend has never been deployed to Replit or any other
public host in this session.** The manual action required:

1. Import this GitHub repo into a new Replit (or connect an existing
   Repl to it).
2. In the Repl's Secrets pane, set at minimum `DATABASE_URL` (a real
   managed PostgreSQL 16 instance — Replit's own Postgres or an
   external one) and `ALLOWED_ORIGINS` (the Vercel production
   domain(s)).
3. Click **Publish** (Reserved VM or Autoscale deployment). Replit
   provisions the public URL and `$PORT` automatically.
4. Copy the resulting public URL into Vercel's `NEXT_PUBLIC_API_URL`
   (see above) and redeploy the frontend.

Never fabricate a Replit deployment URL or token — until step 3 above
happens on a real Replit account, "REPLIT STATUS" is honestly
"not yet deployed," not "verified."

## Database

Production must be real PostgreSQL 16 (never local ephemeral SQLite —
this codebase has no SQLite support path at all; `DATABASE_URL` is
always a `postgresql+psycopg2://` DSN). `/ready` verifies the
connection AND that the schema is at the Alembic head — a schema
mismatch fails readiness (`503`) rather than silently serving on an
incompatible database. Migrations only ever run forward
(`alembic upgrade head`); there is no automatic downgrade path in the
deploy command. For backups/restore, use your PostgreSQL provider's
standard `pg_dump`/point-in-time-recovery tooling — no
project-specific backup tooling exists yet (tracked as NOT_IMPLEMENTED
in `docs/STATUS.md`, matching the existing S3/Redis gap).

## Observability

Every request gets an `X-Request-ID` (client-supplied or generated),
echoed in the response header and in every error body. Structured JSON
request logs (`app/observability.py`) carry
`request_id`/`route`/`method`/`status`/`duration_ms` — never a raw
customer image, uploaded file, or secret value. `/ready`'s per-
component detail is limited to `status` and, on failure, the Python
exception *class name* only (e.g. `OperationalError`), never the
exception message (which could contain a DSN or file path).

## Secret leak prevention

- `.gitignore` covers `.env`, `.env.local`, `.env.production*`,
  `*.pem`, `*.key`, `.vercel`.
- `scripts/secret_scan.py` — stdlib-only, scans every git-tracked file
  for real credential *shapes* (Anthropic/OpenAI/AWS/GitHub/Vercel/Slack
  key patterns, PEM private key headers), not just variable names. Runs
  in CI on every PR; exits non-zero on a hit.
  `backend/tests/test_secret_scan.py` also proves it actually catches a
  synthetic key and stays clean on the real repo.
- `backend/tests/test_secret_scan.py::test_frontend_build_never_contains_secret_key_material`
  builds the real Next.js production bundle and greps it for
  `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` — proven absent (this app never
  references them client-side; there are no Next.js API routes that
  would need them server-side either).
- `app/main.py`'s unhandled-exception handler never returns exception
  text to the client — only a generic message + `error_code` +
  `request_id`; the real detail is in the structured server log only.

## Production smoke test (`scripts/production-smoke.py`)

Stdlib-only (Pillow is used opportunistically for the reference-upload
check if available, gracefully skipped otherwise). Checks A–K from the
release gate below against real `FRONTEND_URL`/`BACKEND_URL`:

```
FRONTEND_URL=https://www.beyondstyle.ae \
BACKEND_URL=https://<your-replit-app>.repl.co \
python3 scripts/production-smoke.py
```

Verified in this session against **local** backend+frontend (not yet
the real production URLs — those don't exist yet, see Replit/Vercel
sections above) using the exact reported bug scenario text
(`حامد حمد فاطمة سلطان خالد مهرة`, with a reference image upload): all
14 checks pass, including exactly 10 candidates returned.

## Release gate

Production release is acceptable only when ALL of the following are
true (checked in this order):
1. Backend tests green.
2. Frontend production build green.
3. Browser E2E green.
4. Migrations green (up/down/up cycle).
5. Secret scan green.
6. Replit `/ready` green (once actually deployed).
7. Vercel frontend green (already true — see Vercel section).
8. Vercel → Replit CORS/API request green (verified locally with the
   fix; requires real URLs to verify in production).
9. Real "Generate Designs" works (the exact previously-failing
   scenario) — verified locally; requires the real deployment to
   verify in production.
10. Deterministic fallback works with Claude/GPT-Image-2/Hermes all
    disabled — verified (`test_deployment_readiness.py`,
    `make external-ai-e2e`'s provider-failure check).

Items 6/8/9 above cannot be marked VERIFIED from this session — there
is no live Replit deployment to point Vercel's `NEXT_PUBLIC_API_URL`
at yet. Everything else (1–5, 10, and the code fix for 8/9) is done
and evidenced in this repository; completing 6/8/9 needs the one
manual Replit Publish step above, then re-running
`scripts/production-smoke.py` against the real URLs.
