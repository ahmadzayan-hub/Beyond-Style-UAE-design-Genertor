# Architecture — current implemented state

Scope: P0 backend Golden Path slice (deterministic core). Frontend, DB
persistence, approval/lock, 3D, pricing are NOT implemented yet.

## Pipeline (all deterministic, no AI dependency)

```
text → NFC normalization → BiDi run segmentation → HarfBuzz shaping
     → glyph identity map (cluster → codepoint indices)   [arabic_engine]
     → glyph outline extraction (fontTools, decomposed,
       fixed-step curve flattening)                        [outline_extractor]
     → parametric construction in mm: scale/spacing/stroke
       delta → composition (bar/plate/frame) → deterministic
       dot bridging → sub-gap counter fill → loops         [geometry_engine]
     → manufacturing validation vs WorkshopRules           [validator]
     → deterministic recipe expansion ≥30 → feature vectors
       → greedy max-min diverse top 10                     [generator]
     → SVG (mm, metadata) / DXF (INSUNITS=4, custom vars)  [exporters]
```

## Modules (backend/app)

| Module | Responsibility |
|---|---|
| `config.py` | `WorkshopRules` (TEST_DEFAULTS profile, all mm, kerf-aware effective limits); schema/generator versions |
| `schemas/jewellery_design.py` | Versioned canonical schema: `ImmutableSourceText` (frozen, sha256) separate from all geometry; `GlyphIdentity`, `TextIdentityProof`, `ValidationReport` + `ProposedFix`, `RecipeParams`, `DesignCandidate`, `JewelleryDesign` |
| `fonts/registry.py` + `fonts.json` | Font rights registry. Seeded with 3 SIL-OFL fonts (Amiri, Cairo, Scheherazade New; binaries + OFL texts vendored — OFL permits redistribution). Rights gate: non-commercial statuses block production export |
| `engines/arabic_engine.py` | Normalization, paragraph direction, directional run segmentation, uharfbuzz shaping, identity verification (full codepoint coverage + zero .notdef) |
| `engines/outline_extractor.py` | Glyph id → closed contours (font units); composite decomposition; open-path detection (reported, never guessed closed) |
| `engines/geometry_engine.py` | Shapely mm geometry; even-odd contour combination; parametric transforms; compositions: bare/baseline_bar/underline_bar/plate_oval/plate_rect/frame_circle; deterministic `bridge_components`; `fill_small_holes` (sub-cuttable counters left solid — standard practice); attachment loops |
| `engines/validator.py` | Erosion/dilation checks: thin stroke, weak bridge, small gap, floating island/disconnect, open path, unsafe loop, oversize; plus text-identity and font-rights gates. Fixes proposed, never auto-applied |
| `engines/generator.py` | Seed library (10 recipes, `data/design_recipes.json`) × fixed variation axes → 40 internal candidates; documented TEST ranking heuristic; greedy max-min diversity top-10 |
| `exporters/svg_exporter.py` | mm width/height + viewBox, evenodd single path, JSON metadata (ids, source text + hash, versions), no raster |
| `exporters/dxf_exporter.py` | R2010, `$INSUNITS=4`, closed LWPOLYLINE on CUT/HOLES layers, custom header vars for traceability; raises `ProductionExportBlocked` on failed validation or unconfirmed text |
| `api/designs.py` + `main.py` | FastAPI: create → confirm exact text → generate → validation/SVG/DXF per candidate; fonts registry endpoint. In-memory store (slice only) |

## Key invariants enforced in code + tests

1. `ImmutableSourceText` is frozen; confirmation requires byte-exact NFC match; every candidate and export carries `source_text_sha256`.
2. Identity proof = every codepoint index covered by shaped clusters, zero `.notdef`; failure ⇒ `TEXT_IDENTITY_UNVERIFIED` ⇒ production export blocked.
3. Same input ⇒ identical candidate ids and geometry WKT (no randomness anywhere; fixed curve sampling and buffer resolutions).
4. DXF export refuses unvalidated candidates and unconfirmed text (HTTP 423 / `ProductionExportBlocked`).
5. Fonts are lettering sources, not products; rights status gates production; UNKNOWN_RIGHTS never exports commercially.

## Deferred (later slices)
PostgreSQL persistence + pgvector retrieval, approval/version lock,
designer copilot edits, reference/WhatsApp intake, auto-repair application
UI, frontend, Redis, S3, Docker Compose orchestration, CI.
