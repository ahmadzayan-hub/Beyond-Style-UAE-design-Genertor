"""The backend on a Vercel Function: read-only code directory, /tmp only,
capped request bodies, no release phase. Each limitation must be explicit."""
from __future__ import annotations

import importlib

import pytest

from app import platform


def test_server_defaults_unchanged(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert platform.on_vercel() is False
    assert platform.writable_root().name == "var"
    assert platform.cap_body_bytes(8 * 1024 * 1024) == 8 * 1024 * 1024
    assert platform.has_durable_local_disk() is True


def test_vercel_limits(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert platform.on_vercel() is True
    assert str(platform.writable_root()).startswith("/tmp/")
    assert platform.cap_body_bytes(12 * 1024 * 1024) == platform.VERCEL_MAX_BODY_BYTES
    assert platform.VERCEL_MAX_BODY_BYTES < 4_500_000  # below the platform's own cut-off
    assert platform.has_durable_local_disk() is False
    assert platform.info() == {"host": "vercel", "durable_local_disk": False,
                               "max_body_bytes": platform.VERCEL_MAX_BODY_BYTES}


def test_upload_limit_is_capped_on_vercel(monkeypatch):
    import app.security.uploads as uploads

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024))
    try:
        assert importlib.reload(uploads).MAX_UPLOAD_BYTES == platform.VERCEL_MAX_BODY_BYTES
    finally:
        monkeypatch.delenv("VERCEL")
        monkeypatch.delenv("MAX_UPLOAD_BYTES")
        importlib.reload(uploads)


def test_build_sha_from_vercel(monkeypatch):
    from app.build_info import build_sha

    monkeypatch.delenv("BUILD_SHA", raising=False)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "0123456789abcdef0123456789abcdef01234567")
    assert build_sha() == "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("BUILD_SHA", "abcdef1")
    assert build_sha() == "abcdef1"  # explicit override still wins


def test_readiness_refuses_local_storage_on_vercel(monkeypatch, tmp_path):
    from app.readiness import check_storage

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("OBJECT_STORAGE", "local")
    monkeypatch.setenv("PRIVATE_STORAGE_DIR", str(tmp_path))
    out = check_storage()
    assert out["status"] == "error"
    assert out["durability"] == "PROCESS_LOCAL_DISK"
    assert "OBJECT_STORAGE=s3" in out["detail"]


def test_readiness_local_storage_still_ok_on_a_server(monkeypatch, tmp_path):
    from app.readiness import check_storage

    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("OBJECT_STORAGE", "local")
    monkeypatch.setenv("PRIVATE_STORAGE_DIR", str(tmp_path))
    assert check_storage()["status"] == "ok"


@pytest.fixture()
def admin_client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.admin as admin_module
    from app.main import app

    monkeypatch.setattr(admin_module, "ADMIN_API_TOKEN", "test-admin-token-vercel")
    return TestClient(app), {"X-Admin-Token": "test-admin-token-vercel"}


FONT_FORM = {"font_id": "probe-font", "family": "Probe", "license_name": "OFL", "license_text": "x",
             "rights": "VERIFIED_OPEN_SOURCE", "script_family": "arabic", "capability": "PRODUCTION"}


def test_font_registration_refused_without_durable_disk(monkeypatch, admin_client):
    client, headers = admin_client
    monkeypatch.setenv("VERCEL", "1")
    res = client.post("/api/admin/fonts", headers=headers, data=FONT_FORM,
                      files={"file": ("probe.ttf", b"not-a-font", "font/ttf")})
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "READ_ONLY_DEPLOYMENT"


def test_font_upload_over_vercel_body_cap_is_413(monkeypatch, admin_client):
    client, headers = admin_client
    monkeypatch.setenv("VERCEL", "1")
    big = b"0" * (platform.VERCEL_MAX_BODY_BYTES + 1)
    res = client.post("/api/admin/fonts", headers=headers, data={**FONT_FORM, "dry_run": "true"},
                      files={"file": ("probe.ttf", big, "font/ttf")})
    assert res.status_code == 413, res.text


def test_calibration_write_refused_without_durable_disk(monkeypatch, admin_client):
    client, headers = admin_client
    monkeypatch.setenv("VERCEL", "1")
    import app.engines.calibration as calibration

    def must_not_write(*_a, **_k):
        raise AssertionError("profile file must not be written on a read-only host")

    monkeypatch.setattr(calibration, "write_profile", must_not_write)
    monkeypatch.setattr(calibration, "calibrate", lambda profile, manifest, results, operator: {
        "report": {"ok": True}, "promoted": True, "profile": {**profile, "calibration_status": "CALIBRATED"}})
    res = client.post("/api/admin/calibration/apply", headers=headers, json={
        "product": "pendant", "material": "silver-925", "manifest": {}, "results": {}, "operator": "tester", "write": True})
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "READ_ONLY_DEPLOYMENT"
