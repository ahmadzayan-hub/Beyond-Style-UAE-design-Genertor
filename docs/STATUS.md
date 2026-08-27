# STATUS

Statuses (general sections below): VERIFIED (automated tests + evidence) / PARTIAL / FALLBACK / DISABLED / UNAVAILABLE / NOT_IMPLEMENTED.
Statuses (External AI / Real Tool Wiring sections, precise per-claim vocabulary):
  VERIFIED_LOCAL — real code path executed against a real local dependency (PostgreSQL, engines) in this environment.
  VERIFIED_EXTERNAL — a real external provider/runtime call actually executed and returned (Claude/GPT-Image-2/isolated Hermes).
  VERIFIED_E2E — proven through a full HTTP/browser round trip, not just a unit call.
  AVAILABLE_NOT_VERIFIED — code is real/wired but has not itself been executed in this environment (e.g. no docker daemon).
  SKIPPED_NO_CREDENTIALS — the honest-skip branch ran (no API key); the real-call branch is implemented but unexercised here.
  OPTIONAL_NOT_RUNNING — an optional runtime (isolated Hermes) is not configured/reachable; the deterministic path is unaffected.
  BLOCKED — implemented but intentionally refused (e.g. approve_design for agents).
  FAILED — a real call/round-trip was attempted and errored (never silently downgraded to a softer status).
Updated: 2026-08-26 · Backend suite: 382 passed (357 + 25 Curation Analysis) (PostgreSQL 16, incl. 11-test immutable seven-name golden fixture) · E2E: 5 browser flows passed (incl. dedicated seven-name+reference flow) · production smoke: 15/15 checks passed (local, corrected fixture) · GitHub Actions CI: VERIFIED_CI, run 32900447345 (current HEAD `a7e3858`) conclusion=success — 5 consecutive green runs — see RELEASE_EVIDENCE.md.

## P2 Curation Analysis + Customer Validation (this slice)
Machinery to turn human review decisions into aesthetic and commercial recommendations — built, tested, and
reporting **INSUFFICIENT_HUMAN_REVIEW_EVIDENCE** because no human review decisions exist yet. See CURATION_STATUS.md.

| Item | Status | Evidence |
|---|---|---|
| Aesthetic/commercial signals derive from human scores only | VERIFIED_LOCAL | `test_engineering_values_never_move_an_aesthetic_signal`; `excluded_inputs` recorded in every output |
| Customer responses stored separately, never merged with expert scores | VERIFIED_LOCAL | `test_customer_scores_never_enter_expert_signals`; own table + own migration |
| Customer responses anonymous + append-only | VERIFIED_LOCAL | `test_customer_responses_are_anonymous_and_append_only` (no name/email/phone column; DB triggers) |
| Family claims refuse to guess below threshold | VERIFIED_LOCAL | `test_best_family_refuses_to_guess_without_evidence`, `test_thin_evidence_is_excluded_with_a_reason` |
| Four family claims stay distinct | VERIFIED_LOCAL | `test_the_four_family_claims_have_different_bases` |
| Hard gates beat approval in commercial class | VERIFIED_LOCAL | `test_hard_gate_beats_approval_in_commercial_class` |
| Golden relevance may be reported as NOT predictive | VERIFIED_LOCAL | `test_golden_can_be_reported_as_not_predictive` |
| Quality check flags but never edits reviewer decisions | VERIFIED_LOCAL | `test_contradictory_reviews_are_flagged_not_resolved`; `reviewer_decisions_modified: 0` |
| Customer board leaks no engineering metadata | VERIFIED_LOCAL | leak scan over `review-board.html`: 0 tokens |

**Honest status:**
- **0 human reviews, 0 customer responses.** BEST_AESTHETIC / BEST_COMMERCIAL / BEST_CUSTOMER_FAMILY are all
  `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` (0/9 products). BEST_ENGINEERING_FAMILY unchanged and still ENGINEERING_ONLY.
- **Commercial curation**: 0 RECOMMENDED, 0 CANDIDATE, 25 DESIGN_EXPERIMENT, 11 HIDDEN (all 11 on hard gates).
- **Golden predictiveness UNDETERMINED** — no reviewed items in both groups to compare.
- **The customer pack (13 items) is NOT aesthetically curated**; basis is `MANUFACTURING_PASS_AND_DIVERSITY_ONLY`
  and the pack records that. It is usable for real customer testing today, before AD review.
- Thresholds are deliberately strict (5 scored reviews across 3+ items per family; 2 reviewers for HIGH
  confidence; 10 customer responses per family). They can be lowered, but not without weakening the claim.

## Human Aesthetic Review Workflow (previous slice)
The workflow, review pack and evidence exist. **No aesthetic decision has been made by anyone.** 52 features
remain EXPERIMENTAL, every item is HUMAN_REVIEW_PENDING, and `human-scores.json` holds zero reviews.
Golden Path and its immutable fixture byte-unchanged.

| Item | Status | Evidence |
|---|---|---|
| Review unit is a combination (font+features+axes+product+composition+text+proof) | VERIFIED_LOCAL | `test_review_item_is_a_combination_not_a_font`; same font + different product = different item |
| Human approval cannot open Arabic / manufacturing / rights gates | VERIFIED_E2E | `test_human_approval_cannot_open_a_hard_gate` (all 3); real HTTP APPROVE on a failing item → HIDDEN |
| PRODUCTION_RECOMMENDED needs all gates + APPROVE + no critical score < 3 | VERIFIED_LOCAL | `test_weak_critical_score_downgrades_approve_to_allowed` |
| Promotion is product-specific, never global | VERIFIED_LOCAL | `test_promotion_is_product_specific_not_global` (pendant RECOMMENDED / ring ALLOWED / cufflink EXPERIMENTAL) |
| Review history append-only, enforced by DB triggers | VERIFIED_LOCAL | `test_reviews_cannot_be_updated_or_deleted`, `test_review_history_is_append_only` |
| AI advisory cannot promote; never merged into human scores | VERIFIED_LOCAL | `test_ai_advisory_never_promotes_without_a_human`; status SKIPPED_NO_CREDENTIALS |
| Customer sees friendly style words; OT tags stay internal | VERIFIED_LOCAL | `test_review_item_shows_customer_style_not_raw_tags` |
| Art Director screen (`/admin/review`) | VERIFIED_E2E | 403 without token; 18-item pack with proofs over real HTTP; ships as a Next.js route |
| Preparing a pack creates no review rows | VERIFIED_LOCAL | `test_no_review_rows_are_created_by_generating_a_pack` |
| 52 features NOT marked reviewed by this slice | VERIFIED_LOCAL | `test_features_are_not_marked_reviewed_by_this_slice` |

