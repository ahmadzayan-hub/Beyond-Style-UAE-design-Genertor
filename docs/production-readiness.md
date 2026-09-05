# Production Readiness

Updated: 2026-09-05 · Latest slice: **Arabic Calligraphy Source Registry + Text Integrity Engine +
Vector Composition Engine + Jewelry Manufacturing Gate** (ADR-0006, six increments on top of the
jewellery-realism slice, ADR-0005). The report below is the honest readiness picture for the
owner specification; earlier slice tables follow unchanged.

## Readiness report — 2026-09-05 (spec "BEYOND STYLE ARABIC JEWELRY DESIGNER")

Rule applied: a percentage is claimed only from executed evidence (tests, browser E2E, CI). 100 %
is never claimed for an area whose acceptance E2E has not passed.

| Area (spec section) | Readiness | Evidence (executed) | Not done / caveat |
|---|---|---|---|
| Text integrity (ميثه never becomes ميثة; hidden chars; NFC only) | **95 %** | `test_text_integrity.py` 7/7; acceptance E2E: TEXT INTEGRITY PASS, confirm/approve displays byte-exact; `certify()` on version + exports | sacred-text special mode not built (blocks are generic, not a scripture register) |
| Calligraphy source registry (never a fake locked style) | **85 %** | 37 rights-cleared OFL families vendored; `test_source_registry.py`, `test_font_onboarding.py` 5/5, `test_font_upload.py` 3/3; style catalogue with honest statuses; upload API + `/admin/fonts` UI; `/styles` browser (favourites/recent persisted) | Thuluth/Diwani are INFLUENCED_ONLY until a licensed source is uploaded (by design, not imitated); glyph-variant library per calligraphic style is partial (OT sets + dot/swash variants only) |
| Shaping (HarfBuzz, contextual forms, marks) | **95 %** | existing Arabic regression suite; identity proof per cluster; multi-name proof through per-name offsets | Nastaliq true source absent (influenced) |
| Vector Composition Engine (6–12 variants from the same glyph vectors) | **85 %** | `test_composition_engine.py` 4/4 (engineering case 23/24 valid, 10 diverse); E2E: 10 different compositions for the seven names (family tree / arch / circular / horizontal flow / oval / interwoven) | ornament/component library is small (bridges, rings, frames, swashes); no calligraphic ligature re-composition |
| Materials + weight from actual area | **90 %** | 11 materials; `weight_report` tests; E2E shows weight from area×thickness×density | 18K 60×40 mm ≈10 g reached only for oval/arch layouts at 1.0 mm (documented in ADR-0006/test) |
| Manufacturability QA ("JEWELRY QA: PASS/FAIL", real attachments) | **90 %** | `test_manufacturing_gate.py` (QA plain language, attachment facts); E2E: JEWELRY QA PASS | workshop rule values remain INDUSTRY_TYPICAL_UNCALIBRATED (calibration kit exists) |
| Vector editor (transforms, booleans, fail-safe, versioned) | **75 %** | `test_vector_edit.py` 8/8 (engine + DB/API); E2E: Pro-mode translate → version 2 → locked | node/anchor editing and pen tool NOT built (listed as unavailable in the UI, never fake); scale is uniform only |
| Real repair (bridges / rings / gaps / thicken) | **85 %** | validator-fix → vector op → dry-run → offered only when errors drop; bridge, ring and narrow-gap tests in `test_vector_edit.py` | gap widening is refused (honestly) when the hole sits inside the letters |
| Approval states + immutable lock | **90 %** | existing lock suite; E2E: approval hash of v2, later edits invalidate; **secure customer link**: single-use, 72 h, bound to the geometry hash, retype-to-confirm, recorded as SECURE_LINK (`test_approval_link.py` 2/2, `e2e/approval_link_e2e.py`) | no OTP/identity check on the link holder; internal approvals remain possible and are labelled INTERNAL_UI |
| Exports SVG / DXF / PDF / PNG + manifest | **95 %** | `test_pdf_export_is_true_scale_vector_and_reimports`, `test_png_preview_raster_export_passes_raster_fidelity`; E2E: three vector exports, `X-Export-Fidelity: PASS` | PNG is a preview raster (508 dpi, scale/hash chunks, coverage-area fidelity ≤1.5 %) recorded as kind=preview — it never counts toward WORKSHOP READY |
| Export fidelity gate (re-import → compare → WORKSHOP READY) | **95 %** | fidelity stored per export; readiness ladder from facts; E2E: WORKSHOP READY | the PDF re-import found by the E2E (multi-op lines) fixed in `44001e0` |
| Style browser / 10-step wizard / Pro mode / premium UX | **70 %** | `/styles`, Golden Path steps, Pro panel, actual-size preview mode, mobile action bar; build green; E2E screenshots 360/390/768/1280 | wizard is 7 steps (start → confirm → generate → proofs → selected → approve → approved), not the spec's 10; no on-body preview modes |
| Mobile-first (360 px) | **85 %** | E2E: no horizontal overflow at 360/390/768/1280 on start + styles; mobile flow passes at 390 | full flow at 360 not run as a separate viewport (only layout checks) |
| Reference import (IP reminder, "same style, change text") | **80 %** | existing reference flow E2E; copyright notice | unchanged this slice |
| AI as art director only | **100 % of what exists** | deterministic engines own text/geometry; AI tools blocked from writes | external providers unverified here (no credentials) |
| Performance | **75 %** | seven-name generation 14.6 s on 4 cores (52 s inline) after `8c4bf41` (proxy placement search, erosion reuse, fork pool over recipes; byte-identical candidates); single names 2–8 s | 2-core hosts (CI, small Replit) still see ~30 s; no progress stream to the customer yet |
| Security | **80 %** | secret scan in CI, private font storage never served by URL, admin token on upload, session-scoped ownership | private font licence text stored but no encryption-at-rest claim |
| Tests / CI | **see below** | full local suite result recorded below; CI runs 33971823356 / 33972231291 / 33972484731 / 33972620082 | — |
| **Mandatory acceptance E2E (seven names)** | **PASSED 2026-09-05** | `e2e/acceptance_seven_names_e2e.py`, evidence `docs/evidence/acceptance-seven-*` | run on localhost, not on the production deployment (Production Monitor red — deployment unreachable) |

