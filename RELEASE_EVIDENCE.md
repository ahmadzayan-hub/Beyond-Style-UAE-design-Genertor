# Release Evidence — P1 Production Deployment Closure

**FINAL RELEASE DECISION: NOT PRODUCTION READY.**

Every check that could be executed against real infrastructure from
this session was executed and is recorded below with real command
output — no check is claimed done without it. Two hard blockers,
verified (not assumed) to be outside this session's tool access,
prevent full closure: no backend has ever been deployed anywhere, and
the one Vercel frontend deployment that exists is not publicly
reachable. See "FINAL RELEASE DECISION" at the end for the exact
blocker/owner/action list.

## COMMIT SHA

`680aa1d9934becb13e331c5bb8e4b88b31ec6484` on branch
`claude/p0-golden-path-audit-jtyduw`,
`ahmadzayan-hub/Beyond-Style-UAE-design-Genertor`. Confirmed via
`git merge-base --is-ancestor` that HEAD descends from the prior
closure commit `1e1fa6c`.

## FRONTEND PRODUCTION URL

Real Vercel project `frontend` (`prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`),
confirmed via the Vercel API (`get_project`/`get_deployment`), not
assumed:

- Latest deployment: `dpl_6aMGbMLjF1Z3yCexXRQfn6tEGJEE`, `readyState: READY`, `target: production`
- `githubCommitSha` on that deployment: `680aa1d9934becb13e331c5bb8e4b88b31ec6484` — **exact match** to this document's commit
- Domains: `frontend-sigma-sable-22.vercel.app`, `frontend-celia2026-3923s-projects.vercel.app`, `frontend-git-claude-p0-golden-p-b26d96-celia2026-3923s-projects.vercel.app`
- Runtime errors (`get_runtime_errors`, 24h window): **0**
- Runtime logs (`get_runtime_logs`, 24h window): **0 log lines found** — consistent with the finding below that the site is receiving no real traffic

**This deployment is NOT publicly reachable as a working product.** Two independent, verified reasons:

1. **Vercel Authentication (SSO) is enabled on the project**
   (`get_project_deployment_protection`: `ssoProtection.enabled: true`,
   `deploymentType: all_except_custom_domains`). None of the project's
   three domains is a custom domain — all are `*.vercel.app` — so
   **every one of them requires a Vercel login to view**. A real
   customer hitting any of these URLs today gets Vercel's auth wall,
   not the app.
2. **This session's own network egress is blocked to `vercel.app`.**
   `curl https://frontend-sigma-sable-22.vercel.app/` failed with
   `CONNECT tunnel failed, response 403`; the agent-proxy status
   endpoint confirms this as a policy denial, not a transient error:
   ```
   "recentRelayFailures": [
     {"kind": "connect_rejected",
      "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
      "host": "frontend-sigma-sable-22.vercel.app:443"}
   ]
   ```
   Per this environment's own proxy documentation: "do not retry
   organization policy denials — report them instead." This session
   therefore could not load the production URL in a real browser
   (Playwright) or via `curl`/`WebFetch` to verify it end-to-end, even
   setting the SSO issue aside.

**`NEXT_PUBLIC_API_URL` is still not set** — no tool available in this
session (Vercel MCP tools here are read-only for project config: only
`get_project_deployment_protection`/`update_project_deployment_protection`
for auth settings, `list_deployments`/`get_deployment`/build-logs/
runtime-logs/errors — no env-var write endpoint) can set a Vercel
project environment variable. Even if the SSO/egress issues above were
resolved, the deployed frontend still cannot reach any backend.

## BACKEND PRODUCTION URL

**None. Not deployed anywhere.** Re-confirmed this slice: no Replit MCP
connector, no Replit CLI/API token (`ToolSearch` for "replit" returns
no matching tool). No other backend-hosting tool available in this
session can run a Python/FastAPI process (the Supabase MCP tools
present manage Postgres + Deno edge functions only, not a Python ASGI
app — using them would mean rewriting the backend, which is out of
scope for a deployment-closure pass). `.replit` (build/run/deploy
config) is prepared and valid but has never been executed outside this
sandbox.

