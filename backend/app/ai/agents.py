"""Hermes-compatible agent orchestration layer.

Claude = reasoning. Hermes = agent operating layer (registry, skills,
delegation, tool policy, budgets, audit). Deterministic engines =
truth. Human = final approval.

Hermes runtime: the `hermes-agent` package (Nous Research, MIT) is
detected at runtime through `HermesRuntimeAdapter`. It is deliberately
NOT installed in the API process — it pins `openai==2.24.0` /
`pydantic==2.13.4`, which conflict with this service's pinned stack — so
it is hosted in the AI worker environment. When absent the in-process
orchestrator runs the same registry/policy/budget contract, so no
business logic depends on the runtime being present.

Hard invariants enforced here, not by any model:
  SOURCE-OF-TRUTH: confirmed source_text > deterministic Arabic engine >
  approved DesignVersion > manufacturing geometry > workshop profile >
  AI recommendation. Levels 1–5 can never be overridden by an LLM.
"""
from __future__ import annotations

import importlib.util
import os
import time
import uuid
from dataclasses import dataclass, field

from .llm import BudgetExceeded, LLMUnavailable, TIER_MODELS, get_provider

HERMES_RUNTIME_ENABLED = os.environ.get("HERMES_RUNTIME", "enabled") == "enabled"
HERMES_PACKAGE = "hermes_agent"

MAX_AGENT_DEPTH = int(os.environ.get("MAX_AGENT_DEPTH", 3))
MAX_AGENT_CALLS_PER_JOB = int(os.environ.get("MAX_AGENT_CALLS_PER_JOB", 12))
MAX_TOOL_CALLS_PER_JOB = int(os.environ.get("MAX_TOOL_CALLS_PER_JOB", 40))
MAX_AI_COST_PER_JOB_USD = float(os.environ.get("MAX_AI_COST_PER_JOB", 1.50))
MAX_AI_COST_PER_SESSION_USD = float(os.environ.get("MAX_AI_COST_PER_SESSION", 5.00))
AGENT_TIMEOUT_S = float(os.environ.get("AGENT_TIMEOUT_S", 90))

#: Read/search tools are separated from production/write actions. Write
#: actions are NEVER allow-listed for agents — they require the
#: deterministic service layer plus human approval.
READ_TOOLS = {
    "retrieve_design_memory",
    "retrieve_reference_dna",
    "load_skill",
    "read_workshop_profile",
    "web_search",
}
WRITE_TOOLS_REQUIRING_HUMAN = {
    "approve_version",
    "production_export",
    "release_order",
    "modify_source_text",
    "change_manufacturing_rule",
}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    tier: str  # llm.TIER_MODELS key
    tools: frozenset[str]
    context_budget_tokens: int
    may_write: bool = False


def _spec(name, role, tier, tools, ctx) -> AgentSpec:
    return AgentSpec(name=name, role=role, tier=tier, tools=frozenset(tools), context_budget_tokens=ctx)


#: Specialist registry. Every agent gets the smallest capable model and a
#: per-agent context budget (progressive context loading).
AGENT_REGISTRY: dict[str, AgentSpec] = {
    a.name: a
    for a in [
        _spec("master_orchestrator", "Routes jobs, coordinates specialists", "fast", ["load_skill"], 2000),
        _spec("customer_brief", "Understands AR/EN requests, WhatsApp intent", "fast", ["load_skill"], 3000),
        _spec("reference_intelligence", "Extracts STYLE-ONLY DesignDNA from references", "primary",
              ["retrieve_reference_dna", "load_skill"], 6000),
        _spec("calligraphy_art_director", "Chooses script/style family", "primary", ["load_skill", "retrieve_design_memory"], 4000),
        _spec("design_concept", "Produces diverse DesignRecipes (never raster)", "primary",
              ["retrieve_design_memory", "load_skill"], 6000),
        _spec("jewellery_engineering", "Maps artistic intent to manufacturable geometry params", "primary",
              ["read_workshop_profile", "load_skill"], 5000),
        _spec("manufacturing_qa", "Reads deterministic validator output, explains failures", "fast",
              ["read_workshop_profile"], 3000),
        _spec("visual_critic", "Scores result vs design intent / reference DNA", "primary",
              ["retrieve_reference_dna"], 5000),
        _spec("diversity", "Checks perceptual/structural difference of top concepts", "fast", [], 2500),
        _spec("design_memory", "Curates approved styles/recipes/outcomes", "fast", ["retrieve_design_memory"], 3000),
        _spec("trend_scout", "Researches trends (inspiration only, never copies)", "primary", ["web_search"], 6000),
        _spec("font_research", "Finds font/calligraphy resources + license metadata", "primary", ["web_search"], 5000),
        _spec("pricing_commercial", "Future: metal/weight/margin logic", "fast", [], 3000),
    ]
}


