# CLAUDE.md — Beyond Style UAE AI Jewellery Designer

## Purpose
Build a real production platform, not a prototype:
**AI Jewellery Designer + Customer Service/Sales Engine + Designer Copilot + Workshop Manufacturing OS + Trend Intelligence + Continuous Learning.**

Full product specification: `docs/BEYOND_STYLE_MASTER_SPEC.md`.
**Do not read the full spec by default. Read only the section(s) required for the current task.**

## Execution Rule
1. Audit before coding; preserve working code.
2. Implement **P0 only** until its acceptance gates pass.
3. Prefer one complete vertical slice over many partial features.
4. Make small reversible changes.
5. Never fake a feature, API, CAD output, price, test, or production-readiness claim.
6. If blocked by Arabic accuracy, licensing, manufacturing ambiguity, security, or unavailable integration: stop and report.

## Priority
1. Exact text correctness
2. Reference/WhatsApp intake
3. 10 diverse 2D proofs
4. Designer Copilot
5. Manufacturing validity
6. Customer approval/version lock
7. SVG/DXF workshop handoff
8. Customer conversion
9. 3D
10. Automation/learning/scale

## P0 Golden Path
Customer text OR reference/WhatsApp image
→ structured brief
→ exact text confirmation
→ retrieve design knowledge
→ generate ≥30 internal parametric candidates
→ Arabic/Text QA
→ geometry/manufacturing QA
→ diversity ranking
→ show 10 genuinely different 2D proofs
→ customer selects
→ AI/Human Designer refines
→ auto-repair
→ final proof
→ customer confirms spelling/design
→ immutable version lock
→ dimensioned SVG/DXF workshop export.

Must work on mobile + desktop.

## Canonical Architecture
Use one versioned `JewelleryDesignSchema` across all services.

Design Graph:
`SourceText → Characters → Glyphs → Dots/Harakat → Connectors → Composition → Components → Vector Geometry → Manufacturing Geometry → CAD → ProductionVersion`

Multi-component products also use:
`Components → Connectors/Joints → AttachmentPoints → Materials → Process → AssemblyOrder`

`immutableSourceText` is separate from `editableVisualGeometry`.

Raster/image generation is never manufacturing truth.

## Arabic/Text Truth
Arabic accuracy is deterministic P0.
Use Unicode normalization + BiDi + HarfBuzz/OpenType shaping.
AI must never silently alter spelling, order, dots, Hamza, Taa Marbuta, Alif Maqsura, Harakat, names, or phrases.
If identity cannot be verified: `BLOCK_PRODUCTION_EXPORT`.
Transliteration requires explicit confirmation.
Sacred text: no paraphrasing/generative rewriting; enhanced verification + explicit approval.

## Design Intelligence
Use approved/legal fonts + Glyph Variant Library + ≥150 structured archetypes.
Retrieve with metadata + pgvector; never send the whole library to the LLM.
Store Design DNA and Product Construction archetypes.
Do not copy third-party protected artwork.

## Reference / WhatsApp Flow
Core use case: customer sends screenshot/photo and asks “same style/design, change the writing”.
Classify:
- exact-text-replacement
- same-structure-new-text
- style-inspired-redesign
- product-conversion
- material-conversion
- needs-clarification

Vision/OCR is not authoritative for customer text.
Require explicit confirmed source text before production.
Flag copyright/brand risk; create inspired alternatives when copying is unsafe.

## Candidate Generation
AI proposes structured parameters; deterministic engines generate geometry.
Generate ≥30 internally; show exactly 10 diverse valid options.
Default ranking:
Arabic 30%, Manufacturing 25%, Visual 20%, Wearability 10%, Originality 10%, Customer Fit 5%.
Do not show near-duplicate 10 options.

## Manufacturing
Constraint Solver validates:
minimum stroke/gap/bridge, connectivity, stone clearance, attachment points, balance, sharp edges, center of gravity, fit and process limits.
Auto Repair proposes before/after; never silently changes source text.
Use real mm units.
Three.js preview ≠ manufacturing CAD.
CadQuery/OpenCascade or equivalent produces production CAD.

## Approval
Before workshop:
exact source text + final artwork + material/size.
Customer approval creates immutable `DesignVersion + hash + timestamp`.
Any later modification invalidates approval.

## 3D Stage
Only after 2D selection/QA.
Use Three.js/WebGL for customer visualization.
Support material, dimensions, thickness, chain/bail, stones, finish, weight estimate, 360°.
2D Design Graph remains canonical.

## Workshop OS
State machine:
`New → Design Review → Technical Check → Approved → Manufacturing → QC → Rework? → Ready → Delivered`
Do not skip required states.
Production Pack includes approved hash, exact text, dimensions, material, process, BOM, tolerances, warnings, score, SVG/DXF/PDF and CAD where applicable.
Delivery completion requires:
- Receiver Name
- Staff Number
- Actual Received Date

## Memory / Learning
PostgreSQL = source of truth.
pgvector = semantic retrieval.
Redis = session/cache.
Object Storage = images/SVG/CAD.
Immutable events/audit = operational history.

Memory layers:
Session, Customer Preference(opt-in), Design Knowledge, Manufacturing, Episodic/Audit, Evaluation, Trend.

