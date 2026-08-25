"""HermesClient — the main API process's front door to Hermes.

Hermes now has two possible execution surfaces:
  in_process → the existing, fully-tested `Orchestrator` (app/ai/agents.py).
  isolated   → the OPTIONAL separate runtime in services/hermes/, reached
               over typed HTTP/JSON. It may use its own dependency pins
               (real `hermes-agent`, newer pydantic/openai) without
               touching this process's requirements.txt.
  disabled   → orchestration/agent reasoning is skipped entirely.

HERMES_MODE selects the surface (default in_process — unchanged
behavior from the previous slice). In isolated mode, ANY failure
talking to the isolated runtime (unreachable, timeout, non-2xx, bad
body) transparently falls back to the in-process Orchestrator — the
isolated runtime's availability can never block deterministic
jewellery design (CLAUDE.md AI Control Plane).

Tool EXECUTION always happens in this process (app/ai/tools.py) even in
isolated mode: the isolated runtime is a reasoning/orchestration proxy
only, never a DB/file-mutating actor — see the module docstring there.
"""
from __future__ import annotations

import os

HERMES_MODE = os.environ.get("HERMES_MODE", "in_process").lower()
HERMES_URL = os.environ.get("HERMES_URL", "http://localhost:8100")
HERMES_TIMEOUT_S = float(os.environ.get("HERMES_TIMEOUT", 10))

VALID_MODES = {"isolated", "in_process", "disabled"}


class HermesUnavailable(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"HERMES_UNAVAILABLE: {reason}")


def _mode() -> str:
    return HERMES_MODE if HERMES_MODE in VALID_MODES else "in_process"


def isolated_health() -> dict:
    """Best-effort health check against the isolated runtime container.
    Never raises — a connection failure is a normal, expected outcome
    when the optional service isn't deployed."""
    import httpx

    try:
        resp = httpx.get(f"{HERMES_URL}/health", timeout=HERMES_TIMEOUT_S)
        resp.raise_for_status()
        return {"reachable": True, **resp.json()}
    except Exception as exc:  # noqa: BLE001 — any failure just means "unreachable"
        return {"reachable": False, "error": str(exc)}


def hermes_client_status() -> dict:
    mode = _mode()
    status = {
        "mode": mode,
        "url": HERMES_URL if mode == "isolated" else None,
        "timeout_s": HERMES_TIMEOUT_S,
        "fallback": "in_process_orchestrator",
    }
    if mode == "isolated":
        status["isolated_health"] = isolated_health()
    return status


class HermesClient:
    """Use this instead of `Orchestrator` directly from application code —
    it resolves HERMES_MODE and guarantees the deterministic pipeline is
    never blocked by the optional isolated runtime being down."""

    def __init__(self, job_id: str | None = None, budget=None):
        from .agents import (
            HERMES_MAX_AGENT_DEPTH,
            HERMES_MAX_COST_PER_JOB,
            HERMES_MAX_TOOL_CALLS,
            JobBudget,
            Orchestrator,
        )

        self.mode = _mode()
        self.budget = budget or JobBudget(
            max_depth=HERMES_MAX_AGENT_DEPTH,
            max_tool_calls=HERMES_MAX_TOOL_CALLS,
            max_cost_usd=HERMES_MAX_COST_PER_JOB,
        )
        self._orchestrator = Orchestrator(job_id=job_id, budget=self.budget)
        self.used_isolated = False

    @property
    def job_id(self) -> str:
        return self._orchestrator.job_id

    def available(self) -> bool:
        if self.mode == "disabled":
            return False
        if self.mode == "isolated":
            return isolated_health().get("reachable", False)
        return True  # in_process orchestrator is always structurally available

    # ------------------------------------------------------------ reasoning
    def run_agent(self, agent_name: str, system: str, user_content, schema, **kwargs):
        """Same contract as Orchestrator.run_agent — one structured
        Claude call for the named agent. Tries the isolated runtime
        first in isolated mode; ANY failure falls back to in-process
        rather than raising, per the "never block deterministic design"
        rule. Raises LLMUnavailable only when the fallback itself has
        no usable credentials (honest — never fabricated)."""
        if self.mode == "disabled":
            from .llm import LLMUnavailable

            raise LLMUnavailable("HERMES_MODE=disabled")
        if self.mode == "isolated":
            try:
                return self._run_agent_isolated(agent_name, system, user_content, schema, **kwargs)
            except Exception:
                pass  # isolated runtime unavailable/erroring → fall through, never block
        return self._orchestrator.run_agent(agent_name, system, user_content, schema, **kwargs)

    def _run_agent_isolated(self, agent_name, system, user_content, schema, **kwargs):
        import httpx

        resp = httpx.post(
            f"{HERMES_URL}/orchestrate/{agent_name}",
            json={
                "system": system,
                "user_content": user_content,
                "schema": schema.model_json_schema(),
                **kwargs,
            },
            timeout=HERMES_TIMEOUT_S,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "OK":
            raise HermesUnavailable(body.get("reason", "isolated runtime returned non-OK"))
        self.used_isolated = True
        return schema(**body["result"]), body["usage"]

    # ---------------------------------------------------------------- tools
    def call_tool(self, agent_name: str, tool: str, session, **kwargs) -> dict:
        """Tool execution ALWAYS runs in this process — it owns the DB
        session and the deterministic engines. The isolated runtime, if
        used, only ever proposes tool calls (MCP-style); it never
        executes them. See app/ai/tools.py."""
        return self._orchestrator.call_tool(agent_name, tool, session, **kwargs)

    def audit_log(self) -> list[dict]:
        return self._orchestrator.audit_log()