**Honest status:**
- **HUMAN_REVIEW_PENDING. 0 human decisions recorded.** 36 items generated across 9 products; 25 EXPERIMENTAL
  (awaiting review), 11 HIDDEN on engineering grounds alone. Zero RECOMMENDED, zero ALLOWED — correctly, since
  no one has reviewed anything.
- **AI advisory unavailable**: `SKIPPED_NO_CREDENTIALS`, no `ANTHROPIC_API_KEY`. No advisory scores were invented.
- **BEST_AESTHETIC_FAMILY and BEST_COMMERCIAL_FAMILY do not exist yet** and are deliberately absent. The existing
  best-family table remains labelled ENGINEERING_ONLY.
- The review pack samples the space (≤1 item per font family per product); it is a prioritised starting set, not
  exhaustive coverage of every safe variant.

## Variable-Font Axis Plumbing + Real-mm Validation (previous slice)
Variable-font coordinates are now first-class production inputs: validated, carried identically through shaping
AND outline extraction from one shared instance, part of design identity, traceable in exports, and gated on
real millimetres. Golden Path and its immutable fixture byte-unchanged.

| Item | Status | Evidence |
|---|---|---|
| Shaping + outlines share one instance (`app/fonts/instances.py`) | VERIFIED_LOCAL | `test_shaping_and_outlines_use_the_same_instance`; weight visibly thickens built geometry |
| Invalid / unsupported axis refused, never clamped | VERIFIED_LOCAL | `AXIS_VALUE_OUT_OF_RANGE`, `UNSUPPORTED_AXIS`; validated in the shared build path so designer edits are covered |
| Axes in design identity; empty axes leave pre-axis hashes untouched | VERIFIED_LOCAL | `test_empty_axes_do_not_change_pre_axis_candidate_ids`; golden fixture unchanged |
| Weight change creates a NEW version; approved version untouched | VERIFIED_LOCAL | `test_changing_axes_creates_a_new_version_never_mutates_approved` |
| Export metadata carries font_id + axes + features + font binary sha256 | VERIFIED_LOCAL | `test_export_metadata_carries_axes_and_font_binary`; DXF custom vars too |
| Real-mm measurements drive manufacturing decisions | VERIFIED_LOCAL | `app/engines/geometry_metrics.py`, basis `REAL_MM_FROM_BUILT_GEOMETRY`; proxy asserted absent |
| Axis ranges revalidated on real geometry, per product | VERIFIED_LOCAL | `geometry-mm-validation.json`, `product-axis-ranges.json`: wght 400–700 GEOMETRY_VERIFIED_SAFE on 8/8 products × 3 fonts |
| Weight combinations revalidated through real geometry | VERIFIED_LOCAL | `combination-revalidation.json`: 4/5 PRODUCTION_CAPABLE |
| Long-text probe uses the real production adaptation | VERIFIED_LOCAL | multi_name + medallion now manufacturable → 12/12 products covered |
| Seven names preserved at 16/48 | VERIFIED_LOCAL | unchanged, stacked multi-line, source text preserved |
| Designer slider bounded to verified range; customer sees no numbers | VERIFIED_LOCAL | `designer_axis_bounds`, `test_customer_never_receives_numeric_axis_values` |

**Honest limitations and one corrected claim:**
- **The earlier font-unit axis ranges were WRONG and are not promoted.** The proxy flagged small-size Reem Kufi
  unsafe above wght=400 on a fill-ratio ceiling; real built geometry shows 2.4–2.5mm counter clearance holding
  across the full range, with material only increasing. The proxy measured raw glyph fill, not the manufactured
  piece. Real-geometry verdicts supersede it.
- **8/8 products safe reads permissive but is gate-limited, not gate-free**: only 1–2 of 4 configurations pass at
  each grid point, and Nastaliq weight+stacking is NOT_PRODUCTION_CAPABLE — both gates are genuinely binding.
- **Aesthetics unchanged**: 52 features EXPERIMENTAL, 3 dimensions NOT_ASSESSED. No aesthetic approval happened.
- **Axis coverage is `wght` only** — the three variable fonts expose no other axis.
- **Safe ranges are for one workshop profile** (pendant / silver-925); other materials are NOT_TESTED.

## Aesthetic Curation + Combination/Axis Safety (previous slice)
Machinery for aesthetic curation, with taste left to humans. 10 of 13 suitability dimensions are measured from
real geometry; 3 are `NOT_ASSESSED` pending human review. All 52 discovered OT features stay EXPERIMENTAL and
are hidden from customers. Golden Path and its immutable fixture unchanged.