Production data must not directly self-modify rules.
Learning:
`Observe → Candidate → Offline Eval → Golden Dataset → Safety/MFG Tests → Approval → Versioned Promotion → Monitor → Rollback`

## AI Control Plane
Version and trace:
Agent, Model, Prompt, Tools, Design-KB, Arabic Engine, Manufacturing Rules, Evaluations.
Support routing, permissions, budgets, feature flags and rollback.
Deterministic rules override AI for text truth, licensing, pricing math, manufacturing hard limits and security.
Implemented as: Hermes-compatible orchestration (in-process adapter, or an
OPTIONAL isolated runtime in `services/hermes/` with its own dependency
pins, reached over HTTP with automatic fallback to in-process — never a
hard dependency) + Claude (fast/primary/escalate tiered routing, 9 real
tools wired to existing services, human-only write tools always blocked)
+ GPT-Image-2 (visualization only, never manufacturing truth) — see
`docs/adr/0002-hermes-claude-gpt-image2-orchestration.md` and
`docs/adr/0003-isolated-hermes-runtime-and-tool-wiring.md`.
No credentials in this environment: report `SKIPPED_EXTERNAL_MODEL` /
`PHOTOREAL_PREVIEW_UNAVAILABLE`, never a fabricated result.

## Trend Agents
One shared research gateway; specialized agents consume normalized evidence.
Cover Global, UAE/GCC, Women, Men, Kids/Teens, Gifts, Accessories, Materials/Manufacturing, Competition, IP/Evidence, Merchandising.
Social media = weak signal only.
Trend loop:
`Discover → Verify → Rights → Score → MFG Check → UAE Fit → Commercial Eval → Human Approval → Prototype → Test → Learn`

## Privacy / Security
Private by default.
No shared-model training on customer designs/photos without explicit opt-in.
RBAC, MFA-ready admin, CSP, rate limits, signed URLs, MIME validation, malware scan, SVG sanitization, font sandbox, secrets, audit logs, backups/restore, RPO/RTO, provider fallback, timeouts, circuit breakers, AI budgets.

## Token-Efficiency Protocol
- Do not restate this file or the master spec in responses.
- Read only files needed for the current task.
- Use `rg`/targeted search before opening files.
- Open only relevant ranges/functions, not entire large files.
- Do not re-read unchanged files already inspected.
- Before changes touching >3 files: list planned files + reason, then execute.
- Prefer targeted tests during iteration; run full suites only at phase gates.
- Summarize tool output; do not paste large logs unless failure evidence is needed.
- Do not explore P1/P2 code while implementing P0 unless required by dependency.
- Update `docs/production-readiness.md` instead of repeating long status in chat.
- End each task with max 10 lines: changed / tests / evidence / blockers / next action.

## Recommended Claude Code Session Commands
At the start of a new independent task:
`/clear`

Check what is consuming context:
`/context`

For a long continuing task:
`/compact focus on current task, decisions, changed files, failing tests, blockers and next step; omit discarded exploration and verbose logs`

Inspect usage when available:
`/cost`

Choose the lightest capable model:
`/model`

For planning-heavy work, if available:
`/model opusplan`

For a side question that should not pollute the main task, if available:
`/btw`

Use `/help` to confirm commands supported by the installed Claude Code version.

## Low-Token Prompt Templates

### Audit
`Read CLAUDE.md. Audit only the files relevant to P0 Golden Path. Do not code. Return: existing/reusable/gaps/risks + max 12-file implementation plan. Do not restate the spec.`

### Implement one slice
`Read CLAUDE.md. Implement only: <SLICE>. Inspect the minimum files required. Preserve working code. Run targeted tests. Update production-readiness.md. Reply in <=10 lines.`

### Fix
`Fix only <BUG>. Find root cause with targeted search. No unrelated refactor. Add regression test. Reply with changed files + test result only.`

### Continue
`Continue the current P0 slice from repo state. Read production-readiness.md and git diff first; avoid re-reading unchanged files. Complete the smallest missing step and test it.`

### Review
`Review only the diff for <SLICE> against CLAUDE.md acceptance rules. Report P0 blockers first. Do not rewrite code unless a blocker is confirmed.`

### Compact checkpoint
`Before compaction, write durable decisions/evidence to docs/production-readiness.md or ADR. Then /compact with focus on current P0 slice only.`

## P0 Acceptance
P0 is not complete unless evidence proves:
- exact Arabic/English source text preserved
- correct RTL/contextual shaping
- reference “change writing” flow works
- top 10 are meaningfully diverse
- unsafe geometry blocked
- valid dimensioned SVG/DXF in mm
- designer edits versioned
- customer approval/hash lock works
- mobile + desktop Golden Path works
- no fake buttons/data
- recovery paths exist
- tests pass and evidence is recorded

## Definition of Done
Maintain:
- `docs/architecture.md`
- `docs/implementation-plan.md`
- `docs/production-readiness.md`
- `docs/adr/`

Run as applicable:
lint, typecheck, unit, integration, E2E, Arabic regression, font, SVG/DXF, geometry, manufacturing, security, performance/build.

Never claim 100% from compilation alone.
