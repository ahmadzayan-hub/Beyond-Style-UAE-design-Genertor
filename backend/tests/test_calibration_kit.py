"""Workshop calibration kit: graded coupon + measured-limit derivation."""
import json
from datetime import date

import pytest

from app.config import load_workshop_profiles
from app.engines.calibration import GRADES, RULE_FIELD, SAFETY_MARGIN, build_coupon, calibrate


def _profile():
    return next(p for p in load_workshop_profiles()["profiles"] if p["profile_name"] == "pendant/silver-925")


def test_coupon_grades_straddle_every_industry_typical_limit():
    p = _profile()
    for cls, field in RULE_FIELD.items():
        sizes = GRADES[cls]
        assert min(sizes) < p[field] <= max(sizes), f"{cls} grades must bracket {field}={p[field]}"


def test_coupon_geometry_and_manifest_agree():
    kit = build_coupon(_profile())
    feats = kit["manifest"]["features"]
    assert len(feats) == sum(len(g) for g in GRADES.values())
    assert kit["cut"].geom_type == "MultiPolygon" and not kit["cut"].is_empty
    assert kit["engrave"].geom_type == "MultiPolygon" and len(kit["engrave"].geoms) > len(feats)
    # Every counter hole really is a hole in the plate of the stated size.
    plate = kit["cut"]
    holes = [r for poly in plate.geoms for r in poly.interiors]
    assert len(holes) >= len(GRADES["counter"]) + len(GRADES["gap"])


def test_calibration_derives_limits_from_smallest_clean_feature():
    p = _profile(); kit = build_coupon(p)
    results = {"clean": ["stroke-3", "stroke-4", "stroke-5", "gap-4", "gap-5", "bridge-3", "bridge-4",
                         "counter-2", "counter-3", "engrave_line-3", "engrave_line-4"]}
    out = calibrate(p, kit["manifest"], results, operator="tester", when=date(2026, 8, 29))
    assert out["promoted"] is True
    prof = out["profile"]
    assert prof["calibration_status"] == "WORKSHOP_CALIBRATED_2026-08-29"
    assert prof["is_production_profile"] is True
    assert prof["min_stroke_mm"] == round(GRADES["stroke"][2] * (1 + SAFETY_MARGIN), 2)
    assert prof["min_gap_mm"] == round(GRADES["gap"][3] * (1 + SAFETY_MARGIN), 2)
    assert prof["min_counter_mm"] == round(GRADES["counter"][1] * (1 + SAFETY_MARGIN), 2)
    assert prof["calibration"]["operator"] == "tester" and prof["calibration"]["coupon_sha256"]


def test_missing_class_blocks_promotion_and_keeps_previous_limit():
    p = _profile(); kit = build_coupon(p)
    out = calibrate(p, kit["manifest"], {"clean": ["stroke-4", "gap-4", "bridge-4", "counter-4"]}, operator="t")
    assert out["promoted"] is False
    assert out["profile"]["calibration_status"] == "CALIBRATION_INCOMPLETE"
    assert out["profile"]["is_production_profile"] is False
    assert out["report"]["engrave_line"]["status"] == "UNRESOLVED"


def test_results_naming_unknown_features_are_refused():
    p = _profile(); kit = build_coupon(p)
    with pytest.raises(ValueError):
        calibrate(p, kit["manifest"], {"clean": ["stroke-99"]}, operator="t")


def test_cli_writes_coupon_files(tmp_path):
    import subprocess, sys
    r = subprocess.run([sys.executable, "../scripts/calibrate_workshop.py", "coupon", "--out", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "coupon.dxf").exists() and (tmp_path / "coupon.svg").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["profile_name"] == "pendant/silver-925"
    import ezdxf
    doc = ezdxf.readfile(str(tmp_path / "coupon.dxf"))
    assert {"CUT", "HOLES", "ENGRAVE"} <= {l.dxf.name for l in doc.layers}
