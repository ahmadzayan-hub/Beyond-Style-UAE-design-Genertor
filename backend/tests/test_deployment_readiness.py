"""Deployment readiness: /health, /ready, /api/ai/status, CORS,
correlation IDs, and structured (never-a-stack-trace) error responses.
Root-causes and regression-guards the "تعذر توليد التصاميم" production
symptom: a request that never reaches a real backend (bad CORS origin,
unset NEXT_PUBLIC_API_URL) is now distinguishable from a real backend
error by the frontend, and every response carries a request_id."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(clean_tables):
    from app.security.sessions import GENERATE_LIMITER, UPLOAD_LIMITER

    UPLOAD_LIMITER.reset()
    GENERATE_LIMITER.reset()
    with TestClient(app) as c:
        yield c


def test_health_is_process_alive_only(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_reports_every_required_component(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    for component in (
        "database", "migrations", "font_registry", "arabic_shaping_engine",
        "geometry_and_manufacturing_engine", "storage", "design_generator",
    ):
        assert body["components"][component]["status"] == "ok", component


def test_ready_never_leaks_secrets(client):
    r = client.get("/ready")
    # Component checks report status/detail-class only, never a DSN,
    # password, or file path — structurally guaranteed by readiness.py.
    text = r.text.lower()
    assert "password" not in text and "postgresql://" not in text and "postgresql+psycopg2" not in text


def test_ai_status_covers_claude_gpt_image_hermes_and_deterministic_fallback(client):
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    body = r.json()
    assert set(("claude", "gpt_image_2", "hermes", "deterministic_fallback")) <= set(body.keys())
    assert body["claude"]["credentials_configured"] is False  # honest, no key in this environment
    assert body["deterministic_fallback"]["status"] == "always_available"
    assert "ANTHROPIC_API_KEY" not in r.text and "OPENAI_API_KEY" not in r.text


def test_cors_allows_configured_origin_only(client, monkeypatch):
    r = client.options(
        "/api/designs",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    r2 = client.options(
        "/api/designs",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r2.headers.get("access-control-allow-origin") != "https://evil.example.com"


def test_cors_never_combines_wildcard_with_credentials():
    from app.main import app as fastapi_app

    for mw in fastapi_app.user_middleware:
        if mw.cls.__name__ == "CORSMiddleware":
            opts = mw.kwargs
            if "*" in (opts.get("allow_origins") or []):
                assert opts.get("allow_credentials") is not True


def test_every_response_carries_a_correlation_request_id(client):
    r = client.get("/health")
    assert r.headers.get("X-Request-ID")

    r2 = client.get("/api/designs/00000000-0000-0000-0000-000000000000")
    assert r2.headers.get("X-Request-ID")
    body = r2.json()
    assert body["request_id"] == r2.headers["X-Request-ID"]


def test_client_supplied_request_id_is_propagated(client):
    r = client.get("/health", headers={"X-Request-ID": "test-correlation-abc123"})
    assert r.headers["X-Request-ID"] == "test-correlation-abc123"


def test_structured_error_codes_never_leak_internal_detail(client):
    # 404 (bad/owned-resource lookup) → SESSION_EXPIRED, no stack trace.
    r = client.get("/api/designs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "SESSION_EXPIRED"
    assert "Traceback" not in r.text and "site-packages" not in r.text


def test_rate_limit_maps_to_rate_limited_code(client):
    design_id, h = _new_session(client)
    for _ in range(5):
        client.post(f"/api/designs/{design_id}/candidates", headers=h)
    r = client.post(f"/api/designs/{design_id}/candidates", headers=h)
    assert r.status_code == 429
    assert r.json()["error_code"] == "RATE_LIMITED"


def test_unhandled_exception_never_exposes_stack_trace(clean_tables, monkeypatch):
    import app.main as main_module

    def _boom(session):
        raise RuntimeError("simulated internal failure with a secret path /var/lib/postgresql/secret")

    monkeypatch.setattr(main_module, "readiness_report", _boom)
    # TestClient re-raises unhandled exceptions by default (test
    # convenience); raise_server_exceptions=False exercises the real
    # ASGI behavior a deployed server has — the registered
    # exception_handler(Exception) converts it to a clean 500.
    with TestClient(app, raise_server_exceptions=False) as no_raise_client:
        r = no_raise_client.get("/ready")
    assert r.status_code == 500
    assert "secret" not in r.text.lower()
    assert r.json()["error_code"] == "BACKEND_UNAVAILABLE"
    assert r.json()["request_id"]


def _new_session(client, text="ميثة"):
    r = client.post("/api/designs", json={"text": text})
    design_id = r.json()["design_id"]
    h = {"X-Session-Token": r.json()["session_token"]}
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": text})
    return design_id, h
