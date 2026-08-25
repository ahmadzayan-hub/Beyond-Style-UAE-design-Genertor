# Release Evidence — Production Release Hardening

**FINAL RELEASE DECISION: NOT PRODUCTION READY.**

Status vocabulary used below (per the release-hardening mandate):
`VERIFIED_LOCAL` (real execution against local infra) /
`VERIFIED_CI` (real execution on GitHub Actions) /
`VERIFIED_PRODUCTION` (real execution against a real deployed production
URL) / `SKIPPED_NO_CREDENTIALS` (honest skip, no API key) /
`OPTIONAL_NOT_RUNNING` (an optional runtime is not configured, the
deterministic path is unaffected) / `BLOCKED` (no tool access in this
session) / `FAILED` (a real attempt errored). Local evidence is never
promoted to production evidence.

## COMMIT SHA

`a7e38587bb21b28ef108959b676d461ccba4438f` on branch
`claude/p0-golden-path-audit-jtyduw`,
`ahmadzayan-hub/Beyond-Style-UAE-design-Genertor`. Vercel's latest
production deployment (`dpl_AwMr2Pnttsgxnq8YuTibE8w49Eye`) confirmed
via the Vercel API to match this exact SHA. GitHub Actions CI run
`32900447345` on this exact commit confirmed `conclusion: success`.

## SECURITY (dependency triage — pip-audit + npm audit, this slice)