| Item | Status | Evidence |
|---|---|---|
| Product-specific suitability, 9 fonts × 12 products, never one universal score | VERIFIED_LOCAL | `test_suitability_is_product_specific_not_universal`; `scores.json` |
| 3 aesthetic dimensions never auto-scored | VERIFIED_LOCAL | `test_aesthetic_dimensions_are_never_auto_scored` |
| Aesthetic score cannot override manufacturing failure | VERIFIED_LOCAL | `test_aesthetic_score_cannot_override_manufacturing_failure`, `test_unmanufacturable_font_is_never_recommended` |
| 17 curated combinations tested; only COMPATIBLE ships | VERIFIED_LOCAL | `combination-matrix.json`; 15 COMPATIBLE, 2 REDUNDANT, 0 UNSAFE |
| Variable-axis safe ranges from real fontTools instancing | VERIFIED_LOCAL | `variable-axis-safety.json`; unsafe extremes excluded by test |
| Experimental/hidden variants excluded from customer bundles | VERIFIED_E2E | `test_hidden_variant_is_excluded_from_customer_ranking`; `GET /api/admin/curation` → 52 awaiting review |
| Customer style picker exposes no raw OT tags | VERIFIED_E2E | `test_customer_style_language_never_exposes_raw_ot_tags`; `GET /api/fonts/styles` |
| Seven names resolved with no constraint weakened | VERIFIED_LOCAL | `seven-name-report.json`: 16/48 valid, stacked multi-line, source text unchanged |
| Golden Production evidence outranks AI opinion and influences products | VERIFIED_LOCAL | `test_golden_case_influences_the_matching_products` |
| Diwani/Thuluth cannot be selected via curation | VERIFIED_LOCAL | `test_classical_diwani_and_thuluth_cannot_be_selected_through_curation` |

**Honest limitations:**
- **No aesthetic review has happened.** 52 features EXPERIMENTAL, 3 dimensions NOT_ASSESSED. This slice built the
  machinery and the proof sheets; a human at Beyond Style must still look at them. Nothing here is a taste verdict.
- ~~Variable-axis ranges measured but NOT renderable~~ — **RESOLVED** by the axis-plumbing slice; those font-unit
  ranges were also contradicted by real geometry and are now marked `SUPERSEDED_BY_GEOMETRY_VERIFIED_RANGES`.
- ~~Combination geometry shaping-verified only~~ — **RESOLVED**: weight-bearing combinations revalidated through
  real built geometry (4/5 PRODUCTION_CAPABLE).
- **The stroke figure in `app/fonts/axes.py` is still a relative proxy**, not a millimetre width. It is now
  explicitly excluded from the manufacturing surface, which uses `geometry_metrics` real mm.
- ~~2 of 12 products have no manufacturable option~~ — **RESOLVED**: the probe now uses the production long-text
  adaptation; 12/12 products covered.

## Font Capability (previous slice)
Advertised script coverage now equals renderable coverage. Nine OFL fonts, every feature discovered from the
font binaries, every optional feature regression-shaped before exposure. The ranked-10 Golden Path and its
immutable golden fixture are unchanged — new families sit in a separate on-demand pool.

| Item | Status | Evidence |
|---|---|---|
| 6 fonts vendored with licences + recorded SHA256 | VERIFIED_LOCAL | `test_every_font_ships_its_licence_file`, `test_recorded_hash_matches_the_binary_on_disk` |
| REAL coverage: Ruqaa, Kufi/geometric Kufi, Nastaliq, modern/minimal | VERIFIED_LOCAL | `test_newly_real_scripts_are_backed_by_a_real_font` |
| True Thuluth/Diwani held at LICENSE_REQUIRED | VERIFIED_LOCAL | `test_true_thuluth_and_diwani_stay_license_required`; bridge fonts cannot satisfy them |
| Unavailable style returns STYLE_NOT_AVAILABLE + alternative, never a silent Amiri substitution | VERIFIED_E2E | `test_diwani_request_is_never_silently_served_by_amiri`; `GET /api/fonts/resolve/diwani` over real HTTP |
| 52 OT features discovered from GSUB/GPOS, 0 invented | VERIFIED_LOCAL | `test_every_registered_feature_exists_in_the_font_binary` |
| 52/52 features passed HarfBuzz shaping regression over the Arabic golden corpus | VERIFIED_LOCAL | `scripts/discover_font_features.py`; `test_every_production_feature_passed_the_shaping_regression` |
| Reem Kufi cv01-cv03 and Aref Ruqaa ss01-ss08/jalt selectable as real variant axes | VERIFIED_E2E | `GET /api/fonts/reem-kufi/variants` |
| Golden Path + golden fixture unchanged | VERIFIED_LOCAL | full suite 276 passed; `font_index` made an explicit stable ordinal so vendoring never re-ranks existing designs |

**Honest limitations:**
- **Upstream commit SHA unresolved.** `api.github.com` is blocked by this environment's egress proxy, so each
  new record carries `upstream_commit: null` / `upstream_commit_status: UNRESOLVED_GITHUB_API_BLOCKED`.
  Integrity is anchored on our own recorded `file_sha256`, verified against the binary by test.
- **True Diwani and Thuluth remain NOT IMPLEMENTED.** Katibeh and Lemonada are Naskh-based bridge faces
  labelled THULUTH_INFLUENCED / DIWANI_INFLUENCED. No classical Diwani/Thuluth work is complete.
- **New families are not in the default candidate pool.** They live in `app/data/script_recipes.json` and are
  selected only on explicit script request, so the ranked-10 fixture stays byte-identical.
- **Benchmark manufacturing failures remain on long text.** Every font passes shaping/identity/SVG/licence/
  integrity on all five inputs; `OVERSIZE` on the seven-name string at fixed height is the documented
  "blocked, not repaired" behaviour, which the pre-existing families show too.
- Feature *safety* is proven; feature *aesthetics* are not — no visual review of the 52 variants has happened.

## Golden Production Memory (previous slice — Production Learning)
Two REAL Beyond Style orders — designed, manufactured, delivered and positively received — are now stored as the
highest-weight design-memory tier (`golden_production_cases`, migration `c1a7f30b52d4`). The existing production
Golden Path is untouched: no generation, validation, approval or export code changed.

