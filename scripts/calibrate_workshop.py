#!/usr/bin/env python3
"""Workshop calibration kit CLI.

  python3 scripts/calibrate_workshop.py coupon --product pendant --material silver-925 --out docs/evidence/calibration/
      → writes coupon.svg, coupon.dxf, manifest.json (cut + engrave the plate once)

  python3 scripts/calibrate_workshop.py apply --product pendant --material silver-925 \
      --manifest docs/evidence/calibration/manifest.json --results results.json --operator "Name" --write
      → prints the measured limits; with --write, records a new profile
        version in backend/app/data/workshop_profiles.json (WORKSHOP_CALIBRATED)

results.json: {"clean": ["stroke-4","stroke-5","gap-3",...]}  — the features
that came out clean and to size. Nothing is promoted without this file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engines.calibration import build_coupon, calibrate  # noqa: E402


def _profiles():
    path = ROOT / "backend" / "app" / "data" / "workshop_profiles.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _find(data, product, material):
    for p in data["profiles"]:
        if p["product"] == product and p["material"] == material:
            return p
    raise SystemExit(f"no profile for {product}/{material}")


from app.engines.calibration import coupon_dxf as _dxf, coupon_svg as _svg, write_profile  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coupon"); c.add_argument("--product", default="pendant"); c.add_argument("--material", default="silver-925"); c.add_argument("--out", required=True)
    a = sub.add_parser("apply"); a.add_argument("--product", default="pendant"); a.add_argument("--material", default="silver-925")
    a.add_argument("--manifest", required=True); a.add_argument("--results", required=True); a.add_argument("--operator", required=True); a.add_argument("--write", action="store_true")
    args = ap.parse_args()

    path, data = _profiles()
    profile = _find(data, args.product, args.material)
    if args.cmd == "coupon":
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        kit = build_coupon(profile)
        w, h = kit["manifest"]["plate_mm"]
        (out / "coupon.svg").write_text(_svg(kit["cut"], kit["engrave"], w, h, kit["manifest"]), encoding="utf-8")
        (out / "coupon.dxf").write_text(_dxf(kit["cut"], kit["engrave"]), encoding="utf-8")
        (out / "manifest.json").write_text(json.dumps(kit["manifest"], indent=2), encoding="utf-8")
        print(f"coupon written to {out} — cut/engrave it in {args.material}, then record clean features in results.json")
        return 0

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    outcome = calibrate(profile, manifest, results, operator=args.operator)
    print(json.dumps(outcome["report"], indent=2))
    print("promoted:", outcome["promoted"], "→", outcome["profile"]["calibration_status"])
    if args.write:
        written = write_profile(args.product, args.material, outcome["profile"])
        print(f"profile written: {written['path']} (profiles_version {written['profiles_version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