### Issues by severity
- **Critical (blocks production use)**: none open in code. The production deployment itself is unreachable (Production Monitor workflow red on every push) — an operations task, not a code defect.
- **High**: (1) seven-name generation 15–30 s depending on cores, with no progress stream to the customer; (2) the secure approval link has no OTP/identity check on the holder (anyone with the link can approve); (3) workshop rule values uncalibrated for Beyond Style's actual processes.
- **Medium**: (1) Thuluth/Diwani/Nastaliq need licensed sources (upload path ready); (2) no node/pen editing; (3) wizard is 7 steps and preview modes are flat/actual-size only; (4) gap widening repair only where the cut stays outside the letters.
- **Low**: (1) PNG preview raster has no on-body/scene composition; (2) proof cards are SVG previews, photoreal remains optional/external; (3) `experimental.proxyTimeout` only matters for the local/CI rewrite.

### Local full-suite evidence
`cd backend && python3 -m pytest -q` on HEAD `8c4bf41` (PostgreSQL 16, 4 cores): **511 passed, 0 failed, exit 0** in ~35 min (log `full_s5.log`, 2026-09-05 15:05–15:41 UTC). Re-run on `9fd2379` (approval link + PNG export): 515 collected, 513 passed; the 2 failures were the tests that encoded "png is never an export" — updated in `3c513de` to the real contract (AI images never exported; PNG = lock-gated raster of the master vector, kind=preview) and passing, i.e. effective **515/515** on the committed tree. An earlier run on the pre-fix tree timed out at 50 min because the seven-name generation was 75 s per call under CPU contention; that is what the perf work in `8c4bf41` addressed. CI: runs 53–56 failed only on the three tests fixed in `8c4bf41` (phrase routing ×2, vector-edit text protection); run 57 (`8c4bf41`) passed the backend suite but failed the evidence step (seven-name family count, fixed in `5686ce3`); **runs 59 (33976307374), 60 (33976362966), 61 (33977253484, secure approval link) and 62 (33977527995, proof fix) are green on all four jobs** — backend suite, evidence report, frontend build, browser E2E incl. `approval_link_e2e.py`. Run 63 (`9fd2379`, PNG export) failed on the two tests that encoded "png is never an export"; they now assert the real contract (AI images are never exports; the PNG is a lock-gated raster of the master vector, kind=preview) — see the run recorded for the follow-up commit.

