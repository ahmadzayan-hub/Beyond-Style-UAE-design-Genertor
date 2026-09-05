"""Font onboarding service — one implementation for the CLI kit and the
admin upload API.

Accepts TTF / OTF / WOFF / WOFF2 (WOFF/WOFF2 are unpacked to a TrueType
binary with fontTools), inspects the binary (Arabic coverage, contextual
OpenType features, marks, embedding bits), shapes the golden names with
HarfBuzz, and — only when usable and rights-cleared — stores the binary
privately and registers it. Uploaded fonts live in PRIVATE_FONTS_DIR and
are never served by URL."""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path

GOLDEN_NAMES = ("حامد", "محمد", "سلطان", "ميثه", "حمد", "خالد", "مهرة", "نورة")
ARABIC_LETTERS = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
REQUIRED_FEATURES = ("init", "medi", "fina")
PRODUCTION_RIGHTS = {"VERIFIED_OPEN_SOURCE", "COMMERCIAL_LICENSED", "CUSTOMER_OWNED"}
CAPABILITIES = {
    "NASKH", "RUQAA", "KUFI", "NASTALIQ", "MODERN_ARABIC", "THULUTH", "DIWANI",
    "THULUTH_INFLUENCED", "DIWANI_INFLUENCED", "MODERN_KUFI", "GEOMETRIC_KUFI", "DISPLAY", "BOLD", "LOGO",
    "NASTALIQ_LEVANTINE", "FATIMID_FOLIATED", "HISTORICAL", "CALLIGRAFFITI",
}
ACCEPTED_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}


def private_fonts_dir() -> Path:
    return Path(os.environ.get("PRIVATE_FONTS_DIR", Path(__file__).resolve().parents[2] / "var" / "private_fonts"))


def overlay_file() -> Path:
    return private_fonts_dir() / "uploaded_fonts.json"


def to_truetype_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """WOFF/WOFF2 → unpacked SFNT bytes; TTF/OTF pass through. Returns
    (bytes, stored_suffix)."""
    from fontTools.ttLib import TTFont

    suffix = suffix.lower()
    if suffix not in ACCEPTED_SUFFIXES:
        raise ValueError(f"Unsupported font container {suffix}; use TTF, OTF, WOFF or WOFF2.")
    if suffix in (".woff", ".woff2"):
        tt = TTFont(io.BytesIO(data))
        tt.flavor = None
        out = io.BytesIO()
        tt.save(out)
        return out.getvalue(), (".otf" if "CFF " in tt else ".ttf")
    return data, suffix


def inspect_binary(data: bytes) -> dict:
    from fontTools.ttLib import TTFont

    tt = TTFont(io.BytesIO(data))
    cmap = tt.getBestCmap() or {}
    arabic_cps = [cp for cp in cmap if 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF]
    missing_letters = [ch for ch in ARABIC_LETTERS if ord(ch) not in cmap]
    features: set[str] = set()
    if "GSUB" in tt:
        for rec in tt["GSUB"].table.FeatureList.FeatureRecord:
            features.add(rec.FeatureTag)
    marks = "GPOS" in tt and any(
        rec.FeatureTag in ("mark", "mkmk") for rec in tt["GPOS"].table.FeatureList.FeatureRecord
    )
    name = tt["name"]
    fs_type = int(getattr(tt["OS/2"], "fsType", 0)) if "OS/2" in tt else 0
    return {
        "family_name_in_file": name.getDebugName(1) or "",
        "full_name_in_file": name.getDebugName(4) or "",
        "version": name.getDebugName(5) or "",
        "license_description_in_file": (name.getDebugName(13) or "")[:400],
        "license_url_in_file": name.getDebugName(14) or "",
        "upem": tt["head"].unitsPerEm,
        "glyph_count": len(tt.getGlyphOrder()),
        "arabic_codepoints": len(arabic_cps),
        "missing_arabic_letters": missing_letters,
        "gsub_features": sorted(features),
        "contextual_forms": all(f in features for f in REQUIRED_FEATURES),
        "mark_positioning": bool(marks),
        "latin_basic": all(ord(c) in cmap for c in "ABCabc"),
        "fs_type": fs_type,
        "embedding_restricted": bool(fs_type & 0x0002),
        "is_variable": "fvar" in tt,
    }