## DEPLOYMENT IDs

| Component | ID | State |
|---|---|---|
| Vercel frontend | `dpl_6aMGbMLjF1Z3yCexXRQfn6tEGJEE` | READY (SSO-gated, not publicly reachable) |
| Replit backend | — | NOT DEPLOYED |

## DATABASE CONNECTIVITY

**Production: none exists.** No backend is deployed, so no
`DATABASE_URL` has ever been configured against a real production
database. Local PostgreSQL 16 (this sandbox) is real and verified:

```
$ psql -c "SELECT version();"
PostgreSQL 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1) on x86_64-pc-linux-gnu

$ psql -c "SELECT version_num FROM alembic_version;"
9520aa9396f0

$ curl http://localhost:8000/ready
{"status": "ready", "components": {
  "database": {"status": "ok"},
  "migrations": {"status": "ok", "revision": "9520aa9396f0"}, ...
}}
```
`/ready`'s reported migration revision matches the database's actual
`alembic_version` row exactly — the readiness check reads real state.

## DATABASE PERSISTENCE

Not verifiable in production (no deployment exists to restart). Locally,
migrations were run forward-only (`alembic upgrade head`) against a
from-scratch database three times this slice (once per clean-venv
dependency-bump validation) with no data-loss operation in any
migration — `.replit`'s deploy command runs `alembic upgrade head`
only, never `downgrade`/`stamp`/a destructive command.

## BACKEND TEST RESULT

**230/230 passed**, verified THREE separate ways this slice, not just
reused from before:

1. This sandbox's existing environment (pre-seeded packages): 230/230.
2. **From-scratch clean venv** (`python3 -m venv` + `pip install -r
   requirements.txt` only, nothing pre-seeded) with the pillow +
   python-multipart bump: 230/230, exit code 0.
3. Same clean venv, adding the fonttools bump on top (all three
   dependency changes together): 230/230, exit code 0.

Step 2/3 exist specifically because step 1 alone was misleading: this
sandbox had a stray `python-multipart` package installed outside
`requirements.txt`, silently masking a real bug (see "SECURITY RESULT"
below) that a genuinely clean install — like GitHub's runner, or a
fresh Replit deploy — would hit immediately.

## SMOKE RESULT

**15/15**, local (`FRONTEND_URL`/`BACKEND_URL` = localhost — no real
production URLs exist to point this at; re-run this slice against the
Pillow/python-multipart/fonttools-upgraded backend to confirm no
regression):

```
[PASS] A. frontend loads — status=200
[PASS] B. backend /health — status=200
[PASS] C. backend /ready — status=200
[PASS] K. no sensitive data in /ready
[PASS] D. CORS allows the frontend origin — got='http://localhost:3000'
[PASS] E. Arabic generation request creates a design — status=201
[PASS] E. exact 7-name text preserved byte-for-byte — got='حامد محمد سلطان ميثة حمد خالد مهرة'
[PASS] G. reference upload request — status=201
[PASS] confirm exact text — status=200
[PASS] F. exactly 10 candidate designs returned — status=200 count=10
[PASS] K. no sensitive data in /candidates
[PASS] H. candidate select — status=201
[PASS] I. manufacturing validation passed — status=200
[PASS] J. external AI status endpoint reachable — status=200
[PASS] K. no sensitive data in /api/ai/status

15/15 checks passed.
```

## E2E RESULT

**5/5 browser flows passed**, local, frontend built with
`NEXT_PUBLIC_API_URL=http://localhost:8000` (the production code path —
direct browser→backend fetch, not the dev-only rewrite proxy):

```
[text-flow] approved, locked version 1, hash 6b66cbc1788e…
[reference-flow] approved, locked version 1, hash a2c577a59e3e…
[desktop-text-flow] approved, locked version 1, hash e4539d2695a4…
[seven-names-flow] approved, locked version 1, hash c4d9b394b761…
COPILOT E2E PASSED — locked edited version 2
```

No real production URL exists to run these against.

## 7-NAME GOLDEN-PATH RESULT