## Slice 5 evidence (decorative engine / rules / multi-line / CI)

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| Glyph Variant Library | WORKING | `test_variant_registry_loads_and_validates`, `test_dot_styles_change_geometry_not_identity`, `test_swash_adds_ornament_only` | data-driven registry (OT feature sets, 4 dot styles, 3 swashes); geometry changes, identity proof intact | OT sets rarely alter common name letters in these fonts (probed honestly); per-glyph tail editing needs deeper glyph machinery |
| Kashida elongation | WORKING | `test_kashida_preserves_identity_and_elongates` | +30% width on joining names; tatweel is shaping-input only, cluster indices remapped to source; نورة correctly unchanged | — |
| Aesthetic bridges | WORKING | `test_vertical_bridge_prefers_dot_over_chord`, `test_radial_bridge_in_medallion_no_chord`, `test_bridges_deterministic` | vertical-slab dot joins, radial medallion spokes, round caps + closing fillet; deterministic | bridge width taper is uniform (no artistic taper yet) |
| Workshop profiles | WORKING | `test_profiles_versioned_and_complete`, `test_earring_profile_blocks_pendant_sized_design`, `test_slenderness_gate` | wp-1.0.0: 6 product×material profiles; earring envelope blocks oversized designs; slenderness gate | values are INDUSTRY_TYPICAL_UNCALIBRATED — Beyond Style workshop calibration required before production claim |
| Multi-line long text | WORKING | `test_long_text_yields_10_valid_stacked_options` (7-name chain + phrase) | balanced lossless line breaking, per-line shaping+identity merge, stacked bodies, deterministic width-fit; 10 valid options each | circular/arc text path not yet; last-line readability at 4 lines is tight |
| Copilot variant controls | WORKING | `copilot_e2e.py` + EDITABLE fields | dot/swash/kashida/lines/variant-set editable → new immutable versions | — |
| CI pipeline | ADDED | `.github/workflows/ci.yml` | postgres service, migration cycle, full pytest, evidence artifact upload, frontend build | not yet observed green on GitHub (push required); browser E2E not in CI |
| Acceptance evidence (5 cases) | WORKING | `e2e/generate_evidence_reports.py` (exit-code gated) | all 5 PASS: 10 options, ≥4 composition families (7-name: 5), ≥2 stylistic families, IoU < 0.86, all manufacturing+identity pass; PNG sheets in docs/evidence | — |

## Slice 4 evidence (quality gate / proofs / copilot)

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| High-fidelity relief proofs | WORKING | `test_relief_proofs_show_text_layer` | plate compositions render base + differentiated text layer; production SVG/DXF unchanged single silhouette (`test_production_svg_unchanged_single_silhouette`) | proof styling is 2-tone flat, no material shading yet |
| Proof ↔ canonical fidelity | WORKING | `test_openwork_proof_matches_canonical_geometry`, `test_counters_and_holes_visible_in_proofs` | proof path bbox == geometry mm bounds ±0.02; subpath count == exterior+holes; evenodd | — |
| Perceptual dedup | WORKING | `test_no_near_duplicates_in_top10` (5 names) | occupancy-grid IoU gate 0.86; measured max pairwise IoU 0.78–0.85 per name (diversity-report.json) | grid comparison only; no learned perceptual model (by design) |
| Structural diversity | WORKING | `test_structural_diversity_spread` | per name: ≥4 compositions, ≥2 fonts, ≥5 DNA families in top 10 | vertical/circular text layouts limited to frame/plate forms |
| Curated 32-archetype library | WORKING | `test_curated_library_dna_complete` | 32 recipes ×(family, purpose, products, text-length fit, mfg constraints, rights=BEYOND_STYLE_ORIGINAL_PARAMETRIC); distinct purpose each | 32/150; pgvector retrieval not yet needed at this scale |
| Long-text adaptation | WORKING | `test_every_golden_name_yields_valid_top10[ما شاء الله]` | deterministic stroke+size boost for >8 letters keeps phrase manufacturable | single-line only; multi-line phrase composition later |
| Quality evaluation layer | WORKING | `test_top10_all_pass_manufacturing_and_identity` | 7-dimension report per candidate; heuristic dims labelled HEURISTIC / NOT ML-VALIDATED; persisted on candidates | visual dims remain geometric proxies |
| Golden visual regression | WORKING | `test_golden_visual_regression` | 5-name fixture (own parametric outputs): top-10 ids + combined geometry sha256; regenerator `e2e/generate_golden.py` | fixture grows with future golden dataset |
| Designer Copilot (minimal) | WORKING | `e2e/copilot_e2e.py` | sliders (stroke/spacing/width/height/size) + composition/loops selects; Apply → NEW version; undo/redo navigates immutable versions; edited v2 approved+locked; invalid edits flagged & blocked from approval | per-glyph move/tail/swash editing not yet (needs glyph-variant machinery) |

