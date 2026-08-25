"""External AI acceptance harness (`make external-ai-e2e` →
scripts/external_ai_acceptance.py). Proves every check reports an
honest status — never a fake PASS — and that the deterministic Golden
Path survives with Claude, GPT-Image-2 and Hermes-isolated all
unavailable."""
from __future__ import annotations

import json
import pathlib

from scripts import external_ai_acceptance as eaa


def test_claude_check_skips_honestly_without_credentials(clean_tables, db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    result = eaa.check_claude(db_session)
    assert result["status"] == "SKIPPED_NO_CREDENTIALS"
    assert "reason" in result


def test_gpt_image_check_skips_honestly_without_credentials(clean_tables, db_session, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = eaa.check_gpt_image(db_session)
    assert result["status"] == "SKIPPED_NO_CREDENTIALS"
    assert "reason" in result


def test_hermes_check_optional_not_running_by_default(clean_tables, db_session):
    result = eaa.check_hermes(db_session)
    assert result["status"] == "OPTIONAL_NOT_RUNNING"


def test_hermes_check_optional_when_isolated_but_unreachable(clean_tables, db_session, monkeypatch):
    monkeypatch.setattr(eaa, "HERMES_MODE", "isolated")
    # isolated_health() is a plain-imported function bound to
    # app.ai.hermes_client's own HERMES_URL global, so patch its return
    # value directly rather than eaa.HERMES_URL (which it never reads).
    monkeypatch.setattr(eaa, "isolated_health", lambda: {"reachable": False, "error": "connection refused"})
    result = eaa.check_hermes(db_session)
    assert result["status"] == "OPTIONAL_NOT_RUNNING"  # never FAILED just for being absent


def test_agent_tool_chain_stops_before_approve_design(clean_tables, db_session):
    result = eaa.run_agent_tool_chain(db_session)
    assert result["status"] == "VERIFIED_LOCAL"
    tool_names = [s["tool"] for s in result["steps"]]
    assert tool_names[-1] == "approve_design"
    assert result["steps"][-1]["status"] == "BLOCKED_HUMAN_ONLY"
    assert {"analyze_reference", "retrieve_design_memory", "generate_design_recipes",
            "validate_arabic", "rank_candidates", "validate_manufacturing"} <= set(tool_names)
    assert result["candidate_count"] >= 30


def test_provider_failure_deterministic_path_still_completes(clean_tables, db_session):
    """Point 8: Claude/GPT-Image/Hermes-isolated all unavailable — the
    text → 10 concepts → select → manufacturing validation →
    approval/export path must still work."""
    result = eaa.check_deterministic_path_survives_all_providers_down(db_session)
    assert result["status"] == "VERIFIED_LOCAL"
    assert result["evidence"]["version_status"] == "APPROVED_LOCKED"
    assert result["evidence"]["approval_status"] == "ACTIVE"
    assert result["evidence"]["export_format"] == "dxf"
    assert result["evidence"]["export_sha256"]


def test_evidence_never_contains_secrets_or_raw_payload():
    usage = {"model": "claude-sonnet-5", "response_id": "msg_123", "latency_ms": 42.0,
              "input_tokens": 10, "output_tokens": 5, "estimated_cost_usd": 0.0001,
              "api_key": "sk-ant-SECRET-TEST-VALUE", "prompt": "leaked raw text",
              "raw_response": "should never be here"}
    redacted = eaa._redact_usage(usage)
    assert set(redacted) <= set(eaa.USAGE_EVIDENCE_KEYS)
    assert "api_key" not in redacted and "prompt" not in redacted and "raw_response" not in redacted
    assert "sk-ant-SECRET-TEST-VALUE" not in json.dumps(redacted)


def test_makefile_target_exists_and_points_at_script():
    makefile = pathlib.Path(__file__).resolve().parents[2] / "Makefile"
    text = makefile.read_text()
    assert "external-ai-e2e:" in text
    assert "scripts/external_ai_acceptance.py" in text


def test_main_writes_honest_evidence_and_exits_zero_without_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(eaa, "EVIDENCE_PATH", tmp_path / "evidence.json")
    rc = eaa.main()
    assert rc == 0  # SKIPPED_NO_CREDENTIALS / OPTIONAL_NOT_RUNNING are not acceptance failures
    body = json.loads((tmp_path / "evidence.json").read_text())
    assert body["claude"]["status"] == "SKIPPED_NO_CREDENTIALS"
    assert body["gpt_image"]["status"] == "SKIPPED_NO_CREDENTIALS"
    assert body["hermes"]["status"] in ("OPTIONAL_NOT_RUNNING", "VERIFIED_EXTERNAL")
    assert body["agent_tool_chain"]["status"] == "VERIFIED_LOCAL"
    assert body["provider_failure_deterministic_path"]["status"] == "VERIFIED_LOCAL"
    # No API key value anywhere in the written evidence file.
    raw = (tmp_path / "evidence.json").read_text()
    assert "sk-" not in raw
