#!/usr/bin/env python3
"""Regenerate font capability data FROM the installed font binaries.

Pipeline: fontTools discovery -> HarfBuzz feature-safety regression over
the fixed Arabic golden corpus -> write app/data/font_capabilities.json and
merge the surviving features into glyph_variants.json's ot_feature_sets.

Nothing here invents a feature: a tag reaches production only if it exists
in the font AND shapes the whole corpus without dropping a character.

Usage: python3 scripts/discover_font_features.py [--write]
"""
from __future__ import annotations

import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.fonts.feature_safety import GOLDEN_CORPUS, check_feature  # noqa: E402
from app.fonts.ot_discovery import discover  # noqa: E402
from app.fonts.registry import get_registry  # noqa: E402

CAPS_FILE = BACKEND / "app" / "data" / "font_capabilities.json"
VARIANTS_FILE = BACKEND / "app" / "data" / "glyph_variants.json"

#: Human labels for the feature tags we surface. Unlabelled tags still get
#: a generated label — the label is presentation, the tag is the truth.
LABELS = {
    "salt": "stylistic alternates",
    "calt": "contextual alternates",
    "jalt": "justification alternates",
    "dlig": "discretionary ligatures",
    "liga": "standard ligatures",
    "ss01": "stylistic set 1", "ss02": "stylistic set 2", "ss03": "stylistic set 3",
    "ss04": "stylistic set 4", "ss05": "stylistic set 5", "ss06": "stylistic set 6",
    "ss07": "stylistic set 7", "ss08": "stylistic set 8",
    "cv01": "character variant 1", "cv02": "character variant 2", "cv03": "character variant 3",
}


def main(write: bool) -> int:
    registry = get_registry()
    caps: dict = {"corpus": GOLDEN_CORPUS, "fonts": {}}
    generated_sets: dict = {}

    for record in registry.list():
        cap = discover(record.font_id, record.path)
        if cap.file_sha256 != record.file_sha256 and record.file_sha256:
            print(f"!! {record.font_id}: binary hash differs from registry", file=sys.stderr)
            return 2
        verdicts = [check_feature(record.font_id, tag) for tag in cap.optional_features]
        safe = [v["feature"] for v in verdicts if v["safe_for_production"]]
        rejected = [
            {"feature": v["feature"], "failures": v["failures"][:2]}
            for v in verdicts
            if not v["safe_for_production"]
        ]
        caps["fonts"][record.font_id] = {
            **cap.to_dict(),
            "script_family": record.script_family,
            "style_influence": record.style_influence,
            "production_capability": record.production_capability,
            "safe_features": safe,
            "rejected_features": rejected,
            "feature_verdicts": verdicts,
        }
        print(
            f"{record.font_id:22} discovered={len(cap.optional_features):2} "
            f"safe={len(safe):2} rejected={len(rejected)} {safe}"
        )
        for tag in safe:
            key = f"{record.font_id}-{tag}"
            generated_sets[key] = {
                "fonts": [record.font_id],
                "features": {tag: True},
                "label": f"{record.family} {LABELS.get(tag, tag)}",
                "provenance": "DISCOVERED_FROM_FONT_TABLES",
                "safe_for_production": True,
                "affected_scripts": cap.scripts,
            }

    if not write:
        print("\n(dry run — pass --write to persist)")
        return 0

    CAPS_FILE.write_text(json.dumps(caps, indent=1, ensure_ascii=False) + "\n")
    lib = json.loads(VARIANTS_FILE.read_text(encoding="utf-8"))
    # Hand-curated sets stay; generated ones are refreshed wholesale.
    lib["ot_feature_sets"] = {
        k: v for k, v in lib["ot_feature_sets"].items()
        if v.get("provenance") != "DISCOVERED_FROM_FONT_TABLES"
    }
    for k, v in lib["ot_feature_sets"].items():
        v.setdefault("provenance", "CURATED_VERIFIED_AGAINST_FONT_TABLES")
        v.setdefault("safe_for_production", True)
    lib["ot_feature_sets"].update(generated_sets)
    lib["library_version"] = "0.2.0"
    VARIANTS_FILE.write_text(json.dumps(lib, indent=1, ensure_ascii=False) + "\n")
    print(f"\nwrote {CAPS_FILE.name} and {len(generated_sets)} generated feature sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