| Item | Status | Evidence |
|---|---|---|
| `GoldenProductionCase` table + Alembic migration, linked to design lineage (`design_version_id` FK) | VERIFIED_LOCAL | migration runs clean from base in the test session; 12 new tests |
| Case 1 — Arabic letter drop earrings + hanging pearl (`BS-GPC-0001`) | VERIFIED_LOCAL | concept → workshop outline → manufactured pair → customer approval, registered with per-stage evidence hashes |
| Case 2 — Layered English name necklace ADAM / OMAR (`BS-GPC-0002`) | VERIFIED_LOCAL | customer selection → shop hand annotation → construction sketch → two writing styles proposed → customer picks one → manufactured piece → customer approval |
| Real selection lifecycle stored per case (`design_process`, `variant_selection`) | VERIFIED_LOCAL | `test_case2_records_the_real_customer_selection_lifecycle`, `test_case1_records_its_own_selection_lifecycle`; proven process transfers as a generation hint, geometry still does not |
| Retrieval ranks a proven case first for its product family | VERIFIED_LOCAL | `test_arabic_letter_earring_request_retrieves_the_real_case`, `test_layered_english_name_necklace_request_retrieves_the_real_case` |
| Learning priority: manufactured+approved > designer-approved > AI concept > external inspiration | VERIFIED_LOCAL | `test_manufactured_approved_memory_outranks_lower_evidence_tiers` (identical DNA, tier decides) |
| Retrieval never returns/clones the original geometry | VERIFIED_LOCAL | `test_retrieval_never_returns_original_geometry` — asserts no geometry/lineage key in results or generation hints |
| WhatsApp conversation evidence excluded; only normalized feedback kept | VERIFIED_LOCAL | `test_personal_conversation_evidence_is_never_stored_or_exported` |
| Admin view "Golden Production Cases" (8 sections) | VERIFIED_E2E | `/api/admin/golden-cases[/{id}]` returns 403 with no/wrong token and real data with one, over real uvicorn HTTP; `frontend/app/admin/golden-cases` builds and ships as a route |

**Honest limitations of this slice (do not read as more than it is):**
- **Case 1's Arabic source text is NOT confirmed.** The letters are legible in the workshop drawing, but reading them
  off an image is exactly what the text-truth rule forbids. The case is held at
  `GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION`, contributes style/construction memory only, and is excluded from
  training export until `confirm_customer_source_text()` is called with an order record or an explicit confirmation.
  Case 2's names (`ADAM`, `OMAR`) are stored verbatim on the owner's explicit written instruction — no order record
  exists in this system for either case (both are pre-platform orders, `lineage_status=PRE_PLATFORM_CASE_NO_DESIGN_VERSION`).
