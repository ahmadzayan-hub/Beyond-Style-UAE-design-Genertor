# Production Readiness

Updated: 2026-08-24 · Slice: P0 backend Golden Path (deterministic core)
Test evidence: `cd backend && python3 -m pytest` → **51 passed** (see suites below).

| Feature | Status | Test | Evidence | Gap |
|---|---|---|---|---|
| Unicode/NFC + BiDi + HarfBuzz shaping | WORKING | `tests/test_arabic_engine.py` | RTL direction, contextual positional forms, mixed AR/EN runs all asserted | Harakat-specific fixtures not yet in golden set |
| Exact source text preservation | WORKING | `test_arabic_engine.py`, `test_api_golden_path.py` | Identity map covers every codepoint; wrong confirm text → 422; Hamza/Taa Marbuta/Alif Maqsura traced unchanged | Approval/version-lock (hash freeze of final artwork) not yet built |
| Missing-glyph blocking | WORKING | `test_missing_glyph_fails_verification` | .notdef ⇒ identity unverified ⇒ export blocked | — |
| Font registry + rights gate | WORKING | `test_font_rights_block`, `test_font_registry_endpoint` | 3 OFL fonts seeded w/ licenses vendored; non-commercial statuses block export | Only 3 fonts; no upload/sandbox pipeline |
| Glyph outlines → mm vector geometry | WORKING | `test_generation.py`, smoke evidence | Composite glyphs decomposed; deterministic flattening; real mm sizes | Variable-font named instances unused (defaults only) |
| Parametric candidates ≥30 | WORKING | `test_generation_counts_and_top10` | 40 internal candidates from 10 seed recipes × axes | 10 recipes vs eventual 150+ archetypes; no pgvector retrieval |
| Diverse top 10 | WORKING | `test_top10_geometric_diversity` | min pairwise normalized distance > 0.05; ≥2 fonts, ≥3 compositions in top 10; all 10 golden names fill 10 valid options | Ranking weights are TEST heuristic, not spec's 30/25/20/10/10/5 model |
| Manufacturing validation | WORKING | `tests/test_validator.py` (13 cases) | Thin stroke, weak bridge, small gap, floating island, disconnect, open path, unsafe loop, oversize all detected on synthetic geometry; invalid candidates blocked with reasons + proposed fixes | Rules are TEST_DEFAULTS, not real Beyond Style workshop profile; no stone/balance/center-of-gravity checks |
| Deterministic generation | WORKING | `test_generation_is_deterministic`, `test_shaping_is_deterministic` | identical ids + WKT across runs | — |
| SVG export (mm, vector-only) | WORKING | `tests/test_exports.py` | mm units, evenodd path, JSON metadata w/ source hash, no raster; dimensions match features | — |
| DXF export (machine-tested) | WORKING | `test_dxf_machine_validity_mm_units` | ezdxf read-back: $INSUNITS=4, closed LWPOLYLINEs, extents match mm dims, custom-var traceability; blocked (423) for failed validation/unconfirmed text | PDF proof export not built |
| API golden path | WORKING | `tests/test_api_golden_path.py` | create→confirm→generate→SVG/DXF E2E incl. refusal paths | In-memory store only — no PostgreSQL, no auth, no rate limits |
| Docker reproducibility | PARTIAL | — | Pinned requirements.txt + Dockerfile (manylinux wheels bundle HarfBuzz/GEOS) | Image not built/run in CI yet |
| Approval + immutable version lock | NOT_STARTED | — | — | next slice |
| Designer copilot / edits versioning | NOT_STARTED | — | — | P0 later slice |
| Reference/WhatsApp intake | NOT_STARTED | — | — | P0 later slice |
| Frontend (mobile+desktop) | NOT_STARTED | — | — | P0 later slice |

## Known honest limitations
- Workshop rule values are development defaults, clearly labelled `TEST_DEFAULTS`.
- Candidate ranking is a placeholder heuristic; spec weighting model comes with the ranking slice.
- ~30–45% of internal candidates fail validation by design (thin script joins at small sizes) — blocked, not repaired; deterministic bridging/counter-fill happen at construction time and are tested.
- No persistence: designs vanish on restart (in-memory slice store).

## Blockers
None for the next slice. P0 overall remains incomplete (see NOT_STARTED rows).