class ToolNotPermitted(Exception):
    pass


class AgentDepthExceeded(Exception):
    pass


@dataclass
class JobBudget:
    """Per-job guardrails. Exceeding any cap raises — never silently truncates."""

    max_cost_usd: float = MAX_AI_COST_PER_JOB_USD
    max_agent_calls: int = MAX_AGENT_CALLS_PER_JOB
    max_tool_calls: int = MAX_TOOL_CALLS_PER_JOB
    max_depth: int = MAX_AGENT_DEPTH
    spent_usd: float = 0.0
    agent_calls: int = 0
    tool_calls: int = 0

    def charge(self, usd: float) -> None:
        if self.spent_usd + usd > self.max_cost_usd:
            raise BudgetExceeded(
                f"AI cost budget exceeded: {self.spent_usd + usd:.4f} > {self.max_cost_usd} USD"
            )
        self.spent_usd = round(self.spent_usd + usd, 6)

    def count_agent_call(self, depth: int) -> None:
        if depth > self.max_depth:
            raise AgentDepthExceeded(f"max_agent_depth {self.max_depth} exceeded (depth={depth})")
        if self.agent_calls + 1 > self.max_agent_calls:
            raise BudgetExceeded(f"max_agent_calls_per_job {self.max_agent_calls} exceeded")
        self.agent_calls += 1

    def count_tool_call(self) -> None:
        if self.tool_calls + 1 > self.max_tool_calls:
            raise BudgetExceeded(f"max_tool_calls_per_job {self.max_tool_calls} exceeded")
        self.tool_calls += 1


@dataclass
class AuditEntry:
    job_id: str
    agent: str
    action: str
    detail: dict
    depth: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


class HermesRuntimeAdapter:
    """Detects the Hermes agent runtime without importing it into the API."""

    @staticmethod
    def available() -> bool:
        return HERMES_RUNTIME_ENABLED and importlib.util.find_spec(HERMES_PACKAGE) is not None

    @staticmethod
    def status() -> dict:
        installed = importlib.util.find_spec(HERMES_PACKAGE) is not None
        return {
            "runtime_enabled": HERMES_RUNTIME_ENABLED,
            "package": "hermes-agent (Nous Research, MIT)",
            "installed_in_this_process": installed,
            "execution_mode": "hermes" if (HERMES_RUNTIME_ENABLED and installed) else "in_process_orchestrator",
            "note": (
                "hermes-agent pins openai==2.24.0/pydantic==2.13.4; it is hosted in the "
                "AI worker environment, not the API process. The in-process orchestrator "
                "implements the same registry/policy/budget contract."
            ),
        }


