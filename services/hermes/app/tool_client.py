"""Callback client the isolated Hermes runtime uses to request tool
execution from the main application.

Hermes only ever DECIDES which tool to call; the main app is the sole
process that EXECUTES one (it owns the DB session and the deterministic
Arabic/geometry/manufacturing engines — see app/ai/tools.py in the main
app). This keeps "agent output cannot directly mutate DB/files" true
even when Hermes runs isolated: nothing in this container ever opens a
database connection or writes a file.
"""
from __future__ import annotations

import os

MAIN_APP_URL = os.environ.get("MAIN_APP_URL", "http://localhost:8000")
MAIN_APP_TOOL_TOKEN = os.environ.get("MAIN_APP_TOOL_TOKEN", "")
TOOL_CALL_TIMEOUT_S = float(os.environ.get("HERMES_TOOL_CALL_TIMEOUT", 30))


class ToolCallFailed(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def call_tool(agent_name: str, tool: str, job_id: str, request_id: str | None, **kwargs) -> dict:
    """POST to the main app's internal tool-execution endpoint
    (api/visual.py: POST /api/orchestration/internal/tools/{tool}).
    Requires MAIN_APP_TOOL_TOKEN — the main app rejects any call
    missing/mismatching the shared X-Internal-Tool-Token header, and
    that endpoint is fully closed (returns 403 unconditionally) unless
    a deployment explicitly sets INTERNAL_TOOL_TOKEN, so isolated mode
    never widens the main app's write surface by accident."""
    import httpx

    if not MAIN_APP_TOOL_TOKEN:
        raise ToolCallFailed("MAIN_APP_TOOL_TOKEN not configured — refusing to call an unauthenticated endpoint")
    try:
        resp = httpx.post(
            f"{MAIN_APP_URL}/api/orchestration/internal/tools/{tool}",
            json={"agent_name": agent_name, "job_id": job_id, "request_id": request_id, "input": kwargs},
            headers={"X-Internal-Tool-Token": MAIN_APP_TOOL_TOKEN},
            timeout=TOOL_CALL_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise ToolCallFailed(str(exc)) from exc
