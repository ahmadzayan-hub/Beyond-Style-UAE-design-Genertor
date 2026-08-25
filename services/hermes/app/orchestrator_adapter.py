"""Orchestrator adapter for the isolated Hermes runtime.

Detects the real `hermes-agent` package (installed here — this
container's own venv, unconstrained by the main API's pins) and
performs ONE structured Claude call per request, exactly mirroring the
main app's `Orchestrator.run_agent` contract (app/ai/agents.py) so the
two surfaces are interchangeable from the caller's point of view.

Same honesty rule as the rest of this project: no ANTHROPIC_API_KEY (or
SDK missing) → a clean SKIPPED_EXTERNAL_MODEL response, never a fake
result. Any other failure is reported as ERROR with the real reason,
never swallowed silently.
"""
from __future__ import annotations

import importlib.util
import os

HERMES_PACKAGE = "hermes_agent"

FAST_MODEL = os.environ.get("FAST_LOW_COST_MODEL", "claude-haiku-4-5")
PRIMARY_MODEL = os.environ.get("PRIMARY_REASONING_MODEL", "claude-sonnet-5")
ESCALATION_MODEL = os.environ.get("EXPERT_ESCALATION_MODEL", "claude-opus-5")
TIER_MODELS = {"fast": FAST_MODEL, "primary": PRIMARY_MODEL, "escalate": ESCALATION_MODEL}

MODEL_PRICING = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}


def hermes_agent_installed() -> bool:
    return importlib.util.find_spec(HERMES_PACKAGE) is not None


def hermes_agent_version() -> str | None:
    if not hermes_agent_installed():
        return None
    try:
        import hermes_agent

        return getattr(hermes_agent, "__version__", "unknown")
    except Exception:  # noqa: BLE001 — version probing must never crash health
        return "unknown"


def anthropic_credentials_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def health() -> dict:
    return {
        "status": "ok",
        "hermes_agent_installed": hermes_agent_installed(),
        "hermes_agent_version": hermes_agent_version(),
        "anthropic_sdk_installed": importlib.util.find_spec("anthropic") is not None,
        "anthropic_credentials_configured": anthropic_credentials_available(),
        "routing": TIER_MODELS,
        "note": "reasoning/orchestration proxy only — never mutates the main app's DB/files",
    }


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = MODEL_PRICING.get(model, (2.0, 10.0))
    return round(input_tokens / 1_000_000 * in_rate + output_tokens / 1_000_000 * out_rate, 6)


def run_structured(agent_name: str, system: str, user_content, json_schema: dict, tier: str = "primary") -> dict:
    """One structured Claude call constrained by a raw JSON Schema
    (output_config.format) rather than a local Pydantic type, since the
    schema arrives over the wire from the caller. Returns a dict:
    {"status": "OK", "result": {...}, "usage": {...}}
    {"status": "SKIPPED_EXTERNAL_MODEL", "reason": "..."}
    {"status": "ERROR", "reason": "..."}
    """
    if not importlib.util.find_spec("anthropic"):
        return {"status": "SKIPPED_EXTERNAL_MODEL", "reason": "anthropic SDK not installed"}
    if not anthropic_credentials_available():
        return {"status": "SKIPPED_EXTERNAL_MODEL", "reason": "no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN configured"}

    model = TIER_MODELS.get(tier, PRIMARY_MODEL)
    try:
        import anthropic

        client = anthropic.Anthropic(timeout=float(os.environ.get("LLM_TIMEOUT_S", 120)))
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        import json as _json

        result = _json.loads(text)
        usage = {
            "model": model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "estimated_cost_usd": _estimate_cost(model, response.usage.input_tokens, response.usage.output_tokens),
        }
        return {"status": "OK", "result": result, "usage": usage}
    except Exception as exc:  # noqa: BLE001 — never crash the request; report the real reason
        return {"status": "ERROR", "reason": f"{agent_name}: {exc}"}