- **Stage-comparison scores are recorded human visual assessments, not computed geometry metrics.** Neither case has a
  `DesignVersion` with vector geometry, so silhouette/proportion fidelity cannot be measured. Every stored comparison
  carries `computed_from_vector_geometry: false` and `measurement_method: VISUAL_REVIEW_NO_VECTOR_GEOMETRY`;
  unassessable dimensions (Case 1's `letter_identity`) stay `null` with `NOT_ASSESSED` rather than being invented.
- **Evidence binaries are registered by sha256 but not uploaded.** Every descriptor carries `storage_key: null` and
  `storage_status: PENDING_OBJECT_STORE_UPLOAD`; the admin view says so instead of showing a broken image.
  Conversation screenshots are `EXCLUDED_PERSONAL_DATA` and will never be uploaded without explicit consent.
- **Case 2's chosen writing style is inferred, not recorded.** Two writing styles were proposed and the customer
  picked one, but which one was never stated — the stored `selected_variant` (`UPRIGHT_STACKED_LETTERS`) is read off
  the finished piece and flagged `OBSERVED_FROM_FINAL_PRODUCT_NOT_OWNER_CONFIRMED`.
- Retrieval scoring is the deterministic DNA encoder (`dna-onehot-1`) plus a bounded keyword bonus — not a learned
  ranker, and pgvector is still not installed on the DB host.

## DEPLOYMENT HANDOFF + PRODUCTION ACCEPTANCE (previous slice, see RELEASE_EVIDENCE.md)
**FINAL DECISION: NOT PRODUCTION READY.** Full evidence + exact blocker/owner/action table in `RELEASE_EVIDENCE.md` at repo root.
- **HEAD CI confirmed green**: run `32900447345` on current HEAD `a7e3858` — `conclusion: success`, confirmed via `get_workflow_run` (not assumed). 5th consecutive green CI run on this branch.
- **Frontend reachability VERIFIED_PRODUCTION this slice**: an authenticated fetch (`web_fetch_vercel_url`, SSO stays enabled) against `https://frontend-sigma-sable-22.vercel.app/` returned real `200 OK` with the correct Arabic RTL UI — confirms the deployed build itself is healthy. Does not change that an anonymous customer still can't reach it (SSO) or that this session's own egress to `vercel.app` is still policy-blocked.
- **Replit backend deployment contract complete and re-confirmed**: start command, required secrets, Alembic path, health/readiness URLs and expected responses all documented in `RELEASE_EVIDENCE.md` — still `BLOCKED`, no Replit tool in this session; not faked.
- **Exact `ALLOWED_ORIGINS`**: `https://frontend-sigma-sable-22.vercel.app,https://beyondstyle.ae,https://www.beyondstyle.ae`.
- **Vercel `NEXT_PUBLIC_API_URL` still `BLOCKED`** (no env-var-write tool) — SSO **kept ON**, custom domain **not attached**, per explicit instruction, since the Starlette CVEs (below) are still open.
- No Starlette/FastAPI upgrade attempted this slice, per explicit instruction — the 9 CVEs remain the open RELEASE BLOCKER (real regression found and reverted previously; needs a dedicated bisection slice).
- Production smoke / 7-name browser Golden Path **not run against real URLs** — `BLOCKED`, no real backend URL exists; local/CI results are not counted as production evidence.

## Deployment Readiness (this slice, see docs/DEPLOYMENT.md)
| Component | Status | Detail |
|---|---|---|
| Root cause of reported "تعذر توليد التصاميم" identified | VERIFIED_LOCAL | `lib/api.ts` used relative fetch paths with no `NEXT_PUBLIC_API_URL`; no CORS middleware existed at all; both fixed — see `docs/DEPLOYMENT.md` |
| Real pre-existing bug found + fixed: Pillow used at module import but absent from `backend/requirements.txt` | VERIFIED_LOCAL | `app/security/uploads.py` imports PIL at module level — a fresh `pip install -r requirements.txt` would crash the whole app on Replit; now pinned `pillow==12.3.0` (upgraded again this slice — patches 24 CVEs, see RELEASE_EVIDENCE.md) |
| Real deployment-blocking bug found + fixed: `python-multipart` missing from `backend/requirements.txt` | VERIFIED_LOCAL + VERIFIED via real GitHub Actions job logs | root cause of all 9 prior CI failures on this branch (test-collection `RuntimeError`); pinned `python-multipart==0.0.31`; 230/230 in a from-scratch clean venv — see RELEASE_EVIDENCE.md |
| CORS (`ALLOWED_ORIGINS`, no wildcard+credentials) | VERIFIED_LOCAL | `test_deployment_readiness.py`; preflight tested for an allowed and a non-allowed origin |
| `/health`, `/ready` (7 components), `/api/ai/status` | VERIFIED_LOCAL | all components report `ok` locally; never leaks a DSN/password/path |
| Correlation IDs (`X-Request-ID`) end-to-end | VERIFIED_LOCAL | generated or propagated, echoed in headers + every error body |
| Structured error codes (never a raw stack trace) | VERIFIED_LOCAL | `error_code`+`request_id` on every 4xx/5xx; unhandled 500s return a generic message only, verified via a forced internal exception |
| Frontend direct-fetch to `NEXT_PUBLIC_API_URL` (production) with local-dev rewrite fallback unchanged | VERIFIED_LOCAL | `npm run build` bakes the URL correctly; local E2E (relative paths + rewrite) still green |
| Frontend error-code → friendly AR/EN message + retry + request-id detail | VERIFIED_LOCAL | `lib/i18n.ts:error_codes`; every previously-generic catch site now passes the real error through |
| Real "Generate Designs" works with the exact required 7-name scenario (`حامد محمد سلطان ميثة حمد خالد مهرة`, reference upload) | VERIFIED_LOCAL | `scripts/production-smoke.py` A–O, 15/15, against local backend+frontend; corrected this slice (previous fixture used a wrong/incomplete name list) — see RELEASE_EVIDENCE.md |
| GitHub CI: secret scan + E2E job added | VERIFIED_LOCAL | `.github/workflows/ci.yml`; YAML validated, jobs mirror the exact commands run locally |
| `external-ai-acceptance` / `deployment-smoke` GitHub workflows | VERIFIED_LOCAL (workflow definitions) / AVAILABLE_NOT_VERIFIED (as actual GitHub Actions runs) | manual `workflow_dispatch` only; not yet observed running on GitHub |
| Secret-leak prevention (`.gitignore`, `scripts/secret_scan.py`, frontend-build-no-secrets test) | VERIFIED_LOCAL | `test_secret_scan.py` (4 tests) incl. a real `npm run build` + grep on the actual build output |
| `.replit` config (build/run/deploy) | AVAILABLE_NOT_VERIFIED | valid TOML, standard Replit conventions; never executed — no Replit access in this session |
| Vercel frontend project | VERIFIED_E2E (build/deploy only) / **BLOCKED (not publicly reachable)** | real linked project `frontend` (`prj_qf9LfOdeVRzfYTZ39sS6pja9iDCm`), latest deployment `READY`, exact commit-SHA match, 0 runtime errors — but Vercel Authentication (SSO) is enabled with no custom domain configured, so every existing URL requires a Vercel login; this session's own egress is also policy-blocked to `vercel.app` — see RELEASE_EVIDENCE.md |
| `NEXT_PUBLIC_API_URL` actually set on the Vercel project | BLOCKED (manual action required) | no tool in this session can set a Vercel project env var; must be done in the Vercel dashboard/CLI once a real backend URL exists |
| Replit backend deployment | BLOCKED (manual action required) | no Replit access in this session (no MCP connector, no CLI token) — backend has never been deployed to any public host |
| Full release gate (items 6/8/9 in docs/DEPLOYMENT.md: Replit `/ready`, real CORS/API request, real Generate Designs — all against the REAL deployed URLs) | AVAILABLE_NOT_VERIFIED | code + tests + local proof exist; production URLs don't exist yet to point the smoke test at |

## P0 STATUS: FROZEN/STABLE

All freeze criteria hold: 204/204 backend tests green (PostgreSQL 16,
real Alembic migrations) · 4/4 browser E2E flows green (text/reference/
desktop/copilot) · all 9 real tools still VERIFIED_LOCAL (unchanged
this slice) · deterministic fallback re-verified explicitly (both as a
unit check and via `make external-ai-e2e`'s
`provider_failure_deterministic_path` run, forcing Claude/GPT-Image-2/
Hermes-isolated all unavailable) · no TODO/FIXME/XXX in any Golden Path
module (`engines/`, `services/design_service.py`, `schemas/`,
`api/designs.py`) · STATUS below distinguishes VERIFIED_LOCAL from
SKIPPED_NO_CREDENTIALS/OPTIONAL_NOT_RUNNING everywhere external
execution is claimed.

**External Claude/GPT-Image-2/isolated-Hermes verification is an
explicit deployment acceptance gate, not a P0 blocker** — this
environment has no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/docker daemon,
so those three remain SKIPPED_NO_CREDENTIALS / SKIPPED_NO_CREDENTIALS /
OPTIONAL_NOT_RUNNING here. They are NOT marked complete or VERIFIED —
run `make external-ai-e2e` on a deployment with real credentials to
move them to VERIFIED_EXTERNAL; see `docs/evidence/external-ai-acceptance.json`
for the current (honest) run.

## External AI Acceptance (`make external-ai-e2e`, see `backend/scripts/external_ai_acceptance.py`)
| Component | Status | Detail |
|---|---|---|
| `make external-ai-e2e` command | VERIFIED_LOCAL | runs from repo root, migrates its target DB, writes `docs/evidence/external-ai-acceptance.json`, exits 0 unless any check is FAILED |
| CLAUDE (نورة reference: Claude structured DesignDNA → deterministic Arabic engine → geometry → manufacturing validation) | SKIPPED_NO_CREDENTIALS | no `ANTHROPIC_API_KEY` here; asserts source_text is still exactly "نورة" after the (skipped) call attempt; real-call branch captures model/response_id/latency/tokens/cost/structured_response_hash/design_dna_hash/source_text_sha256/final_geometry_hash when credentials exist |
| GPT_IMAGE (ع → 18K yellow-gold earring, luxury studio scene → IdentityGuard → PASS/REVIEW/REJECT) | SKIPPED_NO_CREDENTIALS | `OPENAI_IMAGE_ENABLED=false`/no key here; asserts PNG/AI-raster export is refused (`ValueError`) regardless; real-call branch captures provider/model/latency/cost/guard_status/geometry_hash/content_sha256 |
| HERMES (one harmless read-only tool job through the isolated runtime) | OPTIONAL_NOT_RUNNING (default) | manually verified VERIFIED_EXTERNAL in this session with `services/hermes` actually running (`HERMES_MODE=isolated`, live `/health` + a real `retrieve_design_memory` round trip) — not this environment's default configuration, so the checked-in evidence file reflects the honest default (OPTIONAL_NOT_RUNNING) |
| Real agent tool chain (reference → analyze_reference → retrieve_design_memory → generate_design_recipes → validate_arabic → validate_manufacturing → repair-if-required → rank_candidates → create_visual_preview-if-available), STOPPING before approve_design | VERIFIED_LOCAL | `approve_design` asserted `ToolNotPermitted` even when attempted by `master_orchestrator`; human/customer approval remains the only path to `APPROVED_LOCKED` |
| Provider-failure fallback (text → 10 concepts → select → manufacturing validation → approval/export, forcing Claude/GPT-Image-2/Hermes-isolated all unavailable) | VERIFIED_LOCAL | reaches `APPROVED_LOCKED` + a real DXF export with content sha256, unaffected by any provider's absence |
| Cost/usage evidence capture (provider, model, tokens, image generations, retries, latency, estimated cost) | VERIFIED_LOCAL (shape) / pending real numbers | redaction allow-list (`USAGE_EVIDENCE_KEYS`) proven to strip any injected secret/prompt/raw-payload key before writing; real numbers appear only once a real call executes |
| No paid photoreal preview for all 10 candidates | VERIFIED_LOCAL | `create_visual_preview` is called only once, on the single selected/ranked candidate — never per-candidate |
| Security: keys server-side only, never logged, no raw images in evidence | VERIFIED_LOCAL | `test_evidence_never_contains_secrets_or_raw_payload`; evidence JSON contains hashes/statuses/numbers only |

## Real Tool Wiring + Isolated Hermes Runtime + Live Provider Acceptance (see ADR-0003)

**Adding real credentials to a deployment** (never commit them —
`backend/.env.example` only ever holds empty values): set
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and `OPENAI_IMAGE_ENABLED=true` as
secret environment variables on the actual deployment target (e.g. your
platform's secrets manager / `.env` on the server, injected at
container-start — never baked into an image or a git-tracked file). If
running Hermes isolated, also set `HERMES_MODE=isolated`,
`INTERNAL_TOOL_TOKEN` (main app) and the identical `MAIN_APP_TOOL_TOKEN`
(services/hermes) as a matching secret pair.

| Component | Status | Detail |
|---|---|---|
| 9 real tools wired to existing services (analyze_reference, retrieve_design_memory, generate_design_recipes, validate_arabic, validate_manufacturing, repair_geometry, rank_candidates, create_visual_preview, approve_design) | VERIFIED_LOCAL | `test_hermes_tools_live.py`; each calls the exact function the HTTP API uses, strict Pydantic I/O schemas, no duplicated logic |
| Orchestrator.call_tool (policy + budget + durable audit) | VERIFIED_LOCAL | every call recorded as a `design_events` row (`TOOL_INVOKED`) with job_id/agent/tool/input_hash/result_status/latency/timestamp; failed calls audited then raised, never swallowed |
| Per-agent tool allow-lists (ReferenceAgent/DesignAgent/ManufacturingAgent examples) | VERIFIED_LOCAL | cross-agent tool use blocked even for globally-permitted tools |
| approve_design wired but always agent-blocked | BLOCKED (by design) | real function in TOOL_REGISTRY; `WRITE_TOOLS_REQUIRING_HUMAN` membership makes `ToolNotPermitted` unconditional, proven for every registered agent |
| No shell/file/network tool ever allow-listed | VERIFIED_LOCAL | `test_no_shell_file_network_tools_registered` |
| Isolated Hermes runtime app code (services/hermes/) | AVAILABLE_NOT_VERIFIED (as a container) / VERIFIED_LOCAL (as app code) | `/health` + `/orchestrate/{agent}` run correctly via direct `uvicorn` in this sandbox (same site-packages, not the pinned isolated venv) and were exercised live against `HermesClient`; `pip install --dry-run -r services/hermes/requirements.txt` resolves cleanly (hermes-agent==0.19.0 + pydantic==2.13.4 + openai==2.24.0 + anthropic==1.0.0 + fastapi==0.118.0, no conflicts) — the actual Docker build/run is still unverified: no docker daemon in this sandbox (`docker info` fails) |
| HERMES_MODE=isolated → in_process fallback | VERIFIED_LOCAL | tested both isolated-reachable (SKIPPED_EXTERNAL_MODEL propagates honestly) and isolated-unreachable (connection refused → silent fallback, never blocks) |
| Internal tool-call callback endpoint (`/api/orchestration/internal/tools/{tool}`) | VERIFIED_LOCAL | closed (403) with `INTERNAL_TOOL_TOKEN` unset (this environment's default); works end-to-end once a shared secret is configured |
| Dependency isolation (main app pins unaffected by Hermes) | VERIFIED_LOCAL | `test_main_app_dependency_pins_unaffected_by_hermes` reads both requirements.txt files; `test_main_app_installed_pydantic_version_matches_pin` checks the actually-imported `pydantic.VERSION` |
| Real `hermes-agent` package | OPTIONAL_NOT_RUNNING (not installed anywhere) | pinned only in `services/hermes/requirements.txt`; never a dependency of `backend/requirements.txt` |
| Live Claude acceptance (نورة reference case) | SKIPPED_NO_CREDENTIALS | `test_live_claude_acceptance_arabic_norah_reference`; no `ANTHROPIC_API_KEY` here — honest-skip branch ran; deterministic candidate generation + exact source_text preservation proven regardless |
| Live GPT-Image-2 acceptance (ع → 18K gold earring) | SKIPPED_NO_CREDENTIALS | `test_live_gpt_image2_acceptance_letter_ain_earring`; canonical `geometry_hash` exists and PNG/AI raster export is blocked regardless of provider availability |
| Full agent orchestration E2E (reference → Claude(skip) → deterministic generation → Arabic QA → Manufacturing QA → ranking → selection → optional preview(skip) → human approval) | VERIFIED_LOCAL | `test_full_agent_orchestration_e2e_deterministic_path_always_completes`; completes with Claude, Hermes-isolated and GPT-Image-2 all unavailable |

## Hermes + Claude + GPT-Image-2 orchestration (see ADR-0002)
| Component | Status | Detail |
|---|---|---|
| Source-of-truth hierarchy enforcement | VERIFIED | `orchestration_status()`; no AI write path touches immutable text/geometry/manufacturing columns (DB-trigger-protected, ADR-0001) |
| Hermes agent registry (13 specialists) + tool allow-listing + budgets + audit | VERIFIED | `test_hermes_claude_visual.py`; write tools (`approve_version`/`production_export`/etc.) raise `ToolNotPermitted` even for the master orchestrator |
| Real `hermes-agent` runtime | UNAVAILABLE (not installed) | pins `pydantic==2.13.4`/`openai==2.24.0`, conflicts with this project's pins; detection adapter reports `execution_mode: in_process_orchestrator` honestly; in-process `Orchestrator` implements the same registry/policy/budget contract |
| Claude model routing (fast/primary/escalate) | VERIFIED (routing) / UNAVAILABLE (live calls) | `anthropic==1.0.0` SDK installed this slice; no `ANTHROPIC_API_KEY` in this environment → `LLMUnavailable`; `llm_status()` reports `sdk_installed: true, credentials_configured: false` |
| Design Jury (structured 4-role Claude call) | UNAVAILABLE (no credentials) | endpoint returns HTTP 200 `{"status":"SKIPPED_EXTERNAL_MODEL"}`, never a fabricated verdict; weighting formula verified directly |
| Shadow model evaluation | UNAVAILABLE (no credentials) | `run_shadow_evaluation` raises `LLMUnavailable`; promotion is advisory-only by design, never auto-applied |
| GPT-Image-2 visualization provider | VERIFIED (guards/wiring) / UNAVAILABLE (live calls) | `openai==3.3.1` SDK installed this slice; `OPENAI_IMAGE_ENABLED=false` default + no key → `ImageProviderUnavailable`; preview endpoint returns 503 `PHOTOREAL_PREVIEW_UNAVAILABLE` with a working `fallback` to the deterministic SVG |
| Visual Identity Guard (geometry-preserving preview) | VERIFIED | alpha-aware, bbox-normalized occupancy-grid IoU; bounded retries (`MAX_PREVIEW_RETRIES=2`, exactly 3 attempts max, never infinite); PASS/REVIEW_REQUIRED/REJECTED_GEOMETRY_DRIFT all exercised with a fake provider double |
| VisualBrief + VisualPromptBuilder (preservation rules, negative constraints) | VERIFIED | cache-key stability + material-sensitivity tested; reference DNA never injects text-content keys into the prompt |
| Cost/cache/session budgets | VERIFIED | cache hit avoids a second paid call; `max_session_cost_usd`/image-count caps reject *before* any spend |
| AI raster never exportable as DXF/CAD | VERIFIED | `export_version()` rejects any format but svg/dxf; reference-workflow and material-variant flows keep `immutable_source_text` unchanged |
| Confidence Engine | VERIFIED | deterministic (no model call); low-dimension flags `requires_human_review` |
| Customer taste memory (opt-in) | VERIFIED | reuses `design_events` (`CUSTOMER_FEEDBACK`); never touches source text; scoped per-customer request ids |
| Design lineage (Request→…→Export, no orphans) | VERIFIED | full-chain + cross-session isolation tested |
| Product-specific Hermes skills (8 products) | VERIFIED | registry + endpoint + unknown-product 404 |
| Secrets never leak via orchestration/status endpoints | VERIFIED | literal API-key value asserted absent from `/api/orchestration/status` JSON |

## Visual Reference Intelligence — honest AI status
| Component | Status | Detail |
|---|---|---|
| Provider abstraction (VisualAnalyzer/ImageGenerator/ImageEditor/Embedding) | VERIFIED | interfaces + AI_MODE config + license registry; MODEL_UNAVAILABLE errors, never faked results |
| Model registry (Qwen3-VL / Qwen-Image-Edit / Qwen-Image / FLUX.1-schnell) | VERIFIED | all Apache-2.0, commercial_use=true, version-pinned; non-commercial models absent by design |
| Real Qwen3-VL analysis | UNAVAILABLE (in this environment) | implementation is real (transformers lazy-load in worker), but no GPU/weights/torch here — AI_MODE=disabled; real-model integration evidence pending a model host |
| DesignDNA (strict schema, OCR/text keys hard-dropped) | VERIFIED | vlm + deterministic_fallback sources, always labelled |
| Deterministic fallback DNA | FALLBACK (active here) | aspect/orientation-derived, most fields honestly "unknown" |
| DNA embedding + retrieval | FALLBACK (deterministic encoder) | dna-onehot-1; Python cosine behind a pgvector-shaped interface (pgvector extension not installed on this DB host) |
| Similar-approved retrieval | VERIFIED | only APPROVED_LOCKED designs' references retrieved |
| SAME_STRUCTURE_NEW_TEXT with reference weights | VERIFIED | ref-0.1.0 ranking (25/25/15/15/10/5/5, hard gates override); target text immutable end-to-end |
| Copy-risk gate | VERIFIED | INSPIRED_ALTERNATIVE_REQUIRED on brand/copy indicators |
| DesignMemoryService (feedback events → retrieval/ranking weights) | VERIFIED | append-only events; weights recomputed, history never mutated; no model retraining claimed |
| LoRA dataset export | VERIFIED (export only) | rights/consent-gated; training itself DISABLED (LORA_TRAINING_ENABLED=false, no adapter wired) |
| AI job queue + worker process | VERIFIED | separate process, timeouts/retries/cancellation; honest MODEL_UNAVAILABLE terminal state |
| Photoreal preview endpoint + identity guard | PARTIAL | guard (silhouette IoU vs canonical geometry) VERIFIED with synthetic renders; end-to-end generation UNAVAILABLE here (no model) → endpoint returns 503 MODEL_UNAVAILABLE |
| FLUX.1-schnell fallback generator | UNAVAILABLE (no weights/GPU here) | code path real; restricted to generic/lifestyle use by prompt policy |
| UI: reference slider + trust badges + analyze call | VERIFIED | style-strength slider, "reference understood/Arabic verified/manufacturing safe/originality" badges |
| Deterministic Golden Path under AI outage | VERIFIED | full suite + 4 E2E flows green with AI_MODE=disabled |

## P0 Golden Path
| Area | Status | Evidence |
|---|---|---|
| Arabic engine (NFC/BiDi/HarfBuzz, identity proof) | VERIFIED | test_arabic_engine.py; wrong-glyph/notdef blocking |
| Immutable source text + confirmation | VERIFIED | 422 on mismatch; DB triggers; E2E |
| Persistence + versioning + approval lock + audit | VERIFIED | 21 integration tests incl. race + tamper attempts (ADR-0001) |
| Reference intake + classification + IP risk | VERIFIED | test_intake_security.py; OCR never source text |
| Upload security + anonymous sessions + rate limits | VERIFIED | magic-byte, EXIF strip, private storage, 404 isolation, 429 |
| Mobile-first customer UI (true RTL) + desktop | VERIFIED | golden_path_e2e.py (3 flows), copilot_e2e.py |
| Perceptual dedup + diversity gate | VERIFIED | IoU gate 0.86; diversity-report.json all 5 cases |
| High-fidelity relief proofs | VERIFIED | test_quality_gate.py; proof-sheet PNGs |
| Glyph Variant Library (OT sets, dot styles, swashes, kashida) | VERIFIED | test_variants_bridges_rules.py; kashida identity-remap proven |
| Aesthetic bridge routing (vertical/radial + fillets) | VERIFIED | bridge tests; medallion spokes replace chords in proofs |
| Workshop rule profiles (product × material, versioned) | PARTIAL | wp-1.0.0, 6 profiles, slenderness/envelope gates tested — values INDUSTRY_TYPICAL_UNCALIBRATED, not yet calibrated with Beyond Style workshop |
| Long-text / multi-line composition | VERIFIED | 7-name chain + phrase → 10 valid stacked options each, width-fit, identity verified |
| Designer Copilot (params incl. variant axes, undo/redo over versions) | VERIFIED | copilot_e2e.py; EDITABLE_RECIPE_FIELDS gate |
| Production SVG/DXF export authorization | VERIFIED | lock+hash re-verify; ezdxf read-back; 423 blocking |
| CI pipeline | PARTIAL | .github/workflows/ci.yml (backend suite + migrations + evidence artifact + frontend build) — added this slice, not yet observed green on GitHub |
| Archetype library | PARTIAL | 40 curated recipes with DNA (target 150+); no pgvector retrieval yet |

## Explicitly NOT_IMPLEMENTED (honest)
Visual design learning engine (VLM analysis, embeddings, AI critic, feedback
buttons, Teach-the-AI, workshop learning loop) — no AI/VLM provider is
available in this environment; adapter surface exists only for intake
analysis (feature-flagged off). 3D preview/CAD, pricing/orders, Customer
Service workspace, admin console, trend agents, digital twin beyond the
existing request→version→approval→export trace, per-glyph move/tail editing,
malware scanner provider, S3/Redis, accounts/RBAC.

## Next
1. **Deploy the backend to Replit** (manual — see `docs/DEPLOYMENT.md` "Replit" section; still no Replit access in this session as of the P0 release-closure slice): import the repo, set `DATABASE_URL`/`ALLOWED_ORIGINS` secrets, click Publish.
2. **Set `NEXT_PUBLIC_API_URL` on the Vercel project** (manual — still no tool in this session can set Vercel env vars) to the real Replit URL from step 1, then redeploy.
3. Run `python3 scripts/production-smoke.py` (now with the corrected 7-name fixture, 15 checks) against the real `FRONTEND_URL`/`BACKEND_URL` to close the release gate's remaining items — this is the exact required 7-name scenario, still only verified locally, not against real production URLs. See `RELEASE_EVIDENCE.md`.
4. Calibrate workshop profiles with real Beyond Style workshop values.
5. Push branch → observe CI green on GitHub (now includes a real E2E job + secret scan, not yet observed running on GitHub itself).
6. Run `make external-ai-e2e` on a deployment with real `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (+ `OPENAI_IMAGE_ENABLED=true`) and, separately, a docker daemon running `services/hermes/` with `HERMES_MODE=isolated` — this is the deployment acceptance gate for CLAUDE/GPT_IMAGE/HERMES to move from SKIPPED_NO_CREDENTIALS/OPTIONAL_NOT_RUNNING to VERIFIED_EXTERNAL. Stop-condition: cannot be built honestly without them; P0 itself does not block on this (see "P0 STATUS: FROZEN/STABLE" above).
