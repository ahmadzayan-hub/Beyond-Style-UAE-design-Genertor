"""Licensed-font onboarding kit + scene grounds for the studio render."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "scripts" / "add_font.py"
ASSETS = ROOT / "backend" / "app" / "assets" / "fonts"


def _kit():
    spec = importlib.util.spec_from_file_location("add_font", KIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _args(mod, tmp_path, **over):
    lic = tmp_path / "EULA.txt"
    lic.write_text("Test EULA: desktop + product license, outlines in goods allowed.")
    argv = [
        "--file", str(ASSETS / "Katibeh-Regular.ttf"), "--font-id", "test-thuluth",
        "--family", "Test Thuluth", "--license", "Test EULA", "--license-file", str(lic),
        "--source-url", "https://example.test/thuluth", "--rights", "COMMERCIAL_LICENSED",
        "--script-family", "thuluth", "--capability", "THULUTH",
        "--registry", str(tmp_path / "fonts.json"), "--assets-dir", str(tmp_path / "assets"),
    ]
    for k, v in over.items():
        if v is True:
            argv.append(k)
        else:
            argv += [k, v]
    return argv


def _temp_registry(tmp_path):
    src = ROOT / "backend" / "app" / "fonts" / "fonts.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    (tmp_path / "fonts.json").write_text(json.dumps(data), encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    for f in ASSETS.iterdir():
        shutil.copy2(f, assets / f.name)
    return tmp_path / "fonts.json", assets


def test_dry_run_reports_a_usable_binary(tmp_path, capsys):
    mod = _kit()
    _temp_registry(tmp_path)
    rc = mod.main(_args(mod, tmp_path))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["usable"] and not out["written"]
    assert out["binary"]["contextual_forms"] and out["binary"]["missing_arabic_letters"] == []
    assert out["shaping"]["ok"] and all(n["notdef"] == 0 for n in out["shaping"]["names"])
    assert out["entry"]["production_capability"] == "THULUTH"
    from app.fonts.registry import get_registry
    expected_index = max(f.diversity_index for f in get_registry().list()) + 1
    assert out["entry"]["file_sha256"] and out["entry"]["diversity_index"] == expected_index
    assert not (tmp_path / "assets" / "EULA.txt").exists()  # dry run copies nothing


def test_unknown_rights_are_refused(tmp_path):
    mod = _kit()
    _temp_registry(tmp_path)
    with pytest.raises(SystemExit):
        mod.main(_args(mod, tmp_path, **{"--rights": "UNKNOWN_RIGHTS"}))


def test_write_registers_verifies_identity_and_unlocks_true_thuluth(tmp_path, capsys, monkeypatch):
    mod = _kit()
    reg_path, assets = _temp_registry(tmp_path)
    monkeypatch.setattr(mod, "ROOT", ROOT)
    rc = mod.main(_args(mod, tmp_path, **{"--write": True}))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["written"] and out["identity_proof"]["all_verified"]
    assert (assets / "test-thuluth-LICENSE.txt").exists()   # licence copied under the font id, never a generic name

    from app.fonts import capabilities as cap, registry as reg_mod

    reg = reg_mod.FontRegistry(reg_path, assets)
    assert reg.get("test-thuluth").production_capability == "THULUTH"
    monkeypatch.setattr(cap, "get_registry", lambda: reg)
    cap.script_capability_map.cache_clear()
    try:
        assert cap.script_capability_map()["thuluth"]["status"] == cap.REAL
        assert cap.resolve_script_request("thuluth")["outcome"] == "AVAILABLE"
        assert cap.production_capability_map()["THULUTH"] == cap.REAL
        assert cap.production_capability_map()["DIWANI"] == cap.LICENSE_REQUIRED  # still honest
    finally:
        cap.script_capability_map.cache_clear()


def test_without_a_licensed_cut_diwani_stays_influenced_only():
    """Diwani has no rights-cleared source (the owner-supplied Al Diwani Al
    Majd carries no licence) → influenced only. Thuluth is now TRUE through
    the OFL AMoshref Thulth."""
    from app.fonts import capabilities as cap

    cap.script_capability_map.cache_clear()
    assert cap.production_capability_map()["DIWANI"] == cap.LICENSE_REQUIRED
    assert cap.resolve_script_request("diwani")["outcome"] == "STYLE_NOT_AVAILABLE"
    assert cap.production_capability_map()["THULUTH"] == cap.REAL
    assert cap.resolve_script_request("thuluth")["outcome"] == "AVAILABLE"


def test_scene_grounds_change_only_the_background():
    from app.config import DEFAULT_RULES
    from app.engines.generator import generate_candidates
    from app.exporters.svg_exporter import SCENE_GROUNDS, export_material_proof_svg
    from app.schemas.jewellery_design import ImmutableSourceText

    src = ImmutableSourceText.create("ميثة", confirmed=True)
    _, top = generate_candidates("d", src, DEFAULT_RULES)
    paths = None
    for scene in SCENE_GROUNDS:
        svg = export_material_proof_svg(top[0], src, "gold-18k-yellow", scene)
        d = re.findall(r'<path d="([^"]+)"', svg)
        assert paths is None or d == paths
        paths = d
        assert SCENE_GROUNDS[scene][0] in svg and f'"scene": "{scene}"' in svg
    with pytest.raises(ValueError):
        export_material_proof_svg(top[0], src, "gold-18k-yellow", "moon_surface")
