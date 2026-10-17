---
name: dashboards
description: How to build staff/production dashboards for Beyond Style on real backend data only — which endpoints exist, how to gate them, how to show "unknown" honestly, and how to lay out metrics with the project design system. Use when adding or changing any /admin page, metric card, chart, or status panel.
---

# Dashboards — real data only

Project-level skill. There is no "claude code dashboards" skill in the
plugin catalogue; this file is the project's standard. The reference
implementation is `frontend/app/admin/page.tsx`.

## 1. Data rules

- Every number is read from a backend endpoint at render time. No client
  side estimates, no cached snapshots, no sample data in production code.
- An endpoint that fails renders an `Alert` or `EmptyState` that names the
  endpoint. Never show `0` for "could not load".
- Slow endpoints (anything that renders proofs: `/api/admin/review/*`,
  `/api/admin/curation/analysis`) load on demand behind a button with a
  `loading` state, never on mount.
- Staff endpoints need `X-Admin-Token`. The token is typed by the operator
  and kept in `sessionStorage` for that tab (`api.setAdminToken`). It is
  never bundled, logged, or put in a URL.
- Human-review verdicts are shown with their evidence status. A family with
  too few reviews stays `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE`; the dashboard
  never promotes it.

## 2. Endpoints available (backend/app)

| Endpoint | Auth | Payload |
|---|---|---|
| `GET /health` | public | `{status, schema_version, build_sha}` |
| `GET /ready` | public | `{status, components{name:{status,…}}}` (503 when not ready; body still complete) |
| `GET /api/ai/status` | public | `{ai_mode, allow_paid_providers, providers{role:{model_id,status,license}}, claude, gpt_image_2, deterministic_fallback}` |
| `GET /api/fonts/registry`, `/api/fonts/styles` | public | font/style registry |
| `GET /api/products/catalogue`, `/size-guide`, `/specifications` | public | product truth tables |
| `GET /api/admin/golden-cases` | admin | `{cases:[{case_id, product_type, memory_tier, evidence_tier, production_result, customer_approved, design_fidelity_score, source_text_status,…}]}` |
| `GET /api/workshop/orders` | admin | `{orders:[{order_id, state, material, rework_count, created_at, history}]}` |
| `GET /api/admin/review/wave-1` | admin or reviewer | slate + `comparison_readiness` (slow) |
| `GET /api/admin/curation/analysis` | admin | evidence, quality_check, comparison_readiness, best_* (slow) |
| `GET /api/admin/calibration/profiles` | admin | workshop calibration profiles |

Typed helpers live in `frontend/lib/api.ts` (`health`, `serviceReadiness`,
`aiStatus`, `listGoldenCases`, `workshopOrders`, `reviewWave1`,
`curationAnalysis`). Add a helper there before calling a new endpoint.

## 3. Layout

- `Stat` cards in a 2/4-column grid at the top: backend, build, readiness,
  components down. Tone is semantic (`ok`/`warn`/`danger`).
- One `Card` per data source, with the endpoint named in the subtitle.
- Bars are plain divs (`Bars`) — the counts are tens of rows and must stay
  legible at 360 px; add a chart library only for time series, and then
  bundle it (no CDN) to keep the CSP.
- Staff pages are LTR (`dir="ltr"`) and English; customer pages are RTL
  Arabic first.
- Keep every `data-testid` prefixed `dash-` so a smoke test can assert the
  page rendered real values (`dash-backend`, `dash-ready`, `dash-golden-total`).

## 4. Verification

- Start Postgres + backend with `ADMIN_API_TOKEN` set, open `/admin`,
  enter the token, confirm the golden-case total equals the row count in
  the database and the readiness list matches `curl /ready`.
- A dashboard change is not done until `npm run build` passes and the
  page renders with the backend down (every card must degrade to an
  honest message).