| Package | Installed | Fixed | CVE/Advisory | Severity | Reachable in this app? | Remediation |
|---|---|---|---|---|---|---|
| python-multipart | 0.0.9 (implicit, unpinned) | 0.0.31 | 7 advisories (PYSEC-2026-1851/1852/3036–3040) | Moderate | **Yes** — used by every multipart upload request (reference-image intake) | **FIXED**: pinned `0.0.31`. Also fixed a real, separate deployment blocker: this package was never pinned at all, so a clean install (GitHub Actions, fresh Replit) failed at test-collection — this was the actual root cause of all 9 prior CI failures on this branch. |
| pillow | 10.4.0 | 12.3.0 | 24 advisories incl. PYSEC-2026-2249/2250/2874/3451/3453/3493-3496 (native heap out-of-bounds writes) | High (several) | **Yes** — processes every customer-uploaded reference image | **FIXED**: pinned `12.3.0`. Full 230-test suite re-verified green. |
| fonttools | 4.53.1 | 4.60.2 | CVE-2025-66034 (arbitrary file write via `fontTools.varLib` CLI merge script) | Moderate | **No** — this app only does glyf/CFF parsing, never invokes the `varLib` CLI | **FIXED anyway**: same-major, low-risk bump, no code depends on the affected path. |
| pytest | 8.3.3 | 9.0.3 | PYSEC-2026-1845 (predictable `/tmp/pytest-of-{user}` dir) | Low | **No** — dev/CI-only, pytest never runs in a production deployment | **FIXED anyway**: zero-risk bump, achieves a fully clean `pip-audit` scan. |
| next.js | 14.2.13 | 15.5.24 (used) / 16.3.3 (npm's stated "fix") | 30 advisories rolled into one `npm audit` entry (DoS via Server Components/Actions, SSRF, cache poisoning, XSS, HTTP request smuggling in `rewrites()`, etc.) | Critical + High (mixed; several individual advisories are High) | **Partially** — this app has no Server Actions, no `next/image`, no `middleware.ts`, so most advisories don't apply to its actual usage; but `rewrites()` **is** unconditionally compiled into the production build (even though the app's own client code doesn't call it in production), so the "HTTP request smuggling in rewrites" advisory (range `<15.5.13`) is a real reachable surface | **FIXED**: upgraded to `15.5.24` (latest 15.x), which is beyond every individual advisory's fixed-version range found (`<15.0.8` through `<15.5.21`) — closes every reachable CVE without the 2-major-version jump to 16.x npm's summary line names. Verified: clean typecheck, clean build, 5/5 E2E flows. |
| postcss (project's own) | 8.4.47 | 8.5.26 | GHSA-qx2v/6g55/fxqj/r28c (XSS in stringify, sourcemap path traversal/file read) | High (1) | **No** — build-time-only CSS transform tool; this app authors its own CSS, never processes attacker-supplied CSS | **FIXED anyway**: cheap, no compat risk. |
| postcss (next's internally-vendored copy, `next/node_modules/postcss`) | 8.4.31 | — | same as above | High (1) | **No** — same reasoning; also not under this project's control (bundled by Next.js itself) | **NOT FIXED** — would require forcing a resolution Next.js's own build wasn't tested against, for a build-time-only, non-reachable tool. Left as the sole remaining `npm audit` finding, precisely because it isn't reachable. |
| starlette | 0.38.6 | 1.3.1 (smallest fully-patched) | 9 advisories: PYSEC-2026-161/248/249/1941/1943/2280/2281 (multipart form-data DoS/field confusion, `StaticFiles` path handling, Host-header URL reconstruction) | High (several) | **Yes** — this app accepts multipart uploads and serves via Starlette's request/response stack | **ATTEMPTED AND REVERTED — see below.** Remains open. |

### The FastAPI/Starlette upgrade attempt (real regression found and reverted)

`fastapi==0.115.0` pins `starlette<0.39.0`, which excludes every fix for
the 9 starlette CVEs above. Precisely checked via PyPI metadata for the
smallest compatible fix: `fastapi==0.135.0` is the smallest FastAPI
version whose starlette constraint (`>=0.46.0`, unbounded above) permits
a fully-patched starlette; `pydantic>=2.7.0` required by 0.135.0 was
already satisfied by the existing `2.9.2` pin (no cascading bump
needed).

This combination (`fastapi==0.135.0` + `starlette==1.3.1`) **passed the
full 230-test suite** (FastAPI `TestClient`, in-process ASGI, no real
sockets) — but broke a P0 golden-path feature under **real uvicorn HTTP
request handling**:

- `POST /api/designs/{id}/candidates` returns a normal-looking 200
  response with plausible candidate data.
- A subsequent `GET .../candidates/{id}/svg` on any of those candidate
  IDs returns `404`; `GET .../candidates` (list) returns `[]`.
- Confirmed **100% reproducible** (3/3 fresh design requests) via direct
  `curl` against a live server — not a Playwright/browser artifact.
- Confirmed **NOT reproducible** calling the identical service function
  (`generate_and_persist_candidates`) directly in-process with a real
  DB session and explicit `commit()` — the underlying business logic is
  correct; the bug is specific to real ASGI request/response handling
  under this exact FastAPI/Starlette pairing (most likely the `yield`-
  dependency teardown/commit timing for `get_session()`), and
  `TestClient`-based unit tests do not exercise this path realistically
  enough to catch it.

**Reverted to `fastapi==0.115.0`** (no explicit starlette pin) rather
than ship a P0 golden-path break for a security fix. Re-verified after
the revert, using fresh (non-stale) backend + frontend processes:
230/230 backend tests, 5/5 browser E2E flows, 15/15 production smoke,
and the exact curl reproduction now returns `200`/correct data.

**The starlette CVEs remain open.** Exact remediation path for a future
slice: bisect which specific change (FastAPI's dependency-resolution
internals vs. Starlette's own request lifecycle) causes the commit-
visibility bug, with a minimal reproduction outside this app, before
attempting the upgrade again — or wait for a FastAPI/Starlette release
combination with this specific interaction fixed upstream.

**No secrets found**: `scripts/secret_scan.py` (repo-wide) — clean, this
slice. `frontend/.next` build output grepped for
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`sk-ant-`/`sk-proj-`/DB connection
strings — none found.

## CI

Real GitHub Actions history, not assumed:

- **Runs 1–9** (every prior commit on this branch): all **failed**.
  Root cause confirmed by pulling real job logs: `python-multipart`
  missing from `requirements.txt` → test-collection `RuntimeError` on
  GitHub's clean runner (this sandbox had it as a stray pre-installed
  package, masking the gap locally).
- **Run 10** (`32872953221`, commit `680aa1d`, the python-multipart
  fix): `secret-scan` and `frontend` jobs **succeeded**; `backend`
  job's actual test suite **succeeded** (7m19s, 230 tests) — but the
  job's overall conclusion was **failure** because the
  `actions/upload-artifact` step hit `"Artifact storage quota has been
  hit"` — a GitHub-side resource-limit error, unrelated to code
  correctness. **This is the real reason CI read as failing even after
  the code fix.**
- **Run 11** (`32873532817`, docs-only commit): same artifact-quota
  failure (fix not yet in place).
- **Fixed this slice**: `.github/workflows/ci.yml` — added
  `continue-on-error: true` to both `actions/upload-artifact` steps, so
  a storage-quota (or any other artifact-service) failure can never
  fail an otherwise-green required job again.
- **Run 12** (`32884649563`, commit `27b48d6`, the code-changing
  commit): **`conclusion: success`, confirmed** — all 4 jobs green:
  `frontend` (success, 18:36:26), `secret-scan` (success, 18:35:46),
  `backend` (success, 18:44:41 — test suite 230 tests in 7m26s +
  proof-sheet evidence upload), `e2e` (success, 18:47:05 — Playwright
  install + real backend/frontend + `golden_path_e2e.py` +
  `copilot_e2e.py` both passing). **This is the first fully green CI
  run on this branch.**
- **Run 13** (`32884909589`, commit `99c5bea`, docs-only): `success`.
- **Run 14** (`32885060609`, commit `912355e`, docs-only): `success`.
- **Run 15** (`32900447345`, commit `a7e3858`, docs-only, **current
  HEAD**): `status: completed`, **`conclusion: success`** — confirmed
  via `get_workflow_run`, not assumed. Five consecutive green runs.

**`CI = VERIFIED_CI`.** `head_sha` of the latest confirmed-green run
(`a7e38587bb21b28ef108959b676d461ccba4438f`) matches this document's
release-candidate commit (see COMMIT SHA below) exactly.

## REPLIT BACKEND

**BLOCKED.** Re-confirmed again this slice via `ToolSearch("replit")`:
no Replit MCP connector, no Replit CLI/API token, no matching tool of
any kind in this session. `.replit` (build/run/deploy config) is
prepared and valid:
```toml
entrypoint = "backend/app/main.py"
[deployment]
deploymentTarget = "cloudrun"
build = ["sh", "-c", "cd backend && pip install -r requirements.txt"]
run = ["sh", "-c", "cd backend && python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```
Verified this slice, fresh, against the current (post-hardening) local
backend — all real, none fabricated:
- Start command uses the correct module path (`app.main:app`), binds
  `0.0.0.0:$PORT`, **no `--reload`**.
- Alembic migration path: `python -m alembic upgrade head` runs before
  `uvicorn` starts — forward-only, confirmed by reading the command and
  by 4 separate from-scratch clean-venv runs this pass (all succeeded,
  none used `downgrade`/`stamp`).
- `GET /health` → `200 {"status":"ok","schema_version":"0.1.0"}`.
- `GET /ready` → `200`, all 7 components `ok` (database, migrations at
  head `9520aa9396f0`, font_registry, arabic_shaping_engine,
  geometry_and_manufacturing_engine, storage, design_generator).
- `GET /api/ai/status` → `200`, honestly reports `ai_mode: "disabled"`,
  `claude.credentials_configured: false`, `gpt_image_2.key_configured:
  false`, `hermes.mode: "in_process"`,
  `deterministic_fallback.status: "always_available"` — no fabricated
  provider state.
- Structured logs: every request emits one JSON line
  (`app/observability.py`) with `request_id`/`route`/`method`/`status`/
  `duration_ms` — verified present in this slice's local server output.
- **PostgreSQL only**: `DATABASE_URL` in `.env.example` and `.replit`'s
  comment both specify `postgresql+psycopg2://...`; no SQLite path
  exists anywhere in `app/db/base.py` or the Alembic env.

**Exact manual action required** (project owner, in the Replit
dashboard): import this repo, open the Secrets pane, set `DATABASE_URL`
and `ALLOWED_ORIGINS` (required — exact value below), optionally
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`OPENAI_IMAGE_ENABLED=false`/
`HERMES_MODE=in_process`/`INTERNAL_TOOL_TOKEN`, then click Publish.

**Note on the mandate's requested env var list**: `SECRET_KEY`,
`APP_ENV`, and `AI_PROVIDER` were requested but do not exist anywhere
in this codebase (`grep` across `backend/app/` confirms zero
references) — setting them would do nothing. Real, code-verified env
vars this app reads: `DATABASE_URL`, `ALLOWED_ORIGINS`,
`INTERNAL_TOOL_TOKEN`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`OPENAI_IMAGE_ENABLED`, `HERMES_MODE`. No fake config-reading code was
added to make the requested-but-unused names do something — that would
be feature work outside this hardening pass's scope, and would create
settings that silently no-op.

## VERCEL FRONTEND

Real Vercel project `frontend` (`prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`),
confirmed via the Vercel API this slice. Latest production deployment
`dpl_AwMr2Pnttsgxnq8YuTibE8w49Eye`, `readyState: READY`,
`githubCommitSha: a7e38587bb21b28ef108959b676d461ccba4438f` — **exact
match** to this document's commit SHA.

**`VERIFIED_PRODUCTION` — frontend reachable through the current
protected deployment**, real evidence this slice via an authenticated
fetch (`web_fetch_vercel_url`, which authenticates through Vercel's own
protection rather than bypassing it — SSO stays enabled):
```
GET https://frontend-sigma-sable-22.vercel.app/  → 200 OK
```
Real page HTML returned: correct title ("Beyond Style — صمّم قطعتك"),
correct RTL Arabic UI (`text-input`, `upload-button`,
`style-minimal/luxury/traditional/modern`, `start-continue` present
and correctly `disabled` pre-input). This confirms the deployed
frontend itself is healthy and serving the right build — it does not
change the fact that an anonymous real customer still cannot reach it
(SSO wall) nor that this session's own unauthenticated egress to
`vercel.app` is still policy-blocked.

**`NEXT_PUBLIC_API_URL` still not set — BLOCKED.** No tool in this
session (`update_project_deployment_protection` covers only
password/SSO/trusted-IP settings, not environment variables; no
env-var-write tool exists) can set a Vercel project environment
variable. **Exact manual action required** (project owner, Vercel
dashboard): Settings → Environment Variables → Production, set
`NEXT_PUBLIC_API_URL` to the real backend HTTPS URL from the Replit
step above, then redeploy. Never put `ANTHROPIC_API_KEY`/
`OPENAI_API_KEY` in a `NEXT_PUBLIC_*` variable — confirmed no
server-side code exists in this Next.js app that would need them
client-side (no API routes).

**Vercel Authentication (SSO) is deliberately left enabled** per the
mandate ("keep enabled until security release blockers are cleared") —
the Starlette CVEs above remain open, so this is correct to leave as-is
regardless of tool access. Once security is cleared: either disable SSO
(`update_project_deployment_protection`, available) or attach
`www.beyondstyle.ae` as the production custom domain (SSO's
`all_except_custom_domains` scope already exempts real custom domains).

## DATABASE

`VERIFIED_LOCAL` only — no production database exists (no backend
deployed). Local PostgreSQL 16, migrations verified forward-only
(`alembic upgrade head`) in 4 separate from-scratch clean-venv
validations this slice, `/ready`'s reported revision cross-checked
against the DB's actual `alembic_version` row, exact match.

## CORS

Exact production origins documented in `docs/DEPLOYMENT.md` per the
mandate:
```
ALLOWED_ORIGINS=https://frontend-sigma-sable-22.vercel.app,https://beyondstyle.ae,https://www.beyondstyle.ae
```
`VERIFIED_LOCAL`: allowed origin → `200` with `access-control-allow-origin`
echoed; unknown origin → `400 Disallowed CORS origin`. No wildcard, no
credentialed CORS (`allow_credentials=False`). `ALLOWED_ORIGINS` has no
production default in code — confirmed by reading `app/main.py` — so it
is currently unset in any real production environment because none
exists yet. `VERIFIED_PRODUCTION`: not possible, no production backend.

## PRODUCTION SMOKE

`VERIFIED_LOCAL`: **15/15**, run three times in the prior slice against
successive dependency states (pre-upgrade, mid-upgrade with the
since-reverted FastAPI/starlette, and final reverted state) — all
15/15; baseline unchanged this slice (no code touched). `VERIFIED_CI`:
the 230-test backend suite and the full browser `e2e` job (Golden Path
+ Copilot flows) both independently passed on GitHub Actions run
`32884649563` against this exact commit's code — a second, independent
confirmation of the same baseline beyond this sandbox.
`VERIFIED_PRODUCTION`: `BLOCKED` for the full 15-check script — it
requires both a real `FRONTEND_URL` and `BACKEND_URL`; only the
frontend side is confirmed reachable this slice (see VERCEL FRONTEND
above), no backend exists at all. Per the mandate, this
gap is reported as `BLOCKED`, not filled in with local results.

## 7-NAME GOLDEN PATH

Fixture **حامد محمد سلطان ميثة حمد خالد مهرة** — `VERIFIED_LOCAL` at
three levels (unit: 11 tests incl. 5 fail-closed mutation cases; HTTP:
smoke step E, byte-exact match; browser: real reference-image upload
through the mobile UI, locked version 1, full event trail). Re-run this
slice against the fully security-hardened + reverted final backend —
still passes. `VERIFIED_PRODUCTION`: `BLOCKED` — no live production UI
to run it through.

## CLAUDE

`SKIPPED_NO_CREDENTIALS` — no `ANTHROPIC_API_KEY` in this session.
Deterministic Golden Path proven to work with Claude entirely absent
(the whole 230-test suite and every E2E flow above ran with it unset);
this is proven BEFORE any external-AI acceptance run, per the mandate's
required order. `make external-ai-e2e` was not re-run this slice (no
credentials changed) — see `docs/evidence/external-ai-acceptance.json`
from the prior slice for its honest `SKIPPED_NO_CREDENTIALS` record.

## GPT-IMAGE-2

`SKIPPED_NO_CREDENTIALS` — no `OPENAI_API_KEY`, `OPENAI_IMAGE_ENABLED`
defaults `false`. Same deterministic-path proof as CLAUDE above: image
generation absence never blocks candidate generation, selection,
validation, or export — the deterministic SVG/DXF path is fully
independent of this provider.

## HERMES

`OPTIONAL_NOT_RUNNING` (default, `HERMES_MODE=in_process`) — no
isolated runtime configured in this session. In-process orchestrator
fully covers the deterministic policy/audit contract; this was
previously manually verified `VERIFIED_EXTERNAL` in an earlier slice
with `services/hermes/` actually running (see `docs/STATUS.md`), not
re-attempted here since nothing about Hermes changed this slice.

## SECRET SCAN

`VERIFIED_LOCAL`: `scripts/secret_scan.py` clean on the full tree, this
slice, after all dependency/CI changes. Frontend build output grepped
for API key names and DB connection strings — none found.

## PUBLIC DOMAIN

`beyondstyle.ae` / `www.beyondstyle.ae` are **not yet attached** to the
Vercel project (`get_project`'s `domains` list contains only
`*.vercel.app` entries). No tool in this session can register a custom
domain purchase or attach an unregistered one without DNS control
information not available here. Target documented and prepared in
`docs/DEPLOYMENT.md`'s CORS section; attaching it is a manual step for
the project owner once DNS is ready.

## BLOCKERS

| # | Blocker | Owner | Exact action |
|---|---|---|---|
| 1 | Backend never deployed anywhere | Project owner (human) | Import repo into Replit, set `DATABASE_URL` + `ALLOWED_ORIGINS` secrets, click Publish. No tool in this session can do this. |
| 2 | `NEXT_PUBLIC_API_URL` not set on Vercel | Project owner (human) | Vercel dashboard → project `frontend` → Settings → Environment Variables → Production → set to the real backend URL from #1 → redeploy. No tool in this session can set a Vercel env var. |
| 3 | Vercel deployment not publicly reachable | Project owner (human), only after security clears | SSO deliberately left enabled per the mandate until Starlette CVEs (below) are resolved. Then disable SSO or attach `www.beyondstyle.ae`. |
| 4 | Starlette has 9 unresolved CVEs | Future dedicated slice | The smallest compatible fix (`fastapi==0.135.0`+`starlette==1.3.1`) was tried and caused a real P0 regression (candidate persistence invisible under real HTTP handling) — reverted, not re-attempted this slice per explicit instruction. Needs a proper bisection/reproduction outside this app before retrying. |
| 5 | `beyondstyle.ae` custom domain not attached | Project owner (human), only after #4 clears | Register/point DNS, then attach in Vercel project settings — deliberately not done yet per the mandate. |
| 6 | Production smoke/E2E/7-name scenario never run against real production URLs | Blocked on 1–2 | Re-run `scripts/production-smoke.py` and the browser E2E scripts with `FRONTEND_URL`/`BACKEND_URL` set to the real deployed URLs, once 1–2 are resolved. |

~~CI run not yet confirmed~~ — **resolved this slice**: run `32884649563` confirmed `success` on all 4 jobs (frontend/secret-scan/backend/e2e), and the two subsequent docs-only commits (`99c5bea`, `912355e` — current HEAD) both also confirmed `success`. `CI = VERIFIED_CI`.

No percentage, no "mostly ready," no assumption about any blocker's
outcome. Everything above this table is real, executed evidence backed
by command/API output; everything in this table is a concrete,
actionable gap with a named owner.
