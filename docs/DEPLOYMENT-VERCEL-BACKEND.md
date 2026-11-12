# Backend on Vercel (replacing Replit)

Status: code ready and tested locally; **not deployed**. The Replit path in
`replit.md` keeps working and is the rollback.

## Why

The production monitor reports the Replit backend URL answering 404 on
`/health`, `/ready`, `/api/ai/status` and the CORS preflight. Replit cannot be
reached or operated from the development sessions that maintain this
repository, so the backend could not be repaired there. Vercel already hosts
the frontend and can be operated from those sessions.

## Shape

| Part | Replit (before) | Vercel (now) |
|---|---|---|
| Runtime | long-lived uvicorn | Vercel Python Function, FastAPI entrypoint `backend/app/main.py`, Python 3.12 (`backend/.python-version`) |
| Project root | repo root, `cd backend` | Vercel project **Root Directory = `backend`** |
| Database | Replit PostgreSQL | managed PostgreSQL (Supabase), **pooled** connection string |
| Customer reference images | local `var/` (lost on redeploy) | `OBJECT_STORAGE=s3` (Supabase Storage S3 endpoint, AWS S3 or R2). Required: `/ready` fails without it |
| Migrations | `alembic upgrade head` before every start | `.github/workflows/migrate-database.yml` (on migration changes to the default branch, or on demand) |
| Commit identity | `BUILD_SHA` file written at build | `VERCEL_GIT_COMMIT_SHA`, reported by `/health` |
| Max request body | 8 MB uploads | 4 MB (Vercel rejects bodies above 4.5 MB; the app answers its own 413 first) |
| Request duration | unbounded | `maxDuration` 300 s (`backend/vercel.json`) |

Code that depends on the host goes through `backend/app/platform.py`
(`VERCEL=1` is set by Vercel). Tests: `backend/tests/test_vercel_platform.py`.

## What behaves differently on Vercel (by design, not hidden)

- **Font registration** (`POST /api/admin/fonts`) returns **409
  READ_ONLY_DEPLOYMENT**. A font written to one instance's `/tmp` would vanish
  and be invisible to other instances. `dry_run=true` inspection still works;
  add approved fonts through the repository and redeploy.
- **Calibration pin** (`POST /api/admin/calibration/apply` with `write=true`)
  returns **409 READ_ONLY_DEPLOYMENT** with the report. Commit the calibrated
  profile to `app/data/workshop_profiles.json` and redeploy, which is also
  the versioned-promotion path CLAUDE.md asks for.
- **Rate limits** are per instance unless `RATE_LIMIT_BACKEND=redis` and
  `REDIS_URL` are set.
- **Candidate generation** runs inline (`BS_BUILD_WORKERS=1`). Measured
  locally under a simulated Vercel environment: about 46 to 49 s for the
  seven-name scenario (32 internal, 31 valid, 10 shown), on a container that
  was also running the test suite. Real Vercel timing is **not measured yet**.
  The production smoke test now allows 180 s for this step.

## Environment variables (set in the Vercel backend project; never commit)

| Variable | Required | Value |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg2://…` using the provider's **pooled** host/port |
| `OBJECT_STORAGE` | yes | `s3` |
| `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION` | yes | private bucket; for Supabase Storage the endpoint is the project's S3 endpoint |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | yes | S3 access keys for that bucket |
| `BS_BUILD_WORKERS` | recommended | `1` |
| `ALLOWED_ORIGINS` | optional | extra exact origins; first-party origins are built in |
| `ADMIN_API_TOKEN`, `REVIEWER_API_TOKEN` | optional | staff screens; unset means every staff route 403s |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_IMAGE_ENABLED` | optional | absent means `SKIPPED_EXTERNAL_MODEL` / `PHOTOREAL_PREVIEW_UNAVAILABLE`, never a fabricated result |
| Customer auth variables | as in `docs/DEPLOYMENT.md` | `/ready → customer_auth` refuses dev echo in production |

GitHub repository secret for migrations: `PRODUCTION_DATABASE_URL` (direct,
non-pooled connection string is safer for DDL). If the password contains `%`,
URL-encode it as `%25` (Alembic reads it through configparser).

## Cutover (needs the owner's approval: creates hosting resources)

1. Database and bucket: create or reuse a Supabase project; create a private
   Storage bucket and S3 access keys.
2. GitHub: add `PRODUCTION_DATABASE_URL`, run **Migrate production database**.
3. Vercel: new project from this repository, Root Directory `backend`,
   production branch = the default branch; set the variables above; deploy.
4. Verify: `/health` reports the pushed commit; `/ready` is `ready` with
   `storage.durability = OBJECT_STORAGE` and `platform.host = vercel`.
5. Frontend: set `NEXT_PUBLIC_API_URL` on the frontend Vercel project to the
   new backend origin and redeploy (the CSP already allows that variable).
6. Update `deploy/production.json → backend_url` and `PRODUCTION_BACKEND` in
   `frontend/next.config.mjs`; push. The Production Monitor must go green.

## Rollback

Set the frontend's `NEXT_PUBLIC_API_URL` back to the previous backend origin
and redeploy the frontend. No data migration is involved in switching hosts
unless production data was already written to the new database.
