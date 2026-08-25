# P0 Release Evidence

**Status: NOT PRODUCTION-READY.** Every check below that could be run
in this environment passed. Two release-gate items (real backend
deployment, and the same checks re-run against real production URLs)
remain genuinely undone — this session has no Replit access and no
tool that can set a Vercel project environment variable. No assumption
is made about their outcome. See "Remaining blockers" at the end.

## Commit

`7313438a0681608238561d1b1bd98d6655ac5a2e` on branch
`claude/p0-golden-path-audit-jtyduw`, pushed to
`ahmadzayan-hub/Beyond-Style-UAE-design-Genertor`.

## Frontend URL (real, deployed)

Vercel project `frontend` (`prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`), linked
to this GitHub repo/branch. Confirmed via the Vercel API:

- Latest deployment: `dpl_DA2HhruJRJjSu9NSHZrEChLd1yhn`
- `githubCommitSha` on that deployment: `7313438a0681608238561d1b1bd98d6655ac5a2e` (exact match to the commit above)
- `readyState`: `READY`
- Build time: ~19.5s (`buildingAt` 1787668974440 → `ready` 1787668993911, epoch ms)
- Production domains: `frontend-sigma-sable-22.vercel.app`, `frontend-celia2026-3923s-projects.vercel.app`
- Runtime errors in the last 1h (checked via `get_runtime_errors`): **0**

**`NEXT_PUBLIC_API_URL` is NOT set on this Vercel deployment** — no
tool available in this session can set a Vercel project environment
variable. Until it is set (manually, by the project owner) and the
project redeployed, the live production frontend cannot reach any
backend, by design (see docs/DEPLOYMENT.md's root-cause writeup from
the prior slice).

## Backend URL (real, deployed)

**None. Not deployed anywhere.** This session has no Replit MCP
connector and no Replit CLI/API token — there is no tool available
here that can create, configure, or publish a Replit deployment.
Nothing was fabricated: no URL, deployment ID, or "verified" claim is
made for a backend host that does not exist. `.replit` (build/run/
deploy config) is prepared and valid TOML but has never been executed.

## Deployment IDs

| Component | ID | State |
|---|---|---|
| Vercel frontend | `dpl_DA2HhruJRJjSu9NSHZrEChLd1yhn` | READY |
| Replit backend | — | NOT DEPLOYED |

## Backend test result

**230/230 passed**, PostgreSQL 16, real Alembic migrations (all local —
no real production backend exists to run tests against).

```
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 93%]
..............                                                          [100%]
[exited with code 0]
```

Includes the 11 new immutable golden-fixture tests
(`backend/tests/test_seven_name_golden_fixture.py`):
`test_exactly_seven_names_in_exact_unicode_and_order`,
`test_no_omitted_substituted_duplicated_or_invented_name`,
`test_nfc_normalization_is_a_no_op_on_this_fixture`,
`test_rtl_preserved`, `test_arabic_identity_verifies_and_covers_every_name`,
`test_generated_design_request_contains_all_seven_names_in_order`, and
5 parametrized `test_arabic_validation_fails_closed_on_any_mutation`
cases (omit last name, duplicate last name, substitute ميثة→فاطمة,
reorder first two, invent an 8th name) — all raise `ApprovalRejected`
and leave the original request untouched.

## E2E result (local — no real production URLs exist to test against)

All 5 browser flows passed, run with the frontend **built against
`NEXT_PUBLIC_API_URL=http://localhost:8000`** — i.e. the exact
production code path (direct browser→backend fetch + real CORS), not
the local-dev-only Next.js rewrite proxy:

```
[text-flow] approved, locked version 1, hash 6b66cbc1788e…
[reference-flow] approved, locked version 1, hash a2c577a59e3e…
[desktop-text-flow] approved, locked version 1, hash e4539d2695a4…
E2E PASSED — evidence in docs/evidence/
COPILOT E2E PASSED — locked edited version 2
[seven-names-flow] approved, locked version 1, hash c4d9b394b761…
SEVEN-NAME E2E PASSED — text preserved exactly: حامد محمد سلطان ميثة حمد خالد مهرة
```