class Orchestrator:
    """Runs specialist agents under registry policy, budgets and audit.

    `run_agent` performs ONE structured Claude call for the named agent
    with only the context that agent needs (progressive disclosure). It
    never loops on itself: delegation is explicit and depth-capped.
    """

    def __init__(self, job_id: str | None = None, budget: JobBudget | None = None):
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.budget = budget or JobBudget()
        self.audit: list[AuditEntry] = []

    # ------------------------------------------------------------ policy
    def check_tool(self, agent_name: str, tool: str) -> None:
        spec = AGENT_REGISTRY[agent_name]
        if tool in WRITE_TOOLS_REQUIRING_HUMAN:
            raise ToolNotPermitted(
                f"'{tool}' is a production/write action: human approval required, never agent-invoked"
            )
        if tool not in spec.tools or tool not in READ_TOOLS:
            raise ToolNotPermitted(f"Agent '{agent_name}' may not use tool '{tool}'")
        self.budget.count_tool_call()
        self._log(agent_name, "tool_call", {"tool": tool}, depth=0, cost=0.0)

    def _log(self, agent: str, action: str, detail: dict, depth: int, cost: float) -> None:
        self.audit.append(
            AuditEntry(job_id=self.job_id, agent=agent, action=action, detail=detail,
                       depth=depth, cost_usd=cost)
        )

    # ------------------------------------------------------------- runs
    def run_agent(
        self,
        agent_name: str,
        system: str,
        user_content,
        schema,
        depth: int = 1,
        effort: str = "medium",
        escalate: bool = False,
    ):
        """Execute one specialist agent. Raises LLMUnavailable when no
        Claude credential exists — callers must degrade deterministically."""
        if agent_name not in AGENT_REGISTRY:
            raise KeyError(f"Unknown agent: {agent_name}")
        spec = AGENT_REGISTRY[agent_name]
        self.budget.count_agent_call(depth)
        tier = "escalate" if escalate else spec.tier
        provider = get_provider(tier)
        try:
            parsed, usage = provider.structured(
                system=system, user_content=user_content, schema=schema, effort=effort
            )
        except LLMUnavailable as exc:
            self._log(agent_name, "unavailable", {"reason": exc.reason}, depth, 0.0)
            raise
        self.budget.charge(usage["estimated_cost_usd"])
        self._log(agent_name, "agent_call",
                  {"model": usage["model"], "tier": tier,
                   "input_tokens": usage["input_tokens"],
                   "output_tokens": usage["output_tokens"],
                   "cache_read_input_tokens": usage["cache_read_input_tokens"]},
                  depth, usage["estimated_cost_usd"])
        return parsed, usage

    def audit_log(self) -> list[dict]:
        return [
            {"job_id": e.job_id, "agent": e.agent, "action": e.action, "detail": e.detail,
             "depth": e.depth, "cost_usd": e.cost_usd, "timestamp": e.timestamp}
            for e in self.audit
        ]


def orchestration_status() -> dict:
    from .llm import llm_status

    return {
        "hermes": HermesRuntimeAdapter.status(),
        "claude": llm_status(),
        "agents": {
            name: {"role": s.role, "model": TIER_MODELS[s.tier],
                   "tools": sorted(s.tools), "context_budget_tokens": s.context_budget_tokens}
            for name, s in AGENT_REGISTRY.items()
        },
        "budgets": {
            "max_agent_depth": MAX_AGENT_DEPTH,
            "max_agent_calls_per_job": MAX_AGENT_CALLS_PER_JOB,
            "max_tool_calls_per_job": MAX_TOOL_CALLS_PER_JOB,
            "max_ai_cost_per_job_usd": MAX_AI_COST_PER_JOB_USD,
            "max_ai_cost_per_session_usd": MAX_AI_COST_PER_SESSION_USD,
            "agent_timeout_s": AGENT_TIMEOUT_S,
        },
        "source_of_truth_hierarchy": [
            "confirmed customer source_text",
            "deterministic Arabic identity engine",
            "approved DesignVersion",
            "manufacturing geometry",
            "workshop profile",
            "AI recommendations (lowest)",
        ],
        "write_actions_requiring_human": sorted(WRITE_TOOLS_REQUIRING_HUMAN),
    }
