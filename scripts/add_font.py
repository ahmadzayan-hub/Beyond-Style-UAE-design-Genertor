#!/usr/bin/env python3
"""Onboard a licensed font into the registry — the owner's path to a true
Thuluth / Diwani (or any script) once a commercial license is bought.

    python3 scripts/add_font.py --file ~/Downloads/FoundryThuluth.otf \
        --font-id foundry-thuluth --family "Foundry Thuluth" \
        --license "Foundry EULA 2026 (desktop + product/merchandise)" \
        --license-file ~/Downloads/Foundry-EULA.txt \
        --source-url https://foundry.example/thuluth \
        --rights COMMERCIAL_LICENSED --script-family thuluth --capability THULUTH \
        [--style-influence ...] [--no-redistribution] [--write]

Without --write it is a dry run: the report says whether the binary is
usable (parses, covers Arabic, has contextual OpenType features, shapes the
golden name set without .notdef) and what capability it would unlock. With
--write it copies the binary + license into the assets, appends the registry
entry (next diversity index, sha256 stamped) and re-runs the identity proof
through the real registry. Rights are never assumed: UNKNOWN_RIGHTS and
INTERNAL_ONLY are refused for production capabilities.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

GOLDEN_NAMES = ("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة", "نورة")
ARABIC_LETTERS = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
REQUIRED_FEATURES = ("init", "medi", "fina")
PRODUCTION_RIGHTS = {"VERIFIED_OPEN_SOURCE", "COMMERCIAL_LICENSED", "CUSTOMER_OWNED"}
CAPABILITIES = {
    "NASKH", "RUQAA", "KUFI", "NASTALIQ", "MODERN_ARABIC", "THULUTH", "DIWANI",
    "THULUTH_INFLUENCED", "DIWANI_INFLUENCED",
    "MODERN_KUFI", "GEOMETRIC_KUFI", "DISPLAY", "BOLD", "LOGO",
}


def inspect_binary(path: Path) -> dict:
    from app.fonts.onboarding import inspect_binary as _inspect

    return _inspect(path.read_bytes())


def shape_check(path: Path) -> dict:
    from app.fonts.onboarding import shape_check as _shape

    return _shape(path.read_bytes())


def build_entry(args, path: Path, report: dict, registry: dict) -> dict:
    next_index = max((f.get("diversity_index", 0) for f in registry["fonts"]), default=-1) + 1
    return {
        "font_id": args.font_id,
        "family": args.family,
        "style_family": args.style_family or args.script_family,
        "file": path.name,
        "license": args.license,
        "license_file": Path(args.license_file).name,
        "source_url": args.source_url,
        "rights_status": args.rights,
        "redistribution_permitted": not args.no_redistribution,
        "scripts": ["arab"] + (["latn"] if report["latin_basic"] else []),
        "supports_harakat": report["mark_positioning"],
        "notes": args.notes or (
            f"{args.capability} — onboarded with scripts/add_font.py; license evidence in "
            f"{Path(args.license_file).name}."
        ),
        "script_family": args.script_family,
        "style_influence": args.style_influence,
        "production_capability": args.capability,
        "style_tags": [t for t in (args.tags or "").split(",") if t],
        "version": report["version"],
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "upstream_repo": "",
        "upstream_distribution": "COMMERCIAL_PURCHASE" if args.rights == "COMMERCIAL_LICENSED" else "",
        "upstream_path": "",
        "upstream_ref": "",
        "upstream_commit": None,
        "upstream_commit_status": "NOT_APPLICABLE_PURCHASED" if args.rights == "COMMERCIAL_LICENSED" else "",
        "retrieved_at": dt.date.today().isoformat(),
        "script_coverage": {"arabic_codepoints": report["arabic_codepoints"], "latin_basic": report["latin_basic"]},
        "diversity_index": next_index,
    }


def run(args) -> dict:
    src = Path(args.file).expanduser()
    if not src.is_file():
        raise SystemExit(f"font file not found: {src}")
    lic = Path(args.license_file).expanduser()
    if not lic.is_file():
        raise SystemExit(f"license file not found: {lic} (keep the EULA/invoice next to the font)")
    if args.rights not in PRODUCTION_RIGHTS:
        raise SystemExit(f"rights {args.rights} cannot back a production capability; refused.")
    if args.capability not in CAPABILITIES:
        raise SystemExit(f"unknown capability {args.capability}; one of {sorted(CAPABILITIES)}")

    report = inspect_binary(src)
    shaping = shape_check(src)
    problems = []
    if report["missing_arabic_letters"]:
        problems.append(f"missing Arabic letters: {''.join(report['missing_arabic_letters'])}")
    if not report["contextual_forms"]:
        problems.append("no init/medi/fina GSUB features — the font cannot join Arabic letters")
    if not shaping["ok"]:
        problems.append("golden names shape with .notdef glyphs")
    usable = not problems

    registry_path = Path(args.registry) if args.registry else ROOT / "backend/app/fonts/fonts.json"
    assets_dir = Path(args.assets_dir) if args.assets_dir else ROOT / "backend/app/assets/fonts"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if any(f["font_id"] == args.font_id for f in registry["fonts"]):
        raise SystemExit(f"font_id {args.font_id} already registered")
    entry = build_entry(args, src, report, registry)
    out = {"usable": usable, "problems": problems, "binary": report, "shaping": shaping,
           "entry": entry, "written": False}

    if args.write:
        if not usable:
            raise SystemExit("refusing --write: " + "; ".join(problems))
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, assets_dir / src.name)
        shutil.copy2(lic, assets_dir / lic.name)
        registry["fonts"].append(entry)
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out["written"] = True
        out["identity_proof"] = registry_identity_proof(registry_path, assets_dir, args.font_id)
    return out


def registry_identity_proof(registry_path: Path, assets_dir: Path, font_id: str) -> dict:
    """After writing: shape + verify through the real engine and registry."""
    from app.fonts import registry as reg_mod
    from app.engines import arabic_engine as ae

    reg = reg_mod.FontRegistry(registry_path, assets_dir)
    # Point the engine at the freshly written registry for the proof only,
    # then restore the process-wide accessor (the kit may run inside a
    # longer-lived process such as the test suite).
    original_reg, original_ae = reg_mod.get_registry, ae.get_registry
    reg_mod.get_registry = lambda: reg  # type: ignore[assignment]
    ae.get_registry = lambda: reg  # type: ignore[assignment]
    try:
        results = {}
        for name in GOLDEN_NAMES:
            runs = ae.shape_text(name, font_id)
            proof = ae.verify_identity(name, runs)
            results[name] = bool(proof.verified)
    finally:
        reg_mod.get_registry = original_reg  # type: ignore[assignment]
        ae.get_registry = original_ae  # type: ignore[assignment]
    return {"all_verified": all(results.values()), "names": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--font-id", required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--license", required=True, help="license name / EULA title")
    ap.add_argument("--license-file", required=True, help="EULA or invoice text kept as evidence")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--rights", required=True, choices=sorted(PRODUCTION_RIGHTS | {"INTERNAL_ONLY", "UNKNOWN_RIGHTS"}))
    ap.add_argument("--script-family", required=True, help="thuluth, diwani, naskh, ruqaa, kufi, nastaliq, modern_arabic")
    ap.add_argument("--capability", required=True, help="THULUTH, DIWANI, NASKH, …")
    ap.add_argument("--style-influence", default=None)
    ap.add_argument("--style-family", default=None)
    ap.add_argument("--tags", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--no-redistribution", action="store_true")
    ap.add_argument("--registry", default=None, help="override registry path (tests)")
    ap.add_argument("--assets-dir", default=None, help="override assets dir (tests)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["usable"] else 1


if __name__ == "__main__":
    sys.exit(main())
