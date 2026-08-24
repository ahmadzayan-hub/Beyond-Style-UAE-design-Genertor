# Production Readiness

Updated: 2026-08-24 · Slices done: (1) deterministic Golden Path core,
(2) PostgreSQL persistence + versioning + approval lock + audit (ADR-0001)
Test evidence: `cd backend && python3 -m pytest` → **72 passed** (PostgreSQL 16 integration, not SQLite).

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
| Reference/WhatsApp intake | NOT_STARTED | — | — | P0 later slice |
| Frontend (mobile+desktop) | NOT_STARTED | — | — | P0 later slice |

## Known honest limitations
- Workshop rule values are development defaults, clearly labelled `TEST_DEFAULTS`.
- Ranking uses spec weights, but 4 of 6 dimensions are geometric heuristics labelled HEURISTIC / NOT ML-VALIDATED.
- ~30–45% of internal candidates fail validation by design (thin script joins at small sizes) — blocked, not repaired; deterministic bridging/counter-fill happen at construction time and are tested.
- Approval identity is a free-text reference; authentication/session binding is a later slice.

## Blockers
None for the next slice. P0 overall remains incomplete (see NOT_STARTED rows).
