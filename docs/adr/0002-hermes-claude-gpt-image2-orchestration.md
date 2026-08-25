# ADR-0002: Hermes orchestration, Claude reasoning, GPT-Image-2 visualization

Date: 2026-08-25 · Status: Accepted

## Context
CLAUDE.md's AI Control Plane requires versioned/traced Agent, Model, Prompt,
Tools, and a documented rule that deterministic engines override AI for text
truth, licensing, pricing math, manufacturing hard limits and security. The
architecture-update and P0.6 requests ask for: Hermes Agent (Nous Research)
as the orchestration/runtime layer, Claude as the base reasoning model,
GPT-Image-2 as a pure visualization engine, and a final quality layer (Design
Jury, confidence engine, taste memory, lineage, product skills, shadow
evaluation) — all without weakening ADR-0001's immutability guarantees or
making a GPU/local model a P0 blocker.

## Decision

1. **Source-of-truth hierarchy is code, not convention.**
   `app/ai/agents.py:orchestration_status()` publishes an ordered list: (1)
   confirmed customer `source_text`, (2) the deterministic Arabic identity
   engine, (3) an approved `DesignVersion`, (4) manufacturing geometry, (5)
   the workshop profile, (6) AI recommendations. No LLM call anywhere in
   `app/ai/*` can write `design_versions.immutable_source_text`, geometry, or
   manufacturing fields — those columns remain DB-trigger-protected per
   ADR-0001. AI output is advisory (`JuryScore`, `ConfidenceReport`, visual
   previews) or governed by an explicit human-only write tool.

2. **Hermes is a detection-adapter, not an in-process dependency.**
   `hermes-agent` (PyPI) pins `pydantic==2.13.4` / `openai==2.24.0`,
   incompatible with this project's pinned `pydantic==2.9.2`/
   `fastapi==0.115.0`. Rather than force a pin conflict or fake an
   integration, `HermesRuntimeAdapter.status()` detects the package via
   `importlib.util.find_spec` and reports `execution_mode: "hermes"` when
   present or `"in_process_orchestrator"` otherwise. The in-process
   `Orchestrator` class implements the identical contract (13-agent
   registry, tool allow-listing, budgets, audit log) so business logic never
   branches on which runtime is active. GPU/local models are explicitly not
   a P0 blocker — this mirrors the same pattern already used for the
   Qwen/FLUX local providers.

3. **Claude model routing is tiered and env-overridable.**
   `app/ai/llm.py`'s `ClaudeProvider` maps `fast → claude-haiku-4-5`,
   `primary → claude-sonnet-5`, `escalate → claude-opus-5`
   (`FAST_LOW_COST_MODEL` / `PRIMARY_REASONING_MODEL` /
   `EXPERT_ESCALATION_MODEL` env vars override). Every call goes through
   `.structured()` (Anthropic SDK `messages.parse`, Pydantic schema,
   `cache_control: ephemeral` on the system block). No credentials → raises
   `LLMUnavailable`; callers must surface `SKIPPED_EXTERNAL_MODEL`, never a
   fabricated verdict — see the `/api/visual/versions/{id}/jury` endpoint,
   which always returns HTTP 200 with a `status` field.

4. **GPT-Image-2 renders only after canonical geometry is approved-path
   validated; it can never become manufacturing truth.**
   `app/services/visual_studio.py:generate_preview()` always rasterizes the
   *canonical* vector geometry first (`render_canonical_png`), builds a
   machine-readable `VisualBrief` (`app/ai/visual_brief.py`), and sends that
   PNG as the primary reference with an explicit `PRESERVATION_RULE` string
   plus `NEGATIVE_CONSTRAINTS`. Every generation is passed through the
   Visual Identity Guard (`app/ai/preview_guard.py`: alpha-aware,
   bbox-normalized occupancy-grid IoU) with bounded retries
   (`MAX_PREVIEW_RETRIES=2`) before a final `PASS` / `REVIEW_REQUIRED` /
   `REJECTED_GEOMETRY_DRIFT` status. `design_service.export_version()`
   rejects any format other than `svg`/`dxf` — AI raster output is never
   exportable as a manufacturing file, enforced by the same function that
   already re-verifies the approval hash (ADR-0001 §6).

5. **Cost/budget/cache discipline lives in the same call path as the guard.**
   `generate_preview()` checks a cache hit (identical `VisualBrief` +
   `geometry_hash` → same generation row, no new spend) *before* the
   provider-availability guard, then checks session cost/image-count budgets
   *after* availability but *before* any paid call. `JobBudget` in
   `app/ai/agents.py` enforces `max_cost_usd` / `max_agent_calls` /
   `max_tool_calls` / `max_depth` for orchestration; photoreal generation is
   restricted to the customer's *selected* candidate, never all 10 — Top-10
   exploration stays SVG-only per the explicit instruction not to generate
   photoreal for every candidate.

6. **The quality layer is scoring/retrieval on existing data, not a new
   authority.** Design Jury (`app/ai/quality_layer.py`) is one structured
   Claude call standing in for four critic roles, weighted 0.3/0.3/0.25/0.15,
   advisory only. `ConfidenceReport` is a pure deterministic function (no
   model call) over already-computed signals (`identity_verified`,
   `validation_passed`, preview-guard divergence, IP risk) with
   `CONFIDENCE_THRESHOLD=0.7` forcing `requires_human_review`. Taste memory
   reuses the existing `DesignEvent` audit table (`CUSTOMER_FEEDBACK` event
   type) rather than a new mutable preference row, keeping it append-only
   and opt-in. Lineage assembly (`design_lineage()`) is a read-only join
   across existing tables — no new edges are created that could orphan an
   asset. Shadow evaluation runs a candidate model *silently* alongside
   production and only ever *recommends* promotion
   (`recommend_promotion: bool`); nothing auto-switches the production
   model.

7. **Product skills are progressive-disclosure data, not new agents.**
   `app/ai/product_skills.py` maps 8 product types to their existing
   workshop profile keys (`config.get_profile()`), so routing to a product
   skill never introduces a manufacturing rule the geometry engine doesn't
   already enforce.

## Consequences
- No new column or trigger changes ADR-0001's immutability guarantees;
  `AIGeneration` is a new, independent table (raster artifacts + guard
  reports), never referenced by `design_versions`.
- Every AI-touching code path in this slice has a tested "no credentials /
  no SDK" branch that returns an honest status rather than raising an
  opaque 500 or fabricating a result (`tests/test_hermes_claude_visual.py`,
  `tests/test_quality_layer.py`).
- `anthropic==1.0.0` and `openai==3.3.1` are thin HTTP SDKs added to
  `backend/requirements.txt` (main API process); they are unrelated to
  `backend/requirements-ai.txt`'s GPU stack for the local Qwen/FLUX worker.
- Real end-to-end Claude/GPT-Image-2 calls remain UNAVAILABLE in this
  environment (no API keys configured) — routing, guards, budgets, and
  fallback paths are proven; live-model behavior is not, and must not be
  claimed as verified until credentials exist and a real call is observed.