**Real bug found and fixed along the way**: the local-dev-only Next.js
`rewrites()` proxy (`next.config.mjs`, only used when
`NEXT_PUBLIC_API_URL` is unset) has a hard ~30s response cap. The
7-name fixture's real generation time is ~50s, so the FIRST attempt at
this E2E scenario failed — not because of a code defect, but because
it was run against the dev-proxy path instead of the direct-fetch
production path. Confirmed by direct HTTP timing:
  - Direct to backend (`localhost:8000`): candidates call = 49.1s, 200 OK, 10 candidates.
  - Through the Next rewrite proxy (`localhost:3000/api/...`): candidates call = 30.0s, **500 error**.
`e2e/golden_path_e2e.py`'s `run_flow()` now takes a configurable
`generate_timeout_ms` (Playwright client-side wait, unrelated to the
proxy issue); the actual fix was building+running the frontend in
direct-fetch mode, matching how production is architected — the
rewrite proxy is never used in production regardless.

## Production smoke: 15/15 (local — corrected fixture)

```
[PASS] A. frontend loads — status=200
[PASS] B. backend /health — status=200
[PASS] C. backend /ready — status=200
[PASS] K. no sensitive data in /ready
[PASS] D. CORS allows the frontend origin — got='http://localhost:3000'
[PASS] E. Arabic generation request creates a design — status=201
[PASS] E. exact 7-name text preserved byte-for-byte (no substitution/omission/reorder) — got='حامد محمد سلطان ميثة حمد خالد مهرة'
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

(14 checks from the prior slice + the new byte-exact preservation
check added this slice.)

## Exact seven-name test evidence

Fixture: **حامد محمد سلطان ميثة حمد خالد مهرة** (oldest to youngest,
this exact order, this exact Unicode).

- Unit-level: `backend/tests/test_seven_name_golden_fixture.py` (11
  tests, all passing — see "Backend test result" above). Codepoint
  fingerprint locked per name (catches a visually-similar wrong
  character); order locked; membership locked (no invented/omitted/
  duplicated/substituted name); fail-closed on any of the 5 mutation
  cases.
- HTTP-level: `scripts/production-smoke.py` step E asserts
  `normalized_text == "حامد محمد سلطان ميثة حمد خالد مهرة"` exactly —
  PASS (see smoke output above).
- Browser-level, **with the uploaded reference image**, through the
  real customer UI (`e2e/golden_seven_names_e2e.py`):
  `docs/evidence/seven-names-e2e-results.json`:
  ```json
  {
    "text": "حامد محمد سلطان ميثة حمد خالد مهرة",
    "locked_version": "1",
    "approval_hash": "c4d9b394b76198914c8076da83395007b1b4c0472d3921611e53774832a1c1f4",
    "events": [
      "REQUEST_CREATED", "REFERENCE_UPLOADED", "REFERENCE_ANALYZED",
      "BRIEF_UPDATED", "TEXT_CONFIRMED", "CANDIDATES_GENERATED",
      "VERSION_CREATED", "VALIDATION_PASSED", "DESIGN_SELECTED",
      "CUSTOMER_APPROVED", "VERSION_LOCKED"
    ]
  }
  ```
  Screenshots: `docs/evidence/seven-names-flow-{1-start,2-confirm,
  3-proofs,4-selected,5-approved}.png`.
- Real backend runtime log line for this exact request (from
  `/tmp/uv_fresh.log`, structured JSON, `app/observability.py`):
  ```json
  {"request_id": "782fcd33cfe74fdb92e70f7ba678ccdc", "route": "/api/designs/4b281b64-cfcc-46a5-9b0c-87a81e59496f/candidates", "method": "POST", "status": 200, "duration_ms": 51306.69}
  ```

**This was run against local backend+frontend, not a real production
URL** — no production backend exists to run it against yet (see
"Remaining blockers").

## CORS evidence

```
$ curl -i -X OPTIONS http://localhost:8000/api/designs \
    -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST"
HTTP/1.1 200 OK
access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
access-control-allow-headers: Accept, Accept-Language, Content-Language, Content-Type, X-Request-ID, X-Session-Token
access-control-allow-origin: http://localhost:3000
x-request-id: 21f158f4e4624adf9fe188ee3f94f0e3

