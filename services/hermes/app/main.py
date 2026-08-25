"""Isolated Hermes runtime — a small, independently-deployable FastAPI
service. Optional: the main application (backend/) falls back to its
own in-process Orchestrator whenever this service is unreachable (see
app/ai/hermes_client.py) — nothing here is a hard dependency of the
deterministic jewellery-design pipeline.

Endpoints:
  GET  /health                      — honest hermes-agent/anthropic status
  POST /orchestrate/{agent_name}    — ONE structured Claude call, same
                                       contract as the main app's
                                       Orchestrator.run_agent
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import orchestrator_adapter

app = FastAPI(title="Beyond Style — Isolated Hermes Runtime")


@app.get("/health")
def health():
    return orchestrator_adapter.health()


class OrchestrateRequest(BaseModel):
    system: str
    user_content: object
    json_schema: dict = Field(..., alias="schema")
    tier: str = "primary"

    class Config:
        populate_by_name = True


@app.post("/orchestrate/{agent_name}")
def orchestrate(agent_name: str, body: OrchestrateRequest):
    return orchestrator_adapter.run_structured(
        agent_name, body.system, body.user_content, body.json_schema, tier=body.tier
    )
