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
Updated: 2026-09-05 · GitHub Actions CI: VERIFIED_CI, run 33980737422 (HEAD `48c6e9d`, ADR-0006 slices incl. secure approval link + PNG export — all 4 jobs green; runs 59–62 and 64 also green); earlier: run 33932846404 (HEAD `c5126c9`, jewellery realism slice, ADR-0005) — all 4 jobs green; previous run 33872385421 (`56d07d9`, font onboarding kit + studio-render fallback) — all 4 jobs green; run 33869986675 (`486a5fb`) was red on one test (registry accessor left swapped by the kit's proof step, fixed in `56d07d9`); previous green runs 33861562627 (`b521aa8`), 33664799084 (`3ada443`) — all 4 jobs green (secret-scan, backend full suite incl. Workshop OS / validation API / archetype catalogue / security hardening, frontend build with the split Golden Path page, Golden Path + Copilot browser E2E). The preceding run 33638126995 (`5c3dd32`) was red on 3 tests — vote casing, pack tolerances — fixed in `3ada443` (see the slice sections below). Previous baseline: run 33204109378 (HEAD `5954693`) — all 4 jobs green (secret-scan, backend full suite on the corrected fonttools 4.60.2 + uharfbuzz 0.56.0 pins, frontend build, Golden Path + Copilot browser E2E); local full suite also exit 0 on the same pins. Note: CI was red for the 8 commits between `a7e3858` and this fix (see "CI red since 49c4ceb" below) — the previous "5 consecutive green runs" claim ended at `a7e3858`.
Previous (2026-08-26): Backend suite: 401 passed (394 + 7 First-Wave Analysis) (PostgreSQL 16, incl. 11-test immutable seven-name golden fixture) · E2E: 5 browser flows passed (incl. dedicated seven-name+reference flow) · production smoke: 15/15 checks passed (local, corrected fixture) · CI run 32900447345 (`a7e3858`) conclusion=success — see RELEASE_EVIDENCE.md.

## Owner sample ingestion → Golden Production Memory + product catalogue (2026-09-10)
Owner supplied 64 real images in four batches ("real samples to LLM to learn"). Ingested honestly:
- VERIFIED_LOCAL — 25 new golden cases (BS-GPC-0003…0028) in `backend/app/data/golden_production_cases.py`: bar-name pendant (layout proof + workshop outline + product), pavé name necklace, Latin script bracelet, open name ring, enamel cufflinks, engraved disc keychains, pierced name disc, orchid enamel brooch (vector + product), Arabic name bar-pin brooch, lariat letter stations, car mirror hanger, name bracelet/necklace lines, intertwined calligraphy pendant, phrase plate on mesh band, men's chain catalogue, kids' and cufflink market references, length guides. 27 cases seed idempotently; 17 DB tests pass.
- VERIFIED_LOCAL — text truth preserved: no owner case carries `customer_source_text`; all stay `GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION` until a customer confirms exact text on the platform. Names/dates visible on samples were not transcribed.
- VERIFIED_LOCAL — privacy/rights: 24 evidence items are hash-only (`EXCLUDED_PERSONAL_DATA` for children/faces/on-body/customer name+date; new `EXCLUDED_THIRD_PARTY_RIGHTS` for other brands / unknown origin); `rights_provenance` THIRD_PARTY_NO_COPY / UNKNOWN_RIGHTS cases are excluded from training export and from `golden_case_influence`. Only owner-owned, people-free images are copied (downscaled) to `docs/reference/owner-samples/` (42 files + README index).
- VERIFIED_LOCAL — evidence tiers `MANUFACTURED_OWNER_SAMPLE` 0.9 and `MARKETING_RENDER_UNMANUFACTURED` 0.3 added to `EVIDENCE_TIER_WEIGHTS` and `EVIDENCE_PRIORITY`; `golden_case_influence` now maps bracelet, ring, cufflink, keychain, brooch, hanger (token-boundary matching so RING ≠ EARRING) and orders by evidence priority.
- VERIFIED_LOCAL — `app/data/product_catalogue.json` (75 catalogue items: 24 rings, 6 brooches, 45 necklaces with codes, AR/EN titles, AED starting prices, text_process engraving/cut_out/none, OWNER_CATALOGUE_STATED) and `app/data/wearability.json` (bracelet fit table from the owner's size guide, industry-standard necklace lengths, men's chain length/weight table) served by `GET /api/products/catalogue[/{code}]`, `GET /api/products/size-guide[/bracelet]`; `tests/test_products_api.py` 5 tests; OpenAPI regenerated (94 paths, `--check` OK).
- Honest gaps: owner-owned originals are `PENDING_OBJECT_STORE_UPLOAD`; catalogue pages not shown (9 rings, 5 brooches, 12 necklaces) are not transcribed; chain weights are owner-stated, not weighed; the DecoType Thuluth III reference is a locked commercial font and is recorded as a reference only (never imitated); keychain/brooch/hanger lessons inform the copilot but no geometry recipes exist for those products yet.

## Arabic Calligraphy Source Registry + Text Integrity Engine + Vector Composition Engine + Jewelry Manufacturing Gate (2026-09-05, ADR-0006)
Owner specification ("BEYOND STYLE ARABIC JEWELRY DESIGNER") implemented as six increments after an
audit (preserve working code, remove duplicates: merged `/api/fonts/styles`, one `EXPECTED_LOOPS`
map, one repair service). Full readiness table with percentages and Critical/High/Medium/Low issues:
`docs/production-readiness.md` (top section).
- **Text Integrity Engine** (`engines/text_integrity.py`): VERIFIED — inspect (invisible/bidi/
  tatweel/presentation forms/NFC drift), rasm-group diff classification, `certify()` on every
  version and export; `POST /api/designs/integrity/inspect`, `GET /api/versions/{id}/integrity`.
  ميثه is byte-exact through confirm → approve → export (acceptance E2E).
- **Source Registry**: VERIFIED — 37 OFL families vendored; style catalogue with honest statuses;
  `POST /api/admin/fonts` upload (private storage, never served by URL); `/styles` browser with
  persisted favourites/recent; `/admin/fonts` UI. Thuluth/Diwani/Nastaliq = INFLUENCED_ONLY until
  a licensed source is uploaded (never imitated).
- **Vector Composition Engine**: VERIFIED — six layouts from the same glyph vectors, welded, two
  upper chain rings; seven-name case 23/24 valid, 10 diverse; phrases (function words) keep the
  stacked path; brief hint `text_kind` overrides; pool topped up with stacked recipes when
  compositions cannot supply ten valid options. Generation 14.6 s on 4 cores (`8c4bf41`).
- **Materials + weight**: VERIFIED — 11 materials, weight = area × thickness × density.
- **Jewelry Manufacturing Gate**: VERIFIED — PDF export; every SVG/DXF/PDF re-imported and compared
  with the master vector (verdict on the export record + `X-Export-Fidelity`); JEWELRY QA
  PASS/FAIL in plain Arabic/English; readiness ladder from facts (approval = INTERNAL_UI).
  Migration `c1d2e3f4a5b6`. Two defects found by the acceptance E2E and fixed (`44001e0`).
- **Vector edit ops + real repair** (`engines/vector_edit.py`): VERIFIED — translate/rotate/
  uniform scale/bridge/ring/union/cut with text protection, workshop minimums, must-touch rule,
  replay on recipe edits; node/pen editing NOT_IMPLEMENTED (listed as unavailable in the UI);
  repair options are dry-run and offered only when they reduce errors.
- **UI**: integrity panel, dynamic style chips, JewelryCheck, fidelity badges, readiness ladder,
  Pro-mode panel, actual-size preview mode, mobile sticky action bar; `next build` green.
- **Mandatory acceptance E2E** `e2e/acceptance_seven_names_e2e.py`: VERIFIED_E2E on localhost
  (evidence `docs/evidence/acceptance-seven-*`, results JSON with the event trail); layout has no
  horizontal overflow at 360/390/768/1280. Local dev proxy needed `experimental.proxyTimeout`
  (`4b61409`) — production fetches the backend directly.
- **Workshop profile pinning from real cutting tests** (2026-09-10): the calibration kit is now
  reachable from the admin API — `POST /api/admin/calibration/coupon` (dimensioned SVG/DXF +
  manifest), `POST /api/admin/calibration/apply` (results → measured limits × 1.15 safety
  margin; `write=true` pins a new `profiles_version` with operator/date/coupon-sha provenance,
  refused while any feature class is UNRESOLVED), `GET /api/admin/calibration/profiles`.
  `WORKSHOP_PROFILES_PATH` selects the file (staging copies never touch the repo file). JEWELRY
  QA now reports `calibration_status` for the limits used. **BLOCKED on data**: no coupon has been
  cut by Beyond Style's workshop yet — every profile is still `INDUSTRY_TYPICAL_UNCALIBRATED`
  (wp-1.0.0). Tests `test_calibration_admin.py` 2/2 + kit 6/6.
- **OpenAPI publishing + canonical layout** (2026-09-10): `docs/api/openapi.json` is generated from
  the code (`scripts/export_openapi.py`, 90 paths) and CI fails when it is stale; live at
  `/openapi.json` and `/docs`. Layout audit in `docs/architecture.md`: `backend/` is the only
  application, `services/hermes/` is the optional runtime, no conflicting scaffold exists; the
  root `.replit` is a deployment stub. Production URLs (Replit/Vercel) are unreachable from this
  environment, so live publishing could not be verified here (Production Monitor stays red).
- **Customer identity + secure retrieval** (2026-09-10, migration `e3f4a5b6c7d8`): VERIFIED_LOCAL —
  passwordless login by phone/e-mail + one-time code (hashed, 10 min, 5 attempts, single use;
  only a peppered sha256 + masked contact stored), 30-day customer token (hash only), claim of
  an anonymous request (both tokens required), `GET /api/me/designs`, resume on another device
  (rotates the per-request token — the old device loses access), events REQUEST_CLAIMED /
  SESSION_REISSUED, per-IP start/verify limits through the shared limiter. Frontend `/me` page,
  auto-claim after start, `?design=` resume. Honest delivery: **no SMS/e-mail provider is wired**
  — `delivery.status=SKIPPED_EXTERNAL_PROVIDER`; `AUTH_DEV_ECHO_CODE=1` (dev/CI/E2E only) echoes
  the code and `/ready → customer_auth` warns while it is on. Tests `test_customer_identity.py`
  3/3; browser `e2e/customer_identity_e2e.py` (in CI). Not done: provider integration, OTP on
  the approval link, account deletion/export UI.
- **Shared rate limiter + object storage** (2026-09-10): VERIFIED_LOCAL — one registry
  (`security/ratelimit.py`, memory | Redis via RATE_LIMIT_BACKEND/REDIS_URL, degrade-not-block),
  S3 private store proven with a botocore stub, `/ready` reports storage backend/durability and
  limiter backend. Replit production must set OBJECT_STORAGE=s3 (instance disk is ephemeral).
- **Calligraphy sources** (2026-09-10): Thuluth TRUE via OFL AMoshref Thulth (sweep 1.00), Aref
  Ruqaa Ink Bold added, Diwani stays inspired-only (owner-supplied Al Diwani Al Majd has no
  licence → held out); the chosen script now dominates the shown ten (9/10 measured). See
  `docs/CALLIGRAPHY_SOURCES.md`, `docs/FONT_LICENSING.md`, `docs/evidence/fonts/`.
- **PNG export** (`exporters/png_exporter.py`): VERIFIED — raster of the master vector at a declared
  scale (20 px/mm, 4× supersampled, transparent, scale/version/hash in PNG text chunks, true-size dpi);
  lock-gated like the vectors, recorded as `kind=preview`; raster fidelity = extent within a pixel +
  coverage area within 1.5 % + hash chunk. Never manufacturing truth and never counts toward
  WORKSHOP READY.
- **Secure customer approval link** (`approval_links`, migration `d2e3f4a5b6c7`): VERIFIED — studio
  mints a single-use 72 h link bound to the version's geometry hash (`POST /api/versions/{id}/
  approval-link`); the customer opens `/approve/{token}` without a session, sees the exact text and
  the dimensioned agreement proof, retypes the text (ميثه ≠ ميثة blocks the button) and approves;
  the lock is recorded with `approval_method=SECURE_LINK`, the link is consumed, a newer link
  revokes the older one, the ladder shows the channel. Tests `test_approval_link.py` 2/2; browser
  `e2e/approval_link_e2e.py` (in CI). Not done: OTP/identity check on the link holder.
- **Not done (honest)**: node/pen editing, 10-step wizard (7 steps),
  on-body preview modes, Thuluth/Diwani true sources, gap-widening auto-repair,
  workshop calibration values. Production Monitor is red on every push because the deployment is
  unreachable — an operations task.
- **Tests**: local full suite on `8c4bf41` — 511 passed, 0 failed, exit 0 (~35 min, 4 cores); on `9fd2379` 515 collected, 513 passed + the 2 png-contract tests updated in `3c513de` and passing (effective 515/515); on `1367218` (2026-09-10) — 526 passed, 0 failed, exit 0; slice tests: text_integrity 7, source_registry, font_onboarding 5, font_upload 3, composition_engine 4, manufacturing_gate 4, vector_edit 8, variants/long-text 3; acceptance E2E PASSED (localhost). CI runs 59–62 and 64–65 green on all four jobs (backend suite, evidence, frontend build, browser E2E incl. the approval link) — reference run 65 (33980737422, HEAD `48c6e9d`); **2026-09-10: runs 67 (34426458839, fonts), 68 (34427319432, shared limiter/storage), 69 (34428047159, identity + OpenAPI gate + calibration API) and 70 (34428059280, HEAD `1367218`) all green on all four jobs — backend suite with the OpenAPI freshness step, evidence report, frontend build, browser E2E incl. customer_identity_e2e.py;** runs 53–58 failed only on tests/evidence checks fixed in `8c4bf41` / `5686ce3`.

## Workshop OS + calibration kit (2026-09-02, assessment risks #3 and #7)
**Workshop OS** (`services/workshop_service.py`, `api/workshop.py`, table `workshop_orders`,
migration `b7c3e9d4a1f0`): state machine `NEW → DESIGN_REVIEW → TECHNICAL_CHECK → APPROVED →
MANUFACTURING → QC → (REWORK → MANUFACTURING) | READY → DELIVERED`; no state may be skipped; the
customer approval is re-verified against the version hash at every transition; DELIVERED
requires receiver name + staff number + actual received date; every transition is an audit event.
Production pack = approved hash, exact text, dimensions (ring: size/flat length), material,
process list, BOM with weight estimate, tolerances, warnings, score and SVG/DXF content hashes
(ring packs list `engrave_inner_face_mirrored` and carry the `ENGRAVE_INNER` DXF layer).
Admin-token only. Tests `test_workshop_os.py` 6/6 (fix 2026-09-02: pack tolerances now come from
the persisted validation run's rules snapshot — the version JSON never carried one, so `kerf_mm`
was null in every pack; CI run 33638126995 caught it). Not built: staff UI for the board (API only),
customer-facing order status, invoicing.
**Calibration kit** (`engines/calibration.py`, `scripts/calibrate_workshop.py`,
`docs/evidence/calibration/`): `make calibration-coupon` writes a dimensioned coupon (SVG+DXF+
manifest, hash-bound) with graded stroke/gap/bridge/counter/engrave-line features; the operator
records which grades came out clean and `apply --write` derives the workshop limits with a 15 %
safety margin, bumps the profiles version and records provenance (`WORKSHOP_CALIBRATED_<date>`)
— or `CALIBRATION_INCOMPLETE` if any feature class is missing. Tests `test_calibration_kit.py`
6/6. Honest: the limits in `workshop_profiles.json` are still the uncalibrated defaults until the
owner cuts the coupon; every export says so through the profile provenance.

## Evidence collection enablement (2026-09-02, assessment risk #4)
Zero human/customer evidence was the top non-code risk. Two owner-operable paths now exist:
- `POST /api/admin/golden-cases/{case_id}/confirm-text` (admin token): the owner types the exact
  text from the order record; the golden case promotes to production memory. OCR/vision authority
  is refused (422) — text truth stays deterministic.
- Public customer validation: `GET /api/validation/pack` (manufacturing-passing, diverse proofs
  with engineering metadata stripped) and `POST /api/validation/response` (anonymous; respondent
  token stored hashed; 60 responses / 10 min per IP and per respondent; honeypot field; votes
  bound to the live pack) — served by the new `/vote` page (mobile-first, AR/EN) so a WhatsApp
  link collects real reactions. Responses land in the append-only customer_validation table the
  curation analysis already reads; never mixed with expert reviews.
Tests `test_validation_api.py` 5/5. Honest: still zero real responses recorded — the endpoints
enable evidence, they are not evidence.
Fix (2026-09-02, found by CI run 33638126995): the `/vote` page sent `YES/MAYBE/NO` while the
service accepts lowercase — every real vote would have been refused with 422. The API now
normalises case; the two API tests that reproduced it are green.

## Coverage: ♥ decorative glyph, 215-archetype catalogue, DNA retrieval (2026-09-02, risk #6)
- **♥ (U+2665/U+2764)** is now a first-class decorative glyph: shaped as its own run (never a font
  substitution), parametric heart polygon in the geometry engine, advance 0.95 em, covered by the
  identity proof at its exact index. Tests `test_decorative_symbols.py` 3/3.
- **Archetype catalogue** (`engines/archetype_library.py`): the 46 curated recipes (40 design + 6
  script) are unchanged and first; 169 derived archetypes are built from a deterministic
  construction matrix (composition × dot style × swash × kashida) on each font's curated base,
  de-duplicated by parameter signature — 215 total, 65 DNA families, 9 approved fonts. Every
  derived archetype is labelled `UNCURATED_PARAMETRIC` (inherits manufacturing parameters from a
  curated base; no designer has reviewed it as a look) and still passes the same Arabic +
  manufacturing QA as any candidate.
- **Retrieval**: brief/reference hints (product, style intent, DesignDNA script/dots/swash/
  construction) are encoded into the archetype DNA space; metadata filter (product, text length)
  then cosine ranking; top-8 join the candidate pool. Provenance (basis, considered, returned ids,
  similarities, curation labels) is recorded in the CANDIDATES_GENERATED event. Encoder is the
  deterministic DNA encoder with a Python cosine — pgvector-shaped; the extension is not installed
  on the DB host, and the provenance says so.
- **Golden fixtures untouched**: the hint-less pool is byte-identical (asserted), so the pinned
  candidate ids in `tests/golden/golden_visual.json` did not move. Tests `test_archetype_library.py`
  8/8 + generation/quality gates green.
Honest: 215 archetypes ≠ 150 *curated* archetypes; curation of the derived set is designer work.

## Maintainability: env-pin drift check + Golden Path page split (2026-09-02, risk #8)
- `scripts/check_env_pins.py` (`make check-pins`) fails when the local Python environment differs
  from `backend/requirements.txt` — the drift that hid a red CI for eight commits. Wired as a CI
  step right after install. First local run found real drift (pytest 8.3.3 vs 9.0.3, boto3
  missing); fixed by reinstalling the pins.
- `frontend/app/page.tsx` 1,113 → 860 lines: the start, confirm, approve and approved steps are now
  `components/golden-path/*Step.tsx` with typed props; JSX and every `data-testid` moved verbatim
  (tsc + `next build` clean). The 345-line studio (selected) step remains inline — it is the most
  state-coupled block and is the next split.
- Full backend suite wall time is unchanged (~13–25 min on this box); no test was skipped or
  parallelised to hide it.

## Jewellery realism: the proofs now read as metal pieces (2026-09-04, ADR-0005)
Owner: «ما عجبني التصميمات لأنها غير حقيقية». Measured, not guessed: mean strokes were 1.0–1.7 mm
(up to 0.135 of height), bails floated on stalks, frames used spokes, dots were specks. Fixed in
the deterministic construction (no AI, no new fonts): stroke buffer sized from the face's own
metal (lift the thinnest hairline class to the 0.85 mm neck minimum, or bring a light face toward
0.082·height; never erode — erosion and a local thin-parts pass were both measured to lower
validity and rejected), Cairo recipes on the `wght=300` instance, bails on the central top of the
main body with the chain hole kept clear, chain rings on the true ends of the metal (soldered
overlap, no bridges), medallion names kissing a 1.1 mm ring with solder fillets, rounded plates,
dots ≥ 1.25 mm circles, solder fillets on every bridge landing, stroke weight in the visual
ranking, crisper render. Validity of the 48-candidate pool rose for every golden text (e.g. ميثة
34→45, نورة 27→42, long phrase 24→35). Before/after gold sheets (`docs/evidence/realism/`) were
inspected in headless Chromium at each step. Golden visual fixture regenerated deliberately
(text-truth fixture untouched). Tests `test_jewellery_realism.py` 4/4; full suite: see CI on this
commit. Honest: still parametric lettering from licensed print fonts; a small Naskh charm stays
heavier because its hairlines must physically reach the neck minimum.

## The two remaining reference-study gaps, engineered down (2026-09-04, owner "solve these issues")
1. **True Thuluth / Diwani** — still a license purchase (no OFL true cut exists; none is claimed),
   but now a ten-minute install instead of an engineering task: `scripts/add_font.py` inspects
   the bought binary (Arabic coverage, `init/medi/fina` contextual features, mark positioning,
   golden names shaped without `.notdef`), refuses UNKNOWN/INTERNAL rights, and with `--write`
   copies font + EULA into the assets, appends the registry entry (sha256, next diversity index)
   and re-runs the identity proof on the golden names through the real registry. The capability
   map now computes `THULUTH`/`DIWANI` from the registry, so the chip stops saying "(inspired)"
   the moment a licensed cut is onboarded — proven in `test_font_onboarding.py` with a temp
   registry (Katibeh's binary stands in for a purchased Thuluth). Buying guide:
   `docs/FONT_LICENSING.md`. Registry loader accepts an explicit assets dir (dry runs never
   touch the vendored fonts).
2. **Photoreal without keys** — the photoreal tab no longer dead-ends on `PHOTOREAL_PREVIEW_
   UNAVAILABLE`: it falls back to the deterministic studio render of the same vector (chosen
   metal + scene ground: studio white, clean, luxury black, Beyond Style gold — `?scene=`),
   labelled honestly as a deterministic render, never as AI. The paid tier stays available the
   moment `OPENAI_API_KEY` exists; nothing is faked.
Tests: `test_font_onboarding.py` 5/5, `test_reference_presentation.py` 4/4, font capability
suite green; frontend build clean.

## Reference study applied: script picker + real-metal proof render (2026-09-04, ADR-0004)
Owner shared arabicdesign.ai as the bar for "real jewellery design" (site unreachable from this
sandbox; studied via its public descriptions — flow: text → script → visual direction →
treatments → refine → HD/SVG, credit-priced, no manufacturing concepts).
- **Script picker** on the start step (Naskh, Ruqaa, Kufi, Nastaliq, Modern, Thuluth-inspired,
  Diwani-inspired). Resolved through the rights-gated capability map: Thuluth/Diwani return
  `STYLE_NOT_AVAILABLE` + the closest licensed face + a visible note (never a silent
  substitution); the script's curated recipes join the pool additively and its faces get a
  transparent +4 ranking bonus. Brief echoes `script_family` + `script_resolution`.
- **Real-metal render** of the same vector path: `?material=` on both preview-SVG endpoints
  (silver-925, gold-18k-yellow/rose/white, platinum) — SVG gradient + bevel lighting + soft
  shadow on a studio ground, deterministic, no raster/AI/credentials. Path data proven
  byte-identical to the flat proof; the dimensioned agreement proof stays technical. Rendered
  gold sample inspected in headless Chromium (bevel, highlight, shadow visible).
- Metal chosen at the start drives the 10 proofs, the studio 2D view (chips to switch), the 3D
  viewer and the photoreal request; stored as `material_preference`.
Tests `test_reference_presentation.py` 4/4; generation/quality-gate/archetype/intake/API/reference
regressions re-run (see CI). Honest: no licensed true Thuluth/Diwani cut exists (font purchase
decision); photoreal stays `PHOTOREAL_PREVIEW_UNAVAILABLE` until the owner runs it with keys.

## Security slice: framework CVEs closed, headers, malware scan, S3, staff roles (2026-08-29)
Owner mandate "solve 1–8" → risk #2. Root cause of the previously reverted upgrade found and fixed:
- **FastAPI 0.141.1 + Starlette 1.6.0** now pinned (all 9 previously open Starlette advisories closed).
  The "candidates invisible under real HTTP" regression was a **timing race, not persistence**:
  FastAPI ≥0.118 runs yield-dependency teardown (the session commit) AFTER the response is sent,
  so a client that immediately fetched a candidate beat the ~48-row commit. Reproduced with real
  uvicorn (DB rows = 0 right after a 200 listing 10 candidates), invisible under TestClient
  (regenerates on demand). Fix: `app/db/commit_middleware.py` commits at `http.response.start`
  (rollback on 4xx/5xx; commit failure → 500, never a silently lost write). Regression tests
  `test_commit_before_respond.py` 4/4; real-HTTP round trip with immediate GET passes.
- Security headers on every API response (`app/security/headers.py`: nosniff, DENY framing,
  no-referrer, permissions-policy, restrictive CSP; HSTS when `SECURE_HSTS=true`). Frontend
  CSP + headers via `next.config.mjs` `headers()` (connect-src limited to self + backend).
- Malware scanning: `ClamdScanner` (real INSTREAM protocol, tested against a protocol double);
  infected uploads are refused and never stored; `REQUIRE_MALWARE_SCAN=true` refuses anything
  not positively CLEAN (production policy; scanner outage = refusal, never a fake "clean").
- Object storage: `S3PrivateStorage` (S3/R2/MinIO via boto3, private objects, random keys,
  never served by URL), selected by `OBJECT_STORAGE=s3`. Adapter tested with a fake client —
  a real bucket has not been exercised from this environment.
- Staff roles: `REVIEWER_API_TOKEN` scoped to `/api/admin/review/*`; `ADMIN_API_TOKEN` full;
  constant-time comparison; closed by default. Customer accounts/MFA remain P1 (not built).
Tests: `test_security_hardening.py` 7/7 + 57/57 API/persistence/approval suites on the new
stack; frontend build clean. Honest: CSP keeps `'unsafe-inline'` for scripts/styles because
Next.js's runtime needs it without a nonce pipeline.

## CI red since 49c4ceb — broken pin combo fixed (2026-08-28)
Discovered while verifying the branch for the owner's Replit pull: GitHub Actions CI had been
failing for the last 8 commits (backend job only; frontend + secret-scan green). Root cause:
the security bump to `fonttools==4.60.2` (RELEASE_EVIDENCE.md dependency table) was pinned but
never installed in the local environment, which still ran fontTools 4.53.1 — so every local
"suite green" since that bump ran a different fontTools than CI. fontTools 4.60.2's HarfBuzz
repacker calls `uharfbuzz.serialize_with_tag`, absent from the pinned `uharfbuzz==0.42.0`, so
all 24 axis-plumbing (variable-font instancer) tests crashed in CI. Fix: `uharfbuzz==0.56.0`.
Evidence: CI failure reproduced locally on the exact pinned combo, then on 4.60.2+0.56.0 the
24 axis tests, the 11-test immutable seven-name golden fixture and the quality gate all pass
(59/59 — shaping and geometry hashes did NOT drift across the HarfBuzz upgrade). Full-suite
confirmation is CI's own run on this commit; local full suite also running. Secondary CI
finding, not code: the artifact-upload step hit the GitHub artifact storage quota
("Artifact storage quota has been hit") — old CI artifacts need pruning or the step made
non-blocking; it did not cause the test failures.

## Double-Face Ring Engraving (2026-08-29, completes the wedding-ring production case)
Outer phrase + inner names (photos 12–15) as one design. Text truth preserved structurally:
the inner engraving is the SECOND LINE of the single immutable source text (outer\ninner — the
two-name necklace pattern), so one confirmed text and one identity proof cover every codepoint
("\n" counts as layout, the same convention as shape_multiline's separators). More than two
faces is refused (ValueError), never silently merged.
- `ring_band.build_ring_geometry`: per-face build (shape → outline → downscale-only fit →
  center); the inner flat pattern is MIRRORED about the strip centerline so back-face engraving
  reads correctly after rolling (regression-proven by re-mirroring against a single-face build).
  Engraving-mode violations (stroke/margins) now checked on BOTH faces.
- Persistence: `inner_text_geometry_wkt` on design_candidates + design_versions (migration
  a9d24c8e01b7), threaded through candidate → selection → version → edits.
- **Hash gap fixed**: every ring shares one CUT rectangle, so version geometry_hash previously
  could not distinguish two different engravings. `_design_geometry_hash` now binds
  CUT|ENGRAVE|INNER for rings; silhouette products keep the CUT-only hash byte-identical (no
  existing version renumbered — golden fixture green). Approval/export re-verification updated.
- DXF: ENGRAVE_INNER layer + workshop note ("back face; mirrored in front view; engrave with
  strip flipped"). Agreement proof shows the inner face as its own labelled band panel
  (الوجه الداخلي). 3D viewer renders the inner marks at the inner radius facing into the ring.
- Frontend: ring flow gains an optional "نقش داخلي" input; the combined text is confirmed as
  one; multi-line text displays render both lines.
Tests: `test_ring_dual_face.py` 7/7 + 73/73 across ring/mesh3d/agreement/persistence/approval/
golden-fixture/quality-gate neighbors; frontend typecheck+build clean.

## 3D Viewer (2026-08-29, owner-planned "عرض التصميم ثلاثي الأبعاد")
Customer trust view before approval, per the 3D Stage rules (Three.js for visualization only;
the 2D Design Graph stays canonical; only after 2D selection/QA):
- `services/mesh3d.py` + `GET /api/versions/{id}/mesh3d` (owner-gated, 404 anti-enumeration):
  canonical 2D polygons (holes preserved — payload area re-verified equal to shapely area),
  real thickness (ring spec or workshop rules), real mm dimensions, ring bend radius
  (EU size = inner circumference → r = size/2π), and deterministic weight estimates
  (area × thickness × alloy density; densities are documented constants — rules math, no AI).
- `components/Viewer3D.tsx`: client-side Three.js extrusion of the served polygons; rings are
  bent around the real cylinder radius with the ENGRAVE layer on the outer face; five metal
  materials; auto-rotating 360° with orbit controls; graceful null render when WebGL is
  unavailable (the 2D proof remains authoritative). Loaded via dynamic import only when the
  3D tab opens — shared first-load JS unchanged (103 kB).
- Studio gains a ثلاثي الأبعاد tab showing dimensions (or ring size/band width), estimated
  weight in grams per material, and the explicit "not the manufacturing file" note.
Tests: `test_mesh3d.py` 3/3 (payload↔geometry equality, deterministic weight math, ring bend
radius + engraving passthrough, owner gate); frontend typecheck + build clean. Honest notes:
weight is area×thickness×density (no stones/chain mass; chain/bail/stones visualization not in
this slice); materials are PBR approximations, not calibrated renders.

## Engraved Ring Band product (2026-08-29, owner "go ahead" on the ring slice)
The wedding-ring case (photos 12–15: outer phrase, inner names, 4cm×0.75cm field) is a
different manufacturing mode: marks on solid metal, not cut-outs. Implemented as a first-class
construction through the SAME build choke point:
- `engines/ring_band.py`: flat-pattern build — CUT = developed strip (EU size = inner
  circumference; length = size + π·thickness at the neutral axis), ENGRAVE = text + parametric
  border (none/double_line/ornament_diamond) centered with real margins. Text is NEVER altered
  to fit: uniform downscale only, blocked (ENGRAVING_TEXT_OVERFLOW) below 60% legibility.
- Engraving-mode validation (real mm): ENGRAVING_STROKE_TOO_THIN (<0.30mm measured on the
  actual engrave geometry), ENGRAVING_MARGIN_TOO_SMALL (<0.8mm to the edge),
  RING_SIZE_OUT_OF_RANGE (EU 44–70, band 5–10mm). Dots float freely (no bridges) — correct for
  engraving. Ring rules profile lifts the pendant slenderness/width caps that don't apply to a
  strip that gets rolled.
- `RecipeParams.ring` (None = silhouette product) excluded from candidate identity when None —
  regression-proven that NO existing design was renumbered (seven-name golden fixture green).
- Generation routes on product_type=="ring" (9 fonts × 3 borders × 2 heights = 54 candidates;
  diversity re-featured from the ENGRAVE layer since every band shares one CUT rectangle);
  edits version through the same choke point; construction can never change by edit; repair
  options honestly empty for rings (future slice).
- DXF: ENGRAVE layer + RING_SIZE_EU/BAND_HEIGHT_MM header vars alongside CUT/HOLES.
- Frontend: product picker (قلادة/خاتم), EU size 44–70 + band width selectors; brief carries
  ring_size_eu/band_height_mm into generation hints and syncs the request's product type.
- Fixed en route: `agreement_proof_for_version` read product from the wrong table (Design id
  against DesignRequest) and silently fell back to "pendant" — now Design → DesignRequest.
Tests: `test_ring_band.py` 8/8 (flat-pattern math, strip geometry, margins+identity, floating
dots, size gate, DXF layers, end-to-end ring flow with Arabic agreement proof, hash-stability
invariant) + agreement 6/6 + golden fixture/quality gate/persistence/axis suites green.
Honest limitations: no inner-face second engraving yet (one face per design); ♥ separator
(U+2665) is in NO vendored font — a text containing it fails identity honestly rather than
silently substituting; ring photoreal prompting reuses the generic product prompt.

## Dimensioned Agreement Proof (2026-08-29, owner mandate with 16 real production photos)
Owner requirement: the customer must approve a picture that carries the REAL dimensions —
matching Beyond Style's manual spec sheets (روز/شغف/فرح necklace sheet, the ring's 4cm×0.75cm
engraving drawing) — and AI previews must carry the same dimensions so the manufactured piece
matches the agreed image. Implemented:
- `exporters/agreement_proof.py`: deterministic dimensioned approval SVG — canonical design,
  real-mm dimension arrows measured from the built geometry, spec block (text/product/font/
  dimensions/version·hash), Arabic footer. Byte-identical per version → stable sha256.
- `GET /api/versions/{id}/agreement-proof` (owner-scoped, X-Content-Sha256 header; unowned
  access reads 404 per the API's anti-enumeration contract).
- Approval now records `agreement_proof_sha256` in the CUSTOMER_APPROVED audit event — the
  approval is bound to the exact dimensioned picture the customer saw.
- AI previews: `stamp_dimensions_strip` composites a strip at SERVE time (stored artifact
  untouched) with the real mm from the vector geometry + "AI PREVIEW — NOT THE MANUFACTURING
  FILE" + version·hash. Dimensions always come from geometry, never from the raster.
- Frontend approve step displays the dimensioned proof (falls back to plain proof SVG) with an
  explicit Arabic/English note that approving = agreeing to these dimensions.
Tests: `test_agreement_proof.py` 6/6 (real-mm match, exact-text preservation, determinism,
approval-hash binding, pixel-exact strip compositing on a locally rendered canonical PNG — no
fabricated AI output, endpoint auth). Honest limitation: ring-band engraving construction
(photos 12–15) is a product type the parametric generator does not yet build; the proof/strip
machinery applies to all supported products, ring bands need their own generation slice. 3D
viewer: deferred by owner ("بعد كدا بضيف خاصيه عرض التصميم ثلاثي").

## Live CORS failure fixed: first-party origins now built in (2026-08-28, real device report)
With the frontend wired (below), the owner's phone showed CONNECTION_FAILED on the live site —
the browser's fetch threw, the CORS signature: the deployed backend was missing the
`ALLOWED_ORIGINS` secret, so it only allowed `http://localhost:3000`. Fix: `app/main.py` now
always allows the first-party origins (localhost:3000, frontend-sigma-sable-22.vercel.app,
beyondstyle.ae, www.beyondstyle.ae); `ALLOWED_ORIGINS` extends the set instead of being the
only gate. Regression test added (`test_cors_allows_production_frontend_without_the_secret`);
`test_deployment_readiness.py` 12/12 passed. Owner action to pick this up: pull latest in the
Replit workspace and republish the deployment.

## Backend published — frontend wired to it by default (2026-08-28)
Owner published the Replit deployment: `https://beyond-style-uae-design-genertor.replit.app`
(URL supplied by owner; unreachable from this session — the sandbox egress proxy blocks all
Replit domains, re-verified, so backend liveness is owner-verified via `/health` in a browser,
not by this session).

Change: `next.config.mjs` now defaults `NEXT_PUBLIC_API_URL` to that published backend on
Vercel builds (`env` key, baked at build time). An explicit `NEXT_PUBLIC_API_URL` in the Vercel
dashboard still overrides it; local dev (no `VERCEL`) keeps the empty base + localhost rewrite.
This removes the last manual dashboard step that kept production dead. Verified locally:
`VERCEL=1 next build` inlines the URL into all three page chunks; plain build keeps `""` and
the dev rewrite. `docs/DEPLOYMENT.md` env table updated (var is now an optional override).

Remaining to VERIFIED_E2E (production): owner confirms `/health` returns JSON on the published
URL, `ALLOWED_ORIGINS` secret on Replit includes `https://frontend-sigma-sable-22.vercel.app`
(without it the browser is CORS-blocked), then run the Golden Path on the live site.

## Production frontend failure diagnosed (2026-08-27, real device report)
Owner tested the live Vercel deployment on mobile: UI loads, every action fails with "انتهت صلاحية الجلسة".
Diagnosed against the real deployment (`web_fetch_vercel_url` on `/api/fonts`): **404 with
`x-vercel-error: DNS_HOSTNAME_RESOLVED_PRIVATE`** — `NEXT_PUBLIC_API_URL` is unset, so the app fell back to
relative `/api/*`, the dev-only rewrite (baked into the build) proxied to `localhost:8000`, and Vercel refused
the private hostname. The frontend then mislabelled that non-backend 404 as SESSION_EXPIRED.

Fixed in code (this commit):
- `lib/api.ts`: a non-JSON error body means the response did NOT come from our backend (which always sends
  structured `error_code` JSON) → classified `BACKEND_UNAVAILABLE`, never `SESSION_EXPIRED`.
- `next.config.mjs`: the localhost rewrite is no longer emitted on Vercel builds (unless `BACKEND_URL` is
  explicitly set). Local dev path re-verified: 200 via the rewrite.

NOT fixed by code, unchanged release blockers (owner actions, per RELEASE_EVIDENCE.md):
1. **No backend is deployed** — the Replit deployment contract is documented and waiting.
2. **`NEXT_PUBLIC_API_URL` is not set** on the Vercel project — no env-var tool exists in this session.
The site cannot work for customers until both are done; after this commit it at least reports the true
condition ("الخدمة غير متاحة حالياً") instead of a fake session expiry. Vercel auto-deploys this branch, so
the corrected message ships with this push.

## P4 First Human Review Analysis (this slice)
**The wave has not been reviewed: 0 review rows, 0 customer responses — verified against the append-only log
before any derivation.** No winner is claimed. The P4 analysis pipeline is built and emits every claim honestly
blocked; re-running it after real reviews land produces the real analysis with no code change.

| Item | Status | Evidence |
|---|---|---|
| Evidence verification counts independent reviewers, not rows | VERIFIED_LOCAL | `test_verification_counts_independent_reviewers_not_rows` (a revision never fakes a third reviewer) |
| Critical dimensions expanded to the P4 five | VERIFIED_LOCAL | safe at zero reviews; disagreement + recommendation floor share the set |
| Agreement adds median + reviewer count per dimension | VERIFIED_LOCAL | `REVIEWER_AGREEMENT_REPORT.json`; mean never shown without spread/values |
| Engineering vs human kept as separate claims with observed verdicts | VERIFIED_LOCAL | `test_engineering_vs_human_verdicts` (AGREE/PARTIALLY_AGREE/CONFLICT/NOT_COMPARABLE) |
| Golden analysis restricted to preliminary vocabulary | VERIFIED_LOCAL | `test_golden_signal_uses_preliminary_vocabulary` |
| Bracelet gap reported, no winner manufactured | VERIFIED_LOCAL | `BRACELET_COMPARISON_BLOCKED`, +2 families needed; generation proposal documented, nothing generated |
| Composition scope labelled FONT_FAMILY_COMPARISON_ONLY | VERIFIED_LOCAL | `test_single_composition_products_are_family_comparison_only` |
| Overall claim blocked on structural unfairness even past thresholds | VERIFIED_LOCAL | `test_overall_claim_blocked_when_coverage_is_structurally_unfair` |
| Pipeline derives real winners only from real reviews | VERIFIED_LOCAL | `test_full_pipeline_derives_winners_only_with_real_reviews` (test DB, never evidence) |

## P3 Evidence Threshold Repair + Review Wave 1 (previous slice)
The P2 evidence rule was **unsatisfiable by construction** and is retired, not relaxed. New confidence model,
corrected terminology, blinded review, agreement analysis, and HUMAN_REVIEW_WAVE_1 prepared. Still 0 human
reviews — no winner is claimed. See CURATION_STATUS.md.

| Item | Status | Evidence |
|---|---|---|
| Retired rule flagged STRUCTURALLY_IMPOSSIBLE_THRESHOLD | VERIFIED_LOCAL | `threshold-audit.json`: `max_items_per_product_family = 1`; `test_audit_detects_the_structurally_impossible_threshold` |
| Item confidence 1/2/3+ replaces the old model | VERIFIED_LOCAL | `test_item_confidence_two_reviewers_is_medium_not_high` |
| "Second reviewer = HIGH" terminology corrected everywhere | VERIFIED_LOCAL | `test_confidence_is_driven_by_reviewer_count_not_volume` (9 reviews/1 reviewer = LOW) |
| PRODUCT_COMPARISON_READY gates every winner | VERIFIED_LOCAL | `test_product_not_comparison_ready_without_three_reviewed_families`, `test_one_reviewer_per_family_is_not_comparison_ready` |
| Commercial floors (Appeal/Premium/Fit >= 4) enforced | VERIFIED_LOCAL | `test_commercial_family_needs_the_commercial_floors` |
| Overall claim needs >=3 products, >=6 reviews | VERIFIED_LOCAL | `test_overall_claim_needs_breadth_across_products` |
| Disagreement surfaced, never averaged away | VERIFIED_LOCAL | `test_disagreement_on_a_critical_dimension_is_flagged` (mean 3.5 shown WITH values [5,2]) |
| A revised opinion is not a second reviewer | VERIFIED_LOCAL | `test_a_revised_opinion_does_not_count_as_a_second_reviewer` |
| Review pack blinded until submission | VERIFIED_LOCAL | `_blind()` strips prior decision/reviewer/scores; engineering stays visible |
| 12 review dimensions replaced per brief | VERIFIED_LOCAL | ArabicCorrectness…WouldRecommend; critical = ArabicCorrectness, Legibility, ProductFit |
| HUMAN_REVIEW_WAVE_1 prepared, labelled not-a-winner | VERIFIED_LOCAL | `wave-1.json`: 13 items, `AWAITING_HUMAN_REVIEW`; `test_wave_1_is_labelled_and_not_called_a_winner` |

**Honest status:**
- **Still 0 human reviews and 0 customer responses.** 0/9 products comparison-ready; every family claim blocked.
- **A real bug was found and fixed in my own P2 code**: `**ready` spread its own `status` key over the verdict,
  so a product that passed readiness but had no qualifying candidate reported PRODUCT_COMPARISON_READY instead
  of INSUFFICIENT. Caught by a new test.
- **Bracelet cannot reach comparison-ready** from this corpus: only 1 of 4 items passes manufacturing, giving one
  rival family. Fixing it needs more manufacturable candidates — new generation, out of scope here.
- **Composition diversity within a product is 1** across the corpus; also a generation question.
- Dimension names changed, which is safe only because zero reviews existed. Any future change would lose data.

## P2 Curation Analysis + Customer Validation (previous slice)
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
- ~~Thresholds: 5 scored reviews across 3+ items per family; 2 reviewers for HIGH confidence~~ — **RETIRED in P3**:
  the distinct-item clause was structurally impossible and the HIGH-confidence rule was wrong. See CURATION_STATUS.md.

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

### One-run procedure to move CLAUDE / GPT_IMAGE to VERIFIED_EXTERNAL (owner, ~10 min, paid)
Risk #5 of the 2026-08-29 assessment: the external-model branches have never executed. Nothing in
this environment can run them (no credentials; `workflow_dispatch` is refused for this integration
with 403), so the run is the owner's — the code path is ready and the evidence file is produced
automatically:
1. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**:
   `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` (server-side only; never in the frontend).
2. GitHub → **Actions → "External AI Acceptance" → Run workflow** (branch
   `claude/p0-golden-path-audit-jtyduw`). Runs `make external-ai-e2e` against a fresh PostgreSQL.
3. Download the `external-ai-acceptance-evidence` artifact and commit it as
   `docs/evidence/external-ai-acceptance.json` (redaction allow-list means it holds only hashes,
   statuses, tokens, latency, cost — no prompts, images or keys).
4. Read the statuses: CLAUDE and GPT_IMAGE must show `VERIFIED_EXTERNAL`; if one shows `FAILED`,
   the JSON carries the provider error class — paste it here and it is a real defect to fix.
   `SKIPPED_NO_CREDENTIALS` after step 1 means the secret name is wrong.
5. Expected cost per run: one Claude structured-DNA call plus one GPT-Image-2 generation (well
   under 1 USD at 2026 list prices). Never wired into push/PR CI.
Until that run lands, every claim below stays SKIPPED_NO_CREDENTIALS — not a fake pass.

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