Fixture: **حامد محمد سلطان ميثة حمد خالد مهرة** (oldest to youngest,
exact order, exact Unicode) — verified at three levels, all local:

- **Unit**: `backend/tests/test_seven_name_golden_fixture.py` (11
  tests) — exact count, per-name codepoint fingerprint, exact order,
  no omission/substitution/duplication/invention, RTL preserved, all 7
  names present in every one of 10 generated candidates, and 5
  parametrized mutation cases all fail closed (`ApprovalRejected`,
  request stays `DRAFT`).
- **HTTP**: `scripts/production-smoke.py` step E — byte-exact
  `normalized_text` match, PASS.
- **Browser, with the uploaded reference image**, through the real
  customer UI (`e2e/golden_seven_names_e2e.py`):
  `docs/evidence/seven-names-e2e-results.json` — locked version 1,
  hash `c4d9b394b76198914c8076da83395007b1b4c0472d3921611e53774832a1c1f4`,
  full event trail (`REFERENCE_UPLOADED` → `REFERENCE_ANALYZED` → … →
  `CUSTOMER_APPROVED` → `VERSION_LOCKED`). Screenshots:
  `docs/evidence/seven-names-flow-{1-start,2-confirm,3-proofs,
  4-selected,5-approved}.png`.

**Not run through the live production UI** — no live, publicly
reachable production UI exists (see "FRONTEND PRODUCTION URL" above).

## REFERENCE IMAGE RESULT

Verified this slice against the local backend with the
Pillow/python-multipart-upgraded dependency set:

- Normal upload (valid PNG, reference to a real `design_id`): `201`.
- **Oversized upload (9MB PNG, 8MB limit)**: `413`, structured error,
  no stack trace:
  ```
  status=413
  {"detail":"File exceeds the maximum allowed size.","error_code":"REFERENCE_NOT_READY","request_id":"f6ca92b5360d4839a4803d623aedd151"}
  ```
  Matching runtime log line:
  ```json
  {"request_id": "f6ca92b5360d4839a4803d623aedd151", "route": "/api/designs/db0a7d97-c87e-450f-90ab-c6a5129cd1ec/references", "method": "POST", "status": 413, "duration_ms": 9320.19}
  ```

## CORS POSITIVE/NEGATIVE RESULT

```
$ curl -i -X OPTIONS http://localhost:8000/api/designs \
    -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST"
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:3000

$ curl -i -X OPTIONS http://localhost:8000/api/designs \
    -H "Origin: https://evil.example.com" -H "Access-Control-Request-Method: POST"
HTTP/1.1 400 Bad Request
Disallowed CORS origin
```
No wildcard, no credentialed CORS (`allow_credentials=False`).
`ALLOWED_ORIGINS` has no production default in code (confirmed by
reading `app/main.py`) — it must be explicitly set wherever the
backend is deployed; it is currently unset anywhere in production
because no production backend exists.

## SECURITY RESULT

**Full dependency vulnerability scan run this slice** (`pip-audit` on
`backend/requirements.txt`, `npm audit` on `frontend/package.json`) —
not previously done in this session:

**Fixed and verified** (all three together pass the full 230-test suite
in a from-scratch clean venv — see "BACKEND TEST RESULT"):
- **`python-multipart` — real, previously-undiscovered deployment
  blocker**, not just a CVE. Required by FastAPI's `Form()`/`File()`
  multipart parsing (the reference-image upload endpoint) but never
  pinned in `requirements.txt`. This sandbox had it installed as a
  stray package, masking the gap; a genuinely clean install — GitHub
  Actions' runner, or a fresh Replit deploy — fails at test-collection
  time with `RuntimeError: Form data requires "python-multipart" to be
  installed`. **This is exactly why every one of the 9 prior GitHub
  Actions CI runs on this branch failed** (confirmed by pulling the
  real job logs — see "known limitations" below for the current CI
  run's status). Fixed: pinned `python-multipart==0.0.31` (0 known
  CVEs; the previously-implicit 0.0.9 had 7).
