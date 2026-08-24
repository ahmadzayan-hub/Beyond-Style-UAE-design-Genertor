# ADR-0001: Immutable design versioning, customer approval and version lock

Date: 2026-08-24 · Status: Accepted

## Context
CLAUDE.md requires: customer approval creates an immutable
`DesignVersion + hash + timestamp`; any later modification invalidates
approval; workshop export must bind to the exact approved version; source
text must never be silently altered.

## Decision
1. **PostgreSQL is the source of truth.** Entities: `design_requests`,
   `design_candidates`, `designs`, `design_versions`, `customer_approvals`,
   `design_events`, `font_references`, `manufacturing_validation_runs`,
   `exports`. All UUID keyed, UTC timestamps, schema-versioned. Alembic
   owns migrations.
2. **Versions are append-only.** Every edit creates a new
   `design_versions` row (`version_number` sequential per design, enforced
   by `UNIQUE(design_id, version_number)` + row-locked allocation). A
   version stores immutable source text + sha256, geometry WKT +
   `geometry_hash` (sha256 of WKT), and full provenance: schema, Arabic
   engine, font (id + file sha256), recipe (+ library version),
   manufacturing rules version, validation result, `parent_version_id`,
   `created_by`, edit metadata.
3. **DB-level immutability.** A PostgreSQL trigger on `design_versions`
   rejects any UPDATE that touches text/geometry/hash/provenance columns;
   the only permitted transition is `status: UNAPPROVED → APPROVED_LOCKED`
   (plus `updated_at`). A trigger on `customer_approvals` permits only
   `status: ACTIVE → INVALIDATED`. Application bugs cannot overwrite
   history.
4. **Approval binds text to one exact version.** `customer_approvals` has
   `UNIQUE(design_version_id)`. Approval requires, server-verified in one
   transaction: NFC-exact confirmed text match, identity proof PASS,
   manufacturing validation PASS, font rights allow production, and
   client-supplied hashes equal to stored `source_text_sha256` /
   `geometry_hash`. `approval_hash = sha256(version_id | source_sha256 |
   geometry_hash | approved_at)` — never recomputed or recycled. The lock
   itself is `UPDATE … SET status='APPROVED_LOCKED' WHERE id=? AND
   status='UNAPPROVED'` (rowcount 1, else 409) — race-safe.
5. **Edits after lock.** Editing any version creates a NEW `UNAPPROVED`
   version; the historical approval stays attached to its version. An
   intentional source-text change additionally sets every ACTIVE approval
   of the design to `INVALIDATED` and emits `APPROVAL_INVALIDATED`.
6. **Export authorization.** Production SVG/DXF requires: version status
   `APPROVED_LOCKED`, geometry hash re-verified at export time, stored
   validation PASS, font rights PASS. Every production export is recorded
   in `exports` (format, content sha256, mm dimensions, rules version,
   optional `idempotency_key UNIQUE` — duplicate key returns the original
   record). Candidate previews (pre-selection SVG) remain allowed and are
   not production artifacts.
7. **Audit events are append-only but not the primary model.**
   `design_events` records the lifecycle (REQUEST_CREATED …
   PRODUCTION_EXPORT_CREATED) with actor, ids and metadata; relational
   state remains authoritative.

## Consequences
- History is tamper-evident at the database layer, not only by convention.
- Approval can never drift from what the customer saw: hash equality is
  checked at approval AND at export.
- Storage grows per edit (full geometry per version) — acceptable at P0
  scale; delta storage is a later optimization.
- Ranking configuration (spec weights 30/25/20/10/10/5) is versioned and
  stamped onto candidates; heuristic dimensions are explicitly labelled
  HEURISTIC / NOT ML-VALIDATED.