## Slice 3 evidence (intake / security / customer UI)

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| Private reference intake | WORKING | `test_valid_image_intake_persists_privately` | PRIVATE status, owner-token-only content access, no public URL, honest PENDING_SCAN | no real malware scanner wired (adapter ready) |
| Upload security | WORKING | `test_invalid_mime_rejected`, `test_oversized_upload_rejected`, `test_exif_metadata_stripped` | fake-JPEG/SVG/PDF rejected by magic bytes; size cap 413/422; EXIF Make tag stripped from stored file | SVG uploads deliberately not accepted yet |
| OCR/vision never source truth | WORKING | `test_ocr_text_never_becomes_source_text` | brief confirmed_text stays null until explicit /confirm; generation 409 before confirmation; analysis.detected_text always null | — |
| Deterministic classification | WORKING | `test_reference_classification` | Arabic+English cues → 7 request types incl. نفس الشكل بس غير الكتابة → SAME_STRUCTURE_NEW_TEXT | rule-based only; AI adapter feature-flagged off |
| IP/copy risk flagging | WORKING | `test_branded_reference_flagged_copy_risk` | brand cues → POTENTIAL_COPY_RISK + inspired-alternative notice (no exact-copy promise) | similarity checker vs design library not built |
| Reference → generation hints | WORKING | `test_reference_influences_generation_hints` | vertical reference → plate/frame compositions boosted; transparent score bonus in breakdown | proportions/attachment-point extraction is minimal |
| Anonymous session isolation | WORKING | `test_session_isolation`, `test_version_endpoints_are_session_scoped` | wrong/absent token → 404 on requests AND versions; no existence leak | tokens are per-browser-session; account claim later |
| Rate limiting | WORKING | `test_upload_rate_limit`, `test_generation_rate_limit` | sliding window → 429 | in-process only; Redis for multi-instance later |
| Privacy delete | WORKING | `test_privacy_delete_purges_files` | files removed from storage + rows soft-deleted DELETED | — |
| Repair UX foundation | WORKING | `test_repair_creates_new_version_never_mutates` | repair = NEW version; parent untouched; before/after SVG endpoints | single deterministic fix (thicken); more repair types later |
| Mobile E2E (real stack) | WORKING | `e2e/golden_path_e2e.py` text-flow | ميثة → confirm → 10 proofs → select → approve → locked v1 + hash (390×844 viewport) | download click itself asserted via API-level export tests |
| Reference E2E (real stack) | WORKING | `e2e/golden_path_e2e.py` reference-flow | upload + "نفس الشكل بس غير الكتابة إلى نورة" → confirm نورة → proofs → approve/lock | — |
| Desktop E2E + English | WORKING | `e2e/golden_path_e2e.py` desktop-text-flow | Amal full flow at 1280×800 | — |
| True RTL / bilingual | WORKING | E2E dir assertions + screenshots | documentElement.dir rtl (ar) / ltr (en) toggle | — |
| No fake features | WORKING | UI review | MAKE IT FOR ME rendered disabled "coming soon"; no checkout | — |

