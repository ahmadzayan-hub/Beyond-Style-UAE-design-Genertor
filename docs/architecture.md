# Architecture — current implemented state

Scope: P0 backend Golden Path (deterministic core) + PostgreSQL
persistence / versioning / approval-lock / audit + reference intake +
mobile-first customer UI. 3D, pricing, orders are NOT implemented yet.

## Reference intake + customer UI (slice 3)

Intake (`app/services/intake_service.py`, `app/api/intake.py`):
`reference_assets` (private, sha256, provenance, ip_risk, honest
PENDING_SCAN status) + `customer_briefs` (deterministic rule-based
classification: EXACT_TEXT_REPLACEMENT / SAME_STRUCTURE_NEW_TEXT /
STYLE_INSPIRED_REDESIGN / PRODUCT_CONVERSION / MATERIAL_CONVERSION /
TEXT_ONLY_DESIGN / NEEDS_CLARIFICATION; optional AI analyzer is
feature-flagged and suggestion-only). OCR/vision text can never become
immutable source text — only explicit customer confirmation sets it.
Reference analysis → generation hints (composition/recipe boosts,
transparent score bonus) — never bypasses the schema or validation.

Security (`app/security/`): magic-byte MIME verification (JPEG/PNG/WebP
whitelist), size cap, EXIF strip via re-encode, non-guessable keys in
LocalPrivateStorage (S3-shaped interface; owner-token access only, no
public URLs), malware-scan adapter with honest PENDING_SCAN fallback,
sliding-window rate limits on upload/generation, anonymous session
tokens (sha256 stored; wrong token → 404, no existence leak) scoping
every request/version endpoint, privacy delete that purges files.

Frontend (`frontend/`, Next.js 14 + Tailwind, 93KB first load): one
mobile-first golden-path flow — start (text or reference upload +
message + style intent) → exact-text confirmation → generating →
10 proofs (progressive SVG) → selected (+ deterministic repair
before/after creating a NEW version) → approval statement + lock →
authorized SVG/DXF download; true RTL Arabic default with LTR English
toggle; MAKE IT FOR ME shown disabled (not faked). Domain logic stays
in the backend; the UI only orchestrates the API.

## Quality gate (slice 4)

`engines/similarity.py`: 32×32 occupancy-grid IoU (deterministic,
comparison-only) gates Top-10 selection — no two selections above 0.86.
`engines/quality.py`: 7-dimension quality report, heuristic dimensions
explicitly labelled. `exporters/svg_exporter.export_proof_svg`: relief
compositions render base + differentiated text layer, faithful to the
canonical mm geometry; production exports stay single-silhouette.
`data/design_recipes.json` v0.2: 32 curated archetypes with Design DNA
(family, purpose, products, text-length fit, constraints, rights).
Long-text (>8 letters) gets a deterministic stroke/size adaptation.
Golden visual regression fixture: `tests/golden/golden_visual.json`.
Copilot: frontend panel (sliders/selects, undo/redo over immutable
versions) driving the existing `/edit` endpoint — every accepted edit is
a new DesignVersion.

## Persistence layer (see ADR-0001)

PostgreSQL (SQLAlchemy 2 + Alembic) is the source of truth. Entities:
`design_requests`, `design_candidates`, `designs`, `design_versions`
(append-only, DB-trigger-enforced immutability; only legal transition
UNAPPROVED→APPROVED_LOCKED), `customer_approvals` (unique per version,
hash-frozen, ACTIVE→INVALIDATED only), `design_events` (append-only
audit), `font_references` (font binary sha256 provenance),
`manufacturing_validation_runs`, `exports` (production export records
with content sha256, mm dims, unique idempotency keys).

Lifecycle service (`app/services/design_service.py`):
request → confirm exact text → generate/persist candidates (idempotent,
deterministic keys) → select (Design + version 1) → designer edits (new
versions; visual recipe fields only — source text untouchable) →
intentional text change (new version + forced APPROVAL_INVALIDATED) →
customer approval (server verifies NFC-exact text, identity PASS,
manufacturing PASS, rights PASS, both hashes; race-safe conditional
UPDATE lock) → authorized production export (re-verifies hashes at
export time; 423 BLOCK_PRODUCTION_EXPORT otherwise).