def shape_check(data: bytes) -> dict:
    import uharfbuzz as hb

    face = hb.Face(hb.Blob(data))
    font = hb.Font(face)
    results = []
    for nm in GOLDEN_NAMES:
        buf = hb.Buffer()
        buf.add_str(nm)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        gids = [i.codepoint for i in buf.glyph_infos]
        results.append({"name": nm, "glyphs": len(gids), "notdef": sum(1 for g in gids if g == 0)})
    return {"ok": all(r["notdef"] == 0 and r["glyphs"] > 0 for r in results), "names": results}


def evaluate(data: bytes, suffix: str) -> dict:
    """Dry-run verdict for a candidate font binary."""
    sfnt, stored_suffix = to_truetype_bytes(data, suffix)
    report = inspect_binary(sfnt)
    shaping = shape_check(sfnt)
    problems = []
    if report["missing_arabic_letters"]:
        problems.append(f"missing Arabic letters: {''.join(report['missing_arabic_letters'])}")
    if not report["contextual_forms"]:
        problems.append("no init/medi/fina GSUB features — the font cannot join Arabic letters")
    if not shaping["ok"]:
        problems.append("golden names shape with .notdef glyphs")
    return {"usable": not problems, "problems": problems, "binary": report, "shaping": shaping,
            "sfnt": sfnt, "stored_suffix": stored_suffix, "sha256": hashlib.sha256(sfnt).hexdigest()}


def register_upload(data: bytes, suffix: str, *, font_id: str, family: str, license_name: str,
                    license_text: str, source_url: str, rights: str, script_family: str, capability: str,
                    style_influence: str | None = None, tags: list[str] | None = None, owner: str = "",
                    web_use: bool = False, redistribution: bool = False, notes: str = "") -> dict:
    """Store privately + register (overlay). Rights are recorded as declared
    by the uploader; production use follows the rights status, never the
    declaration alone."""
    from .registry import get_registry

    if rights not in PRODUCTION_RIGHTS | {"INTERNAL_ONLY", "UNKNOWN_RIGHTS"}:
        raise ValueError(f"unknown rights status {rights}")
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability {capability}")
    if not license_text.strip():
        raise ValueError("license text/EULA is required as evidence")
    if any(f.font_id == font_id for f in get_registry().list()):
        raise ValueError(f"font_id {font_id} already registered")
    ev = evaluate(data, suffix)
    if not ev["usable"]:
        raise ValueError("font is not usable for Arabic jewellery lettering: " + "; ".join(ev["problems"]))
    d = private_fonts_dir()
    d.mkdir(parents=True, exist_ok=True)
    file_name = f"{font_id}{ev['stored_suffix']}"
    (d / file_name).write_bytes(ev["sfnt"])
    lic_name = f"{font_id}-LICENSE.txt"
    (d / lic_name).write_text(license_text, encoding="utf-8")
    next_index = max((f.diversity_index for f in get_registry().list()), default=-1) + 1
    entry = {
        "font_id": font_id, "family": family, "style_family": script_family, "file": file_name,
        "license": license_name, "license_file": lic_name, "source_url": source_url,
        "rights_status": rights, "redistribution_permitted": redistribution,
        "scripts": ["arab"] + (["latn"] if ev["binary"]["latin_basic"] else []),
        "supports_harakat": ev["binary"]["mark_positioning"],
        "notes": notes or f"Uploaded {dt.date.today().isoformat()} by {owner or 'admin'}; "
                          f"embedding_restricted={ev['binary']['embedding_restricted']}",
        "script_family": script_family, "style_influence": style_influence, "production_capability": capability,
        "style_tags": tags or [], "version": ev["binary"]["version"], "file_sha256": ev["sha256"],
        "upstream_repo": "", "upstream_distribution": "UPLOAD", "upstream_path": "", "upstream_ref": "",
        "upstream_commit": None, "upstream_commit_status": "NOT_APPLICABLE_UPLOAD",
        "retrieved_at": dt.date.today().isoformat(),
        "script_coverage": {"arabic_codepoints": ev["binary"]["arabic_codepoints"], "latin_basic": ev["binary"]["latin_basic"]},
        "diversity_index": next_index,
        "web_use_permitted": web_use, "owner": owner,
    }
    ov = overlay_file()
    data_ov = json.loads(ov.read_text(encoding="utf-8")) if ov.is_file() else {"fonts": []}
    data_ov["fonts"].append(entry)
    ov.write_text(json.dumps(data_ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reset_registry_caches()
    return {"entry": entry, "binary": ev["binary"], "shaping": ev["shaping"], "stored_privately": str(d / file_name)}


def reset_registry_caches() -> None:
    from . import capabilities, registry

    registry.get_registry.cache_clear()
    capabilities.script_capability_map.cache_clear()
