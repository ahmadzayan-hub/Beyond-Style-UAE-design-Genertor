"""Login-code delivery adapters and the production fail-closed rules.

No request leaves the test: WhatsApp and SMTP are exercised through fake transports, so these
tests prove the request shape and the honest statuses, not that Meta or a relay accepts it.
Live delivery needs the owner's approved provider account and a real test number.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import customer_auth as ca

CODE = "123456"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response or FakeResponse(200, {"messages": [{"id": "wamid.TEST"}]})
        self.error = error
        self.calls: list[dict] = []

    def post(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


class FakeSmtp:
    sent: list = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.tls = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, *, context):
        import ssl

        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        self.tls = True

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        assert self.tls, "message sent before STARTTLS"
        FakeSmtp.sent.append(message)


@pytest.fixture
def whatsapp_env(monkeypatch):
    monkeypatch.setenv("AUTH_CODE_PROVIDER", "whatsapp_cloud")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-token")  # secrets-scan: allow (synthetic)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1000000001")
    monkeypatch.setenv("WHATSAPP_AUTH_TEMPLATE", "login_code")


def test_whatsapp_sends_an_authentication_template_with_the_code(whatsapp_env):
    http = FakeHttp()
    result = ca.deliver_code("phone", "+971501234567", CODE, transport=http)
    assert result == {"status": "SENT", "provider": "whatsapp_cloud", "provider_message_id": "wamid.TEST"}
    call = http.calls[0]
    assert call["url"].endswith("/1000000001/messages")
    assert call["json"]["to"] == "971501234567"
    assert call["json"]["template"]["name"] == "login_code"
    components = call["json"]["template"]["components"]
    assert components[0]["parameters"][0]["text"] == CODE
    assert components[1]["sub_type"] == "url"


@pytest.mark.parametrize(
    "http",
    [
        FakeHttp(response=FakeResponse(400, {"error": {"message": f"bad {CODE}"}})),
        FakeHttp(response=FakeResponse(200, {})),
        FakeHttp(error=TimeoutError("slow")),
    ],
)
def test_whatsapp_failures_are_failed_and_never_echo_the_code(whatsapp_env, http):
    result = ca.deliver_code("phone", "+971501234567", CODE, transport=http)
    assert result["status"] == "FAILED"
    assert CODE not in repr(result)


def test_whatsapp_refuses_email_and_missing_settings(whatsapp_env, monkeypatch):
    assert ca.deliver_code("email", "a@b.ae", CODE, transport=FakeHttp())["status"] == "FAILED"
    monkeypatch.delenv("WHATSAPP_AUTH_TEMPLATE")
    http = FakeHttp()
    assert ca.deliver_code("phone", "+971501234567", CODE, transport=http)["status"] == "FAILED"
    assert http.calls == []


def test_smtp_sends_over_starttls_and_refuses_phone(monkeypatch):
    monkeypatch.setenv("AUTH_CODE_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "login@example.test")
    FakeSmtp.sent = []
    assert ca.deliver_code("email", "maitha@example.test", CODE, smtp_factory=FakeSmtp) == {
        "status": "SENT",
        "provider": "smtp",
    }
    assert FakeSmtp.sent[0]["To"] == "maitha@example.test"
    assert CODE in FakeSmtp.sent[0].get_content()
    assert ca.deliver_code("phone", "+971501234567", CODE, smtp_factory=FakeSmtp)["status"] == "FAILED"


def test_production_ignores_the_dev_echo_flag(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_ECHO_CODE", "1")
    monkeypatch.setenv("APP_ENV", "production")
    assert ca.dev_echo_enabled() is False
    monkeypatch.setenv("APP_ENV", "development")
    assert ca.dev_echo_enabled() is True


def test_production_refuses_the_public_default_pepper(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CONTACT_HASH_PEPPER", raising=False)
    with pytest.raises(ca.IdentityNotConfigured):
        ca.contact_hash("+971501234567")
    monkeypatch.setenv("CONTACT_HASH_PEPPER", ca.DEV_PEPPER)
    with pytest.raises(ca.IdentityNotConfigured):
        ca.contact_hash("+971501234567")
    monkeypatch.setenv("CONTACT_HASH_PEPPER", "a-private-pepper-value")  # secrets-scan: allow (synthetic)
    assert len(ca.contact_hash("+971501234567")) == 64


def test_production_login_without_a_private_pepper_is_503_not_a_stored_weak_hash(clean_tables, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CONTACT_HASH_PEPPER", raising=False)
    monkeypatch.setenv("AUTH_DEV_ECHO_CODE", "1")
    with TestClient(app) as c:
        response = c.post("/api/customers/login/start", json={"contact": "0501234567"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "IDENTITY_NOT_CONFIGURED"


def test_production_login_never_returns_the_code(clean_tables, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CONTACT_HASH_PEPPER", "a-private-pepper-value")  # secrets-scan: allow (synthetic)
    monkeypatch.setenv("AUTH_DEV_ECHO_CODE", "1")
    monkeypatch.delenv("AUTH_CODE_PROVIDER", raising=False)
    with TestClient(app) as c:
        body = c.post("/api/customers/login/start", json={"contact": "0501234567"}).json()
    assert "dev_code" not in body
    assert body["delivery"]["status"] == "SKIPPED_EXTERNAL_PROVIDER"


def test_readiness_marks_production_misconfiguration_as_an_error(monkeypatch):
    from app.readiness import check_customer_auth

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEV_ECHO_CODE", "1")
    monkeypatch.delenv("CONTACT_HASH_PEPPER", raising=False)
    report = check_customer_auth()
    assert report["status"] == "error"
    assert "AUTH_DEV_ECHO_CODE" in report["detail"] and "CONTACT_HASH_PEPPER" in report["detail"]
    assert report["dev_echo_code"] is False

