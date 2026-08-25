# ADR-0003: Isolated Hermes runtime + real tool wiring

Date: 2026-08-25 · Status: Accepted

## Context
ADR-0002 shipped an in-process `Orchestrator` that simulates Hermes's
registry/policy/budget contract without installing the real
`hermes-agent` package (it pins `pydantic==2.13.4`/`openai==2.24.0`,
conflicting with this project's `pydantic==2.9.2`/`fastapi==0.115.0`).
`Orchestrator.check_tool` was policy-only — no agent actually executed
a tool. This slice was asked to (1) let Hermes run as a real, separately
deployable runtime without touching the main app's pins, and (2) make
agents execute real tools against existing services, not just pass a
policy check.

## Decision

1. **Isolated Hermes runtime is a separate service with its own pins.**
   `services/hermes/` is a standalone FastAPI app (`Dockerfile` +
   `requirements.txt` pinning `hermes-agent==0.19.0`/
   `pydantic==2.13.4`/`anthropic==1.0.0`) — nothing here is merged into
   `backend/requirements.txt` (enforced by
   `test_main_app_dependency_pins_unaffected_by_hermes`). It exposes
   `GET /health` (honest `hermes_agent_installed`/credentials status,
   never a fabricated result) and `POST /orchestrate/{agent}` (one
   structured Claude call via `output_config.format=json_schema`,
   mirroring `Orchestrator.run_agent`'s contract exactly so the two
   surfaces are interchangeable).

2. **`HERMES_MODE` selects the surface; isolated failure never blocks
   design.** `app/ai/hermes_client.py:HermesClient` resolves
   `in_process` (default, unchanged behavior) / `isolated` / `disabled`.
   In isolated mode, `available()` does a real health check, and
   `run_agent()` tries the isolated call first but falls through to the
   in-process `Orchestrator` on ANY failure — unreachable, timeout,
   non-2xx, bad body — never raising from the isolated attempt itself.
   Tested with a live isolated instance (see Evidence) both reachable
   (SKIPPED_EXTERNAL_MODEL bubbles through, then in-process also
   SKIPPED, both honest) and unreachable (connection refused → clean
   fallback).

3. **Tool execution never leaves the main app process.** Hermes — in
   either mode — only ever *decides* which tool to call; it can propose
   one via the isolated service's (unused-by-default) `tool_client.py`
   callback, but the callback always targets
   `POST /api/orchestration/internal/tools/{tool}` in the main app,
   which is the only process holding a DB session and the deterministic
   engines. That endpoint is closed by default (`INTERNAL_TOOL_TOKEN`
   unset → 403 unconditionally) and, even when open, routes through the
   same `Orchestrator.check_tool` policy gate as any other caller — an
   isolated Hermes deployment cannot acquire more write access than the
   in-process one already has.

4. **9 real tools, one dispatcher, strict schemas.**
   `app/ai/tools.py` wires `analyze_reference`, `retrieve_design_memory`,
   `generate_design_recipes`, `validate_arabic`, `validate_manufacturing`,
   `repair_geometry`, `rank_candidates`, `create_visual_preview` and
   `approve_design` to the exact existing service/engine functions (no
   duplicated business logic). Each has a Pydantic input/output schema;
   `execute_tool()` validates both directions. All nine only ever create
   NEW rows through the services the HTTP API already uses
   (`generate_and_persist_candidates`, `edit_version`,
   `visual_studio.generate_preview`, ...) or are pure reads — never an
   UPDATE to approved/locked data, which stays DB-trigger-protected
   (ADR-0001). `approve_design` is real and directly testable, but is
   registered in `WRITE_TOOLS_REQUIRING_HUMAN`, so
   `Orchestrator.check_tool` refuses it before `execute_tool` is ever
   reached — proven for every agent in the registry, not just one.

5. **Every tool call is durably audited.** `Orchestrator.call_tool` logs
   a `design_events` row (`event_type=TOOL_INVOKED`) with `job_id`,
   `agent`, `tool`, a sha256 `input_hash`, `result_status`
   (`OK`/`ERROR`), `latency_ms` and the DB's own timestamp column — this
   survives process restarts, unlike the pre-existing in-memory
   `Orchestrator.audit`. A failed tool call is still audited (with
   `error`) before the exception propagates as `ToolExecutionError` —
   never silently swallowed.

6. **Per-agent allow-lists, not just a global list.** `AGENT_REGISTRY`
   entries now carry the new tools (e.g. `manufacturing_qa`:
   `validate_manufacturing`, `repair_geometry`; `design_concept`:
   `generate_design_recipes`), and `READ_TOOLS` gates which tool names
   may ever be agent-invoked at all. `check_tool` requires BOTH
   conditions, so an agent cannot reach a tool outside its own list even
   if that tool is globally permitted (tested:
   `test_cross_agent_tool_use_blocked`).

## Consequences
- `backend/requirements.txt` is byte-for-byte unaffected by this slice
  (`anthropic`/`openai` were already added in ADR-0002); `pydantic`
  stays pinned at `2.9.2` (verified at runtime, not just by reading the
  file).
- The isolated container's actual Docker build is UNVERIFIED in this
  environment — no docker daemon available (`docker info` fails to
  reach `/var/run/docker.sock`). The service's application code was
  instead verified directly: run with `uvicorn` in this same Python
  environment (which already has fastapi/pydantic/httpx), exercised
  against `HermesClient` in both isolated-reachable and
  isolated-unreachable configurations. Building/running the actual
  pinned container image, and installing the real `hermes-agent`
  package, remain unverified until a deployment with a docker daemon
  and a `hermes-agent` PyPI resolution runs it.
- Real Claude/GPT-Image-2 calls through either surface remain
  unavailable in this environment (no API keys) — the honest-skip paths
  are exercised; the real-call paths are implemented and gated behind
  `if credentials_available()` branches that will run unmodified once
  keys exist (see `docs/STATUS.md`).
