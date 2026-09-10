"""Licensed font upload → immediate activation (spec §4 C/D/F/G)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import admin
from app.fonts import onboarding
from app.main import app

ASSETS = Path(__file__).resolve().parents[1] / "app" / "assets" / "fonts"
KATIBEH = ASSETS / "Katibeh-Regular.ttf"


@pytest.fixture
def private_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVATE_FONTS_DIR", str(tmp_path / "private_fonts"))
    monkeypatch.setattr(admin, "ADMIN_API_TOKEN", "admin-secret")
    onboarding.reset_registry_caches()
    yield tmp_path / "private_fonts"
    onboarding.reset_registry_caches()


def _form(**over):
    base = {"font_id": "foundry-diwani-test", "family": "Foundry Diwani (test)", "license_name": "Foundry EULA",
            "license_text": "EULA: desktop + product license; outlines in physical goods permitted.",
            "source_url": "https://foundry.example", "rights": "COMMERCIAL_LICENSED", "script_family": "diwani",
            "capability": "DIWANI", "tags": "diwani,classic", "owner": "beyond-style"}
    base.update(over)
    return base


def test_upload_activates_a_locked_style_immediately(private_dir):
    from app.fonts.capabilities import production_capability_map
    from app.fonts.styles import style_catalogue

    assert production_capability_map()["DIWANI"] == "LICENSE_REQUIRED"
    with TestClient(app) as c:
        h = {"X-Admin-Token": "admin-secret"}
        assert c.post("/api/admin/fonts", data=_form(), files={"file": ("x.ttf", KATIBEH.read_bytes())}).status_code == 403
        r = c.post("/api/admin/fonts", data=_form(), files={"file": ("Foundry.ttf", KATIBEH.read_bytes())}, headers=h)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["registered"] and body["production_use"] and body["capability_map"]["DIWANI"] == "REAL"
        assert body["shaping"]["ok"] and body["binary"]["contextual_forms"]
    assert (private_dir / "foundry-diwani-test.ttf").exists() and (private_dir / "foundry-diwani-test-LICENSE.txt").exists()
    overlay = json.loads((private_dir / "uploaded_fonts.json").read_text())
    assert overlay["fonts"][0]["rights_status"] == "COMMERCIAL_LICENSED" and overlay["fonts"][0]["upstream_distribution"] == "UPLOAD"
    cards = {s["id"]: s for s in style_catalogue()}
    assert cards["diwani"]["status"] == "AVAILABLE" and cards["diwani"]["fonts"][0]["font_id"] == "foundry-diwani-test"
    with TestClient(app) as c:
        rows = c.get("/api/fonts/registry").json()["fonts"]
        row = next(r for r in rows if r["font_id"] == "foundry-diwani-test")
        assert row["production_use"] and row["shaping_status"] == "VERIFIED" and row["hash_sha256"]


def test_unknown_rights_never_reach_production(private_dir):
    from app.fonts.capabilities import production_capability_map

    with TestClient(app) as c:
        h = {"X-Admin-Token": "admin-secret"}
        r = c.post("/api/admin/fonts", data=_form(font_id="mystery-diwani", rights="UNKNOWN_RIGHTS"),
                   files={"file": ("m.ttf", KATIBEH.read_bytes())}, headers=h)
        assert r.status_code == 201 and r.json()["production_use"] is False
    assert production_capability_map()["DIWANI"] == "LICENSE_REQUIRED"   # recorded, not activated


def test_license_evidence_is_mandatory_and_woff2_is_unpacked(private_dir):
    from fontTools.ttLib import TTFont

    with TestClient(app) as c:
        h = {"X-Admin-Token": "admin-secret"}
        r = c.post("/api/admin/fonts", data=_form(license_text=""), files={"file": ("x.ttf", KATIBEH.read_bytes())}, headers=h)
        assert r.status_code == 422 and "license" in r.text.lower()
        tt = TTFont(str(KATIBEH)); tt.flavor = "woff2"; buf = io.BytesIO(); tt.save(buf)
        r = c.post("/api/admin/fonts", data={**_form(font_id="woff2-test"), "dry_run": "true"},
                   files={"file": ("Katibeh.woff2", buf.getvalue())}, headers=h)
        assert r.status_code == 200 and r.json()["dry_run"] and r.json()["usable"]
        assert r.json()["binary"]["contextual_forms"] and not r.json()["binary"]["embedding_restricted"]
        r = c.post("/api/admin/fonts", data=_form(font_id="bad-id!", ), files={"file": ("x.ttf", b"nope")}, headers=h)
        assert r.status_code == 422