## Slice 2 evidence (persistence / approval / lock / export)

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| Alembic migrations | WORKING | `test_migration_cycle` | upgrade head → downgrade base → upgrade head on PostgreSQL 16 | single revision so far |
| Request/candidate persistence | WORKING | `test_request_and_candidates_persist` | ≥30 candidates stored w/ score breakdown, ranking config version, diversity ranks | — |
| Idempotent regeneration | WORKING | `test_candidate_regeneration_is_idempotent` | deterministic candidate keys + unique constraint → no duplicates | — |
| Sequential immutable versions | WORKING | `test_version_numbers_sequential_and_unique` | row-locked allocation; duplicate version_number rejected by DB | — |
| DB-level immutability | WORKING | `test_historical_versions_cannot_be_overwritten`, `test_versions_cannot_be_deleted`, `test_approved_version_is_immutable` | raw-SQL UPDATE/DELETE of version content, status rollback, and approval-hash change all refused by PostgreSQL triggers | — |
| Source text immutable across edits | WORKING | `test_source_text_unchanged_across_geometry_edits`, `test_edit_cannot_touch_source_text_fields` | geometry hash changes, text + sha256 byte-identical; text field not editable | — |
| Customer approval binding | WORKING | `test_approve_exact_version_succeeds_and_locks`, `test_approval_with_wrong_text_or_hash_fails` | NFC-exact text + dual hash verification server-side; approval_hash sha256(version_id\|text_sha\|geom_sha\|ts) | approval identity is a free-text reference (no auth yet) |
| Race-safe lock, no duplicate approvals | WORKING | `test_duplicate_approval_rejected`, `test_racing_approvals_only_one_wins` | 4 concurrent threads → exactly 1 success (conditional UPDATE + unique constraint) | — |
| Edit-after-lock → new UNAPPROVED version | WORKING | `test_edit_after_lock_creates_new_unapproved_version` | historical lock intact; new version blocked from export | — |
| Text change forces approval invalidation | WORKING | `test_text_change_invalidates_approvals` | approval → INVALIDATED + APPROVAL_INVALIDATED event | — |
| Export authorization | WORKING | `test_unapproved_version_export_blocked`, `test_locked_version_exports_svg_dxf_with_records`, `test_export_hash_verification_guard` | 423 unless APPROVED_LOCKED + active approval + hash re-verify at export; tampered geometry refused | — |
| Export records + idempotency | WORKING | `test_export_idempotency_key` | content sha256, mm dims, rules version recorded; duplicate key → replay, cross-format reuse → conflict | — |
| Audit events | WORKING | `test_audit_events_record_lifecycle`, API E2E step 13 | full lifecycle REQUEST_CREATED…PRODUCTION_EXPORT_CREATED; UPDATE/DELETE refused by trigger | — |
| Spec ranking weights | WORKING | `test_request_and_candidates_persist`, E2E step 5 | 30/25/20/10/10/5 persisted per candidate; heuristic dims labelled HEURISTIC / NOT ML-VALIDATED | visual/wearability/originality/customer-fit remain geometric heuristics |
| Font provenance in DB | WORKING | `test_font_references_sync` | font_id + binary sha256 + license recorded, idempotent | — |

## Prior slice evidence (deterministic core)

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| Unicode/NFC + BiDi + HarfBuzz shaping | WORKING | `tests/test_arabic_engine.py` | RTL direction, contextual positional forms, mixed AR/EN runs all asserted | Harakat-specific fixtures not yet in golden set |
| Exact source text preservation | WORKING | `test_arabic_engine.py`, `test_api_golden_path.py` | Identity map covers every codepoint; wrong confirm text → 422; Hamza/Taa Marbuta/Alif Maqsura traced unchanged | — |
| Missing-glyph blocking | WORKING | `test_missing_glyph_fails_verification` | .notdef ⇒ identity unverified ⇒ export blocked | — |
| Font registry + rights gate | WORKING | `test_font_rights_block`, `test_font_registry_endpoint` | 3 OFL fonts seeded w/ licenses vendored; non-commercial statuses block export | Only 3 fonts; no upload/sandbox pipeline |
| Glyph outlines → mm vector geometry | WORKING | `test_generation.py`, smoke evidence | Composite glyphs decomposed; deterministic flattening; real mm sizes | Variable-font named instances unused (defaults only) |
| Parametric candidates ≥30 | WORKING | `test_generation_counts_and_top10` | 40 internal candidates from 10 seed recipes × axes | 10 recipes vs eventual 150+ archetypes; no pgvector retrieval |
| Diverse top 10 | WORKING | `test_top10_geometric_diversity` | min pairwise normalized distance > 0.05; ≥2 fonts, ≥3 compositions in top 10; all 10 golden names fill 10 valid options | — (spec weights live since slice 2) |
| Manufacturing validation | WORKING | `tests/test_validator.py` (13 cases) | Thin stroke, weak bridge, small gap, floating island, disconnect, open path, unsafe loop, oversize all detected on synthetic geometry; invalid candidates blocked with reasons + proposed fixes | Rules are TEST_DEFAULTS, not real Beyond Style workshop profile; no stone/balance/center-of-gravity checks |
| Deterministic generation | WORKING | `test_generation_is_deterministic`, `test_shaping_is_deterministic` | identical ids + WKT across runs | — |
| SVG export (mm, vector-only) | WORKING | `tests/test_exports.py` | mm units, evenodd path, JSON metadata w/ source hash, no raster; dimensions match features | — |
| DXF export (machine-tested) | WORKING | `test_dxf_machine_validity_mm_units` | ezdxf read-back: $INSUNITS=4, closed LWPOLYLINEs, extents match mm dims, custom-var traceability; blocked (423) for failed validation/unconfirmed text | PDF proof export not built |
| API golden path | WORKING | `tests/test_api_golden_path.py` | create→confirm→generate→select→approve→export E2E on PostgreSQL incl. refusal paths | no auth, no rate limits |
| Docker reproducibility | PARTIAL | — | Pinned requirements.txt + Dockerfile (manylinux wheels bundle HarfBuzz/GEOS) | Image not built/run in CI yet |
| Approval + immutable version lock | WORKING | see Slice 2 table | — | — |
| Designer edit versioning (persistence) | WORKING | see Slice 2 table | Copilot UI/UX itself still NOT_STARTED | UI later slice |
| Reference/WhatsApp intake | WORKING | see Slice 3 table | — | WhatsApp channel integration itself is P1 (uploads are the intake path) |
| Frontend (mobile+desktop) | WORKING | see Slice 3 table | browser E2E on mobile + desktop viewports | visual polish; plate-relief proofs render as silhouette (text not visually distinct) |