- **Pillow 10.4.0 → 12.3.0**: patches 24 known CVEs, including several
  native heap out-of-bounds writes reachable via untrusted image input
  — directly relevant since Pillow processes every customer-uploaded
  reference image (`app/security/uploads.py`).
- **fonttools 4.53.1 → 4.60.2**: patches CVE-2025-66034 (arbitrary file
  write via the `fontTools.varLib` CLI script). Low real relevance —
  this app only uses fonttools for glyf/CFF parsing and never invokes
  that script — patched anyway since it's a safe same-major bump.

**Found, NOT fixed this slice — real, unresolved, and reported rather
than silently left out:**
- **Next.js 14.2.13 — `npm audit` reports 1 Critical, 1 High**, with
  the fix requiring `next@16.3.3` (two major versions up). This is a
  framework-level upgrade with real breaking-change risk (App Router
  API changes across two majors) that cannot be safely validated within
  this pass's scope ("do not redesign/refactor unless required to fix a
  blocker" — and a blind 2-major bump without a dedicated regression
  pass would itself be an uncontrolled production risk). **Reported as
  an open release blocker**, not fixed.
- **Starlette 0.38.6 — 9 known CVEs** (multipart form-data DoS/text-
  field confusion, `StaticFiles` path handling, Host-header URL
  reconstruction), fix versions 1.0.1–1.3.1. Checked precisely: FastAPI
  `0.115.0` requires `starlette>=0.37.2,<0.39.0` — the patched
  versions are outside that range, so fixing this requires a
  coordinated FastAPI major-version upgrade too, with its own
  regression risk. **Reported as an open release blocker**, not forced
  through in this pass.

**No secrets found anywhere checked**: `scripts/secret_scan.py` (repo-
wide) — clean. `frontend/.next` build output grepped for
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`sk-ant-`/`sk-proj-`/DB connection
strings — none found. Production debug: no `debug=True`/`--reload` in
`app/main.py`; `.replit`'s deploy command has no `--reload`. Error
responses: confirmed structured (`error_code`+`request_id`), never a
raw stack trace, on 422/413/400 paths tested live this slice.

## RUNTIME LOG RESULT

Real structured JSON request logs captured this slice
(`app/observability.py`'s `CorrelationIdMiddleware`), against the
Pillow/python-multipart-upgraded backend:

```json
{"request_id": "e07e5ca6549444caac12c1c4dc44f871", "route": "/api/designs/31d35fc6-f373-48d3-ba96-e4c0bf7e3e96/references", "method": "POST", "status": 201, "duration_ms": 29.02}
{"request_id": "f6ca92b5360d4839a4803d623aedd151", "route": "/api/designs/db0a7d97-c87e-450f-90ab-c6a5129cd1ec/references", "method": "POST", "status": 413, "duration_ms": 9320.19}
```

No production runtime logs exist because no production backend exists.
Vercel's own runtime-log/error tooling (`get_runtime_logs`,
`get_runtime_errors`) confirms **0 log lines and 0 errors** for the
frontend deployment in the last 24h — consistent with the SSO/egress
findings above (nothing is reaching it).

## KNOWN LIMITATIONS

