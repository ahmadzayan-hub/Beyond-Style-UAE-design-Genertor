"""Workshop calibration through the admin API: coupon → real results → pinned
profile version; nothing promoted without clean results for every class."""
from __future__ import annotations

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import admin

H = {"X-Admin-Token": "admin-secret"}


@pytest.fixture(autouse=True)
def _admin_token(monkeypatch):
    monkeypatch.setattr(admin, "ADMIN_API_TOKEN", "admin-secret")


def test_coupon_apply_and_pin_profile(tmp_path, monkeypatch):
    from app.engines import calibration as cal

    src = cal.profiles_path()
    work = tmp_path / "workshop_profiles.json"
    shutil.copy(src, work)
    monkeypatch.setenv("WORKSHOP_PROFILES_PATH", str(work))
    with TestClient(app) as c:
        assert c.post("/api/admin/calibration/coupon").status_code == 403
        kit = c.post("/api/admin/calibration/coupon", headers=H).json()
        assert kit["svg"].startswith("<svg") and "LWPOLYLINE" in kit["dxf"] and kit["coupon_sha256"]
        feats = kit["manifest"]["features"]
        # incomplete results (no clean gap) → report, not promotable, write refused
        partial = {"clean": [f for f, v in feats.items() if v["class"] == "stroke" and v["nominal_mm"] >= 0.5]}
        r = c.post("/api/admin/calibration/apply", json={"manifest": kit["manifest"], "results": partial, "operator": "Workshop A"}, headers=H)
        assert r.status_code == 200 and r.json()["promoted"] is False and r.json()["calibration_status"] == "CALIBRATION_INCOMPLETE"
        assert r.json()["report"]["stroke"]["status"] == "MEASURED" and r.json()["report"]["gap"]["status"] == "UNRESOLVED"
        w = c.post("/api/admin/calibration/apply", json={"manifest": kit["manifest"], "results": partial, "operator": "Workshop A", "write": True}, headers=H)
        assert w.status_code == 422 and w.json()["detail"]["code"] == "CALIBRATION_INCOMPLETE"
        # complete results: every class has a clean feature → pinned with provenance
        full = {"clean": [f for f, v in feats.items() if v["nominal_mm"] >= {"stroke": 0.5, "gap": 0.4, "bridge": 0.6, "counter": 0.5, "engrave_line": 0.2}[v["class"]]]}
        w = c.post("/api/admin/calibration/apply", json={"manifest": kit["manifest"], "results": full, "operator": "Workshop A", "write": True}, headers=H)
        assert w.status_code == 200, w.text
        body = w.json()
        assert body["promoted"] and body["calibration_status"].startswith("WORKSHOP_CALIBRATED_")
        assert body["written"]["profiles_version"] == "wp-1.1.0" and "restart" in body["note"].lower()
        data = json.loads(work.read_text())
        pinned = next(p for p in data["profiles"] if p["profile_name"] == "pendant/silver-925")
        assert pinned["is_production_profile"] is True and pinned["calibration"]["operator"] == "Workshop A"
        assert pinned["min_stroke_mm"] == round(0.5 * 1.15, 2)   # smallest clean × safety margin
        # the repository file was NOT touched
        assert json.loads(src.read_text())["profiles_version"] == "wp-1.0.0"
        listing = c.get("/api/admin/calibration/profiles", headers=H).json()
        assert listing["profiles_version"] == "wp-1.1.0"
        assert next(p for p in listing["profiles"] if p["profile_name"] == "pendant/silver-925")["is_production_profile"] is True


def test_unknown_feature_ids_are_rejected(monkeypatch, tmp_path):
    from app.engines import calibration as cal

    work = tmp_path / "wp.json"; shutil.copy(cal.profiles_path(), work)
    monkeypatch.setenv("WORKSHOP_PROFILES_PATH", str(work))
    with TestClient(app) as c:
        kit = c.post("/api/admin/calibration/coupon", headers=H).json()
        r = c.post("/api/admin/calibration/apply", json={"manifest": kit["manifest"], "results": {"clean": ["stroke-99"]}, "operator": "Op A"}, headers=H)
        assert r.status_code == 422 and "stroke-99" in r.json()["detail"]