## Golden Production Memory (Production Learning slice)
| Capability | Status | Evidence | Honest limitation |
|---|---|---|---|
| Real manufactured + customer-approved cases as top-tier memory | WORKING | `tests/test_golden_production_memory.py` (12 tests); 2 real cases seeded idempotently | Only 2 cases; both pre-platform, so neither links to a `DesignVersion` |
| Retrieval by product family / keywords | WORKING | retrieval tests rank the correct real case first for Arabic-letter-earring and layered-name-necklace requests | Deterministic `dna-onehot-1` encoder + bounded keyword bonus, not a learned ranker; pgvector still absent |
| Learning-priority weighting | WORKING | `test_manufactured_approved_memory_outranks_lower_evidence_tiers` | Weights are fixed constants, not fitted from outcomes |
| No geometry cloning | WORKING | `test_retrieval_never_returns_original_geometry`; `golden_case_generation_hints` asserts against every geometry/lineage key | — |
| Source-text truth gate | WORKING | `test_confirmed_names_are_stored_exactly_and_never_inferred`, `test_ocr_can_never_supply_source_text` | Case 1 stays at the pending tier until an order record supplies its Arabic letters |
| Privacy: WhatsApp conversations not persisted | WORKING | `test_personal_conversation_evidence_is_never_stored_or_exported` | Screenshots are hash-registered only; retaining them needs explicit consent |
| Stage comparison (concept vs proof/outline vs product) | PARTIAL | stored per-dimension assessments + aggregate; labelled non-computed | Human visual review, NOT measured from vector geometry — impossible until a case has a `DesignVersion` |
| Real selection lifecycle (who chose what, when) | WORKING | `design_process` + `variant_selection` per case; 3 lifecycle tests | Case 2's selected writing style is inferred from the finished piece, flagged as such |
| Admin view | WORKING | real-uvicorn 403/200 smoke; `/admin/golden-cases` route in the Next.js build | Evidence binaries not uploaded, so the view lists descriptors, not images |

## Known honest limitations
- Deterministic dot/text bridges take the shortest path and can look crude (e.g. a diagonal chord inside a medallion ring) — aesthetic bridge routing is a future refinement; geometry is manufacturable.
- Copilot edits are composition-level parameters; per-glyph move/tail/swash requires the glyph-variant library (later slice).
- Workshop rule values are development defaults, clearly labelled `TEST_DEFAULTS`.
- Ranking uses spec weights, but 4 of 6 dimensions are geometric heuristics labelled HEURISTIC / NOT ML-VALIDATED.
- ~30–45% of internal candidates fail validation by design (thin script joins at small sizes) — blocked, not repaired; deterministic bridging/counter-fill happen at construction time and are tested.
- Approval identity is a free-text reference; authentication/session binding is a later slice.

## Blockers
None for the next slice. P0 overall remains incomplete (see NOT_STARTED rows).