1. **GitHub Actions CI — real, previously unexamined finding**: all 9
   prior CI runs on this branch actually ran on GitHub and **failed**
   (`conclusion: "failure"` on every one, verified via
   `actions_list`/`get_job_logs` — not previously checked in this
   session; `docs/STATUS.md` had incorrectly said CI was "not yet
   observed running on GitHub"). Root cause: the `python-multipart` gap
   above. The fix (commit `680aa1d`) triggered CI run
   [`32872953221`](https://github.com/ahmadzayan-hub/Beyond-Style-UAE-design-Genertor/actions/runs/32872953221):
   `secret-scan` and `frontend` jobs completed **success**; the
   `backend` job's test-collection error is confirmed gone (all steps
   through "Migrations up/down/up" succeeded, and the test-suite step
   is genuinely executing rather than failing at collection, unlike
   every prior run) — **but the run was still `in_progress` as of this
   report** and this document does not claim a pass it has not
   observed. Check the run URL above for the current status.
2. No real production URL exists for any of: production smoke,
   backend test suite, E2E, or the 7-name scenario to be run against.
   Every result above is local.
3. Next.js Critical CVE and Starlette CVEs remain open (see "SECURITY
   RESULT") — deliberately not force-fixed this slice given the
   breaking-change risk of the required major upgrades.
4. `frontend`'s only route is `/` (no dynamic/deep-link routes exist in
   `app/`) — "deep-link" testing from item 5 does not apply to this
   app's actual routing surface; a refresh of `/` was exercised
   implicitly at the start of every E2E flow.
5. Database persistence across a real restart/redeploy is unverified
   (no deployment to restart).

## ROLLBACK METHOD

- **Frontend (Vercel)**: every prior deployment remains addressable
  and most are marked `isRollbackCandidate: true` in the Vercel API;
  rolling back means promoting an earlier deployment ID to production
  via the Vercel dashboard/CLI, or reverting the git commit and letting
  the GitHub integration redeploy. No destructive action is required —
  Vercel deployments are immutable and additive.
- **Backend (Replit, once deployed)**: `.replit`'s deploy `run` step
  only ever runs `alembic upgrade head` (forward-only) before serving —
  never a destructive migration. Rolling back the backend means
  redeploying an earlier commit; because migrations are additive/
  forward-only by convention in this codebase (no destructive migration
  exists in the tree), an older app version continues to work against a
  newer schema as long as no column the older code depends on was
  dropped (none have been).
- **Database**: no production database exists yet, so there is nothing
  to roll back. Once one exists, standard point-in-time recovery is
  whatever the hosting platform's Postgres offering provides — not
  configured or verified in this session.

## FINAL RELEASE DECISION

# NOT PRODUCTION READY

Exact remaining blockers, each with owner and required action:

| # | Blocker | Owner | Exact action |
|---|---|---|---|
| 1 | Backend has never been deployed anywhere | Project owner (human) | Import this repo into Replit, set `DATABASE_URL` + `ALLOWED_ORIGINS` secrets (see `backend/.env.example`), click Publish. No tool in this session can do this. |
| 2 | `NEXT_PUBLIC_API_URL` not set on the Vercel project | Project owner (human) | In the Vercel dashboard (project `frontend`, `prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`) → Settings → Environment Variables → Production, set `NEXT_PUBLIC_API_URL` to the real backend URL from step 1, then redeploy. No tool in this session can set a Vercel env var. |
| 3 | The one Vercel deployment that exists is not publicly reachable | Project owner (human) | Disable Vercel Authentication (SSO) for this project, or attach and use a custom domain (SSO is scoped to `all_except_custom_domains`). Currently every `*.vercel.app` URL for this project requires a Vercel login. |
| 4 | Next.js has 1 unresolved Critical + 1 High `npm audit` finding | Future dedicated slice | Upgrade `next` 14.2.13 → 16.3.3 (2 majors) with a full regression pass (App Router changes across two majors) — explicitly out of scope for a safe deployment-closure pass. |
| 5 | Starlette has 9 unresolved CVEs | Future dedicated slice | Requires a coordinated FastAPI upgrade first (`fastapi==0.115.0` pins `starlette<0.39.0`; all Starlette fixes are `>=0.40.0`) — explicitly out of scope here. |
| 6 | CI run for the fix that resolves 9/9 prior failures was still in progress when this report was written | Re-check | See run [`32872953221`](https://github.com/ahmadzayan-hub/Beyond-Style-UAE-design-Genertor/actions/runs/32872953221) for the now-current status; do not assume it passed. |
| 7 | Production smoke/E2E/7-name scenario never run against real production URLs | Blocked on 1–3 | Re-run `python3 scripts/production-smoke.py` with real `FRONTEND_URL`/`BACKEND_URL`, and re-run the browser E2E scenario against the live production UI, once 1–3 are resolved. |

No percentage, no "mostly ready," no assumption about any blocker's
outcome. Everything above this table is real, executed evidence;
everything in this table is a concrete, actionable gap.
