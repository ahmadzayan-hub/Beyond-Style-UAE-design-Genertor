"""Claude LLM provider + cost-aware model routing.

Claude is the primary reasoning intelligence. It NEVER owns Arabic
spelling, glyph geometry, manufacturing limits or exports — see the
source-of-truth hierarchy in `app/ai/agents.py`.

Routing (configurable, no business logic depends on one vendor):
  FAST      → claude-haiku-4-5   (classification, cheap extraction)
  PRIMARY   → claude-sonnet-5    (design reasoning, DesignDNA, critique)
  ESCALATE  → claude-opus-5      (hard/ambiguous cases only)

No key / SDK absent ⇒ LLMUnavailable. Nothing is ever fabricated.
"""
from __future__ import annotations

import importlib.util
import os
import time
from typing import Any, Type

from pydantic import BaseModel

FAST_MODEL = os.environ.get("FAST_LOW_COST_MODEL", "claude-haiku-4-5")
PRIMARY_MODEL = os.environ.get("PRIMARY_REASONING_MODEL", "claude-sonnet-5")
ESCALATION_MODEL = os.environ.get("EXPERT_ESCALATION_MODEL", "claude-opus-5")

#: USD per 1M tokens (input, output) — used for budget estimates only.
MODEL_PRICING = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}

TIER_MODELS = {"fast": FAST_MODEL, "primary": PRIMARY_MODEL, "escalate": ESCALATION_MODEL}

#: Models where `thinking` / `output_config.effort` are supported.
_ADAPTIVE_THINKING = {"claude-sonnet-5", "claude-opus-5", "claude-fable-5"}


class LLMUnavailable(Exception):
    """No usable LLM credential/SDK. Callers must degrade deterministically."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"LLM_UNAVAILABLE: {reason}")


class BudgetExceeded(Exception):
    pass


def sdk_available() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def credentials_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = MODEL_PRICING.get(model, (2.0, 10.0))
    return round(in_tokens_cost(input_tokens, in_rate) + in_tokens_cost(output_tokens, out_rate), 6)


def in_tokens_cost(tokens: int, rate_per_mtok: float) -> float:
    return tokens / 1_000_000 * rate_per_mtok


class ClaudeProvider:
    """Thin, budget-aware wrapper over the official Anthropic SDK."""

    def __init__(self, tier: str = "primary"):
        if tier not in TIER_MODELS:
            raise ValueError(f"Unknown model tier: {tier}")
        self.tier = tier
        self.model = TIER_MODELS[tier]
        self._client = None

    # ------------------------------------------------------------ health
    def _guard(self) -> None:
        if not sdk_available():
            raise LLMUnavailable("anthropic SDK not installed (pip install anthropic)")
        if not credentials_available():
            raise LLMUnavailable("no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN configured")

    def health(self) -> dict:
        try:
            self._guard()
            status = "ready"
        except LLMUnavailable as exc:
            status = f"unavailable: {exc.reason}"
        return {"tier": self.tier, "model": self.model, "status": status,
                "pricing_usd_per_mtok": MODEL_PRICING.get(self.model)}

    def _client_or_raise(self):
        self._guard()
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                timeout=float(os.environ.get("LLM_TIMEOUT_S", 120)),
                max_retries=int(os.environ.get("LLM_MAX_RETRIES", 2)),
            )
        return self._client

    # ------------------------------------------------------------ calls
    def _request_kwargs(self, effort: str) -> dict:
        kwargs: dict[str, Any] = {}
        if self.model in _ADAPTIVE_THINKING:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": effort}
        return kwargs

    def structured(
        self,
        system: str,
        user_content: Any,
        schema: Type[BaseModel],
        effort: str = "medium",
        max_tokens: int = 4096,
        cache_system: bool = True,
    ) -> tuple[BaseModel, dict]:
        """One structured Claude call validated against a Pydantic schema.

        `system` is a stable, cached prefix (progressive context loading:
        keep it small, put volatile task data in `user_content`).
        Returns (parsed_model, usage_dict).
        """
        client = self._client_or_raise()
        system_block = [{"type": "text", "text": system}]
        if cache_system:
            system_block[0]["cache_control"] = {"type": "ephemeral"}
        kwargs = self._request_kwargs(effort)
        start = time.monotonic()
        response = client.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system_block,
            messages=[{"role": "user", "content": user_content}],
            output_format=schema,
            **kwargs,
        )
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        usage = {
            "model": self.model,
            "response_id": getattr(response, "id", None),
            "latency_ms": latency_ms,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
            "estimated_cost_usd": estimate_cost_usd(
                self.model, response.usage.input_tokens, response.usage.output_tokens
            ),
        }
        return response.parsed_output, usage


def get_provider(tier: str = "primary") -> ClaudeProvider:
    return ClaudeProvider(tier)


def llm_status() -> dict:
    return {
        "vendor": "anthropic",
        "routing": {t: TIER_MODELS[t] for t in TIER_MODELS},
        "sdk_installed": sdk_available(),
        "credentials_configured": credentials_available(),
        "tiers": {t: ClaudeProvider(t).health() for t in TIER_MODELS},
        "note": "LLM proposes; deterministic engines own Arabic/geometry/manufacturing truth",
    }