Ranking (`app/engines/ranking.py`): configurable spec weights
Arabic 30 / Manufacturing 25 / Visual 20 / Wearability 10 /
Originality 10 / CustomerFit 5, version-stamped onto every candidate;
visual/wearability/originality/customer-fit are labelled
HEURISTIC / NOT ML-VALIDATED in each stored score breakdown.

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
| `api/designs.py` + `api/intake.py` + `api/auth.py` + `main.py` | FastAPI over PostgreSQL: full lifecycle + intake + repair endpoints, all request/version routes session-token scoped |

## Key invariants enforced in code + tests

1. `ImmutableSourceText` is frozen; confirmation requires byte-exact NFC match; every candidate and export carries `source_text_sha256`.
2. Identity proof = every codepoint index covered by shaped clusters, zero `.notdef`; failure ⇒ `TEXT_IDENTITY_UNVERIFIED` ⇒ production export blocked.
3. Same input ⇒ identical candidate ids and geometry WKT (no randomness anywhere; fixed curve sampling and buffer resolutions).
4. DXF export refuses unvalidated candidates and unconfirmed text (HTTP 423 / `ProductionExportBlocked`).
5. Fonts are lettering sources, not products; rights status gates production; UNKNOWN_RIGHTS never exports commercially.

## AI orchestration: Hermes + Claude + GPT-Image-2 (slice 5 — see ADR-0002)

Deterministic engines above remain sole source of truth; this layer is
advisory/visualization only (`orchestration_status()` publishes the
6-level source-of-truth hierarchy) and cannot write
`design_versions.immutable_source_text`, geometry, or manufacturing
fields — those stay DB-trigger-protected per ADR-0001.

| Module | Responsibility |
|---|---|
| `ai/llm.py` | `ClaudeProvider` (tiered fast/primary/escalate routing, env-overridable model ids, structured `.parse()` calls, cost estimation); raises `LLMUnavailable` honestly with no credentials |
| `ai/agents.py` | 13-agent Hermes-compatible registry, tool allow-listing (`READ_TOOLS` vs human-only write tools), `JobBudget` (cost/depth/call caps), audit log, `HermesRuntimeAdapter` (detects the real `hermes-agent` package vs in-process fallback) |
| `ai/visual_brief.py` | Machine-readable, cacheable `VisualBrief`; `VisualPromptBuilder` — single centralized prompt assembly with explicit preservation-rule + negative-constraint text |
| `ai/image_providers.py` | `OpenAIImage2Provider` (generate/edit + semantic preview wrappers); disabled by default, guarded by `OPENAI_IMAGE_ENABLED` + API key |
| `services/visual_studio.py` | Renders canonical geometry to PNG, builds the brief, calls the provider, runs the identity guard with bounded retries, enforces session cost/image-count budgets before any paid call, caches identical requests |
| `ai/preview_guard.py` | Alpha-aware, bbox-normalized occupancy-grid IoU between canonical geometry and AI raster → PASS / REVIEW_REQUIRED / REJECTED_GEOMETRY_DRIFT |
| `ai/quality_layer.py` | Design Jury (one structured Claude call, 4 weighted scores), deterministic `ConfidenceReport`, opt-in taste-memory signals (reuses `design_events`), read-only design lineage assembly, shadow-model evaluation (advisory promotion recommendation only) |
| `ai/product_skills.py` | 8-product progressive-disclosure skill registry mapped to existing workshop profiles |
| `api/visual.py` | `/api/visual/*` + `/api/orchestration/status` — every failure mode returns an honest status (`PHOTOREAL_PREVIEW_UNAVAILABLE`, `SKIPPED_EXTERNAL_MODEL`, `BUDGET_*`), never a fabricated result; deterministic SVG/DXF path is unaffected |

Real Claude/GPT-Image-2 calls are UNAVAILABLE in this environment (no API
keys) — routing, budgets, guards and fallbacks are proven; live-model
behavior is not yet observed.

## Deferred (later slices)
pgvector retrieval over a grown archetype library, designer copilot
editor UI, WhatsApp channel integration, real malware scanner + S3,
Redis-backed rate limits, accounts/design claiming, CI pipeline,
3D preview, pricing/orders (P1). Hermes runtime package installation (an
approved-pin decision needed first), live Claude/GPT-Image-2 credentials,
tool-execution wiring from `Orchestrator.run_agent` into
`reference_intelligence.py`/`design_memory.py` services.
