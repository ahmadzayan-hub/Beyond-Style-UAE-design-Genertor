# STATUS

Statuses: VERIFIED (automated tests + evidence) / PARTIAL / FALLBACK / DISABLED / UNAVAILABLE / NOT_IMPLEMENTED.
Updated: 2026-08-25 · Backend suite: 174 passed (PostgreSQL 16) · E2E: 4 browser flows passed.

## Hermes + Claude + GPT-Image-2 orchestration (this slice, see ADR-0002)
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

## Visual Reference Intelligence (this slice) — honest AI status
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
1. Calibrate workshop profiles with real Beyond Style workshop values.
2. Push branch → observe CI green on GitHub.
3. Reference Intelligence P0.5 / Hermes+Claude+GPT-Image-2: needs real `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` credentials (and a pin-conflict decision for the real `hermes-agent` package) before any live-model behavior can be claimed VERIFIED — stop-condition: cannot be built honestly without them.