$ curl -i -X OPTIONS http://localhost:8000/api/designs \
    -H "Origin: https://evil.example.com" -H "Access-Control-Request-Method: POST"
HTTP/1.1 400 Bad Request
Disallowed CORS origin
x-request-id: f58a53b5948f4d15a5c7070a42e2e6e2
```

Allowed origin gets `access-control-allow-origin` echoed back; a
non-configured origin is refused with `400` — no wildcard, no
credentialed CORS (`allow_credentials=False`).

## Database evidence

```
$ psql -c "SELECT version();"
PostgreSQL 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1) on x86_64-pc-linux-gnu

$ psql -c "SELECT version_num FROM alembic_version;"
9520aa9396f0

$ curl http://localhost:8000/ready
{"status": "ready", "components": {
  "database": {"status": "ok"},
  "migrations": {"status": "ok", "revision": "9520aa9396f0"},
  ...
}}
```

`/ready`'s reported migration revision (`9520aa9396f0`) matches the
database's actual `alembic_version` row exactly — the readiness check
is reading real state, not a hardcoded value. 15 real tables present
(`\dt`): `ai_generations`, `ai_jobs`, `alembic_version`,
`customer_approvals`, `customer_briefs`, `design_candidates`,
`design_events`, `design_requests`, `design_versions`, `designs`,
`exports`, `font_references`, `manufacturing_validation_runs`,
`reference_assets`, `reference_dna`.

This is the LOCAL PostgreSQL 16 instance in this sandbox — no real
production database exists yet (see "Remaining blockers").

## Runtime logs

Structured JSON, one line per request (`app/observability.py`), no
secrets/raw images:

```
{"request_id": "782fcd33cfe74fdb92e70f7ba678ccdc", "route": "/api/designs/.../candidates", "method": "POST", "status": 200, "duration_ms": 51306.69}
{"request_id": "06cdabb9f5784c63b6b285c249017cec", "route": "/api/designs/.../select", "method": "POST", "status": 201, "duration_ms": 125.13}
{"request_id": "2849e6e689a24ac29cc109148ebe9b61", "route": "/api/versions/...", "method": "GET", "status": 200, "duration_ms": 17.55}
{"request_id": "e99b864b175a4c718c2e646d272adcb9", "route": "/api/ai/status", "method": "GET", "status": 200, "duration_ms": 22.7}
{"request_id": "21f158f4e4624adf9fe188ee3f94f0e3", "route": "/api/designs", "method": "OPTIONS", "status": 200, "duration_ms": 0.38}
{"request_id": "f58a53b5948f4d15a5c7070a42e2e6e2", "route": "/api/designs", "method": "OPTIONS", "status": 400, "duration_ms": 0.33}
{"request_id": "4a4575247a9346e8b7c77aef8f58375e", "route": "/ready", "method": "GET", "status": 200, "duration_ms": 17.47}
```

## Remaining blockers (release NOT closed)

1. **No real backend deployment.** No Replit access in this session
   (no MCP connector, no CLI/API token). `.replit` is prepared; the
   backend has never run outside this local sandbox. Manual action
   (per `docs/DEPLOYMENT.md`): import this repo into Replit, set
   `DATABASE_URL`/`ALLOWED_ORIGINS` secrets, click Publish.
2. **`NEXT_PUBLIC_API_URL` not set on the Vercel project.** No tool in
   this session can set a Vercel environment variable. Manual action:
   set it to the real Replit URL from step 1 in the Vercel dashboard
   (Settings → Environment Variables, Production), then redeploy.
3. Once 1 and 2 are done, re-run against the real URLs:
   `python3 scripts/production-smoke.py` (with `FRONTEND_URL`/
   `BACKEND_URL` set to the real URLs — this closes item E/F/H/I/J
   from the smoke checklist against production for the first time),
   and manually verify the exact 7-name scenario through the live
   production UI (this document's browser-level evidence is local
   only).
4. GitHub Actions CI (`.github/workflows/ci.yml`,
   `external-ai-acceptance.yml`, `deployment-smoke.yml`) has not been
   observed running on GitHub itself yet — only validated locally
   (YAML parse + the same commands run by hand).

**No "production ready" claim is made.** This document records exactly
what has and has not been verified, with real command output for
everything claimed done.
