"""OpenType capability discovery — read from the font binary, never invented.

Every feature tag, variation axis and script/language system reported here
is enumerated from the installed font's own GSUB/GPOS/fvar tables via
fontTools. Nothing in this module hardcodes what a font "should" support:
if a tag is absent from the binary it is absent from the capability record,
so the Glyph Variant Library can only ever offer variants that really exist.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fontTools.ttLib import TTFont

#: Features HarfBuzz applies on its own for correct Arabic text. They are
#: never offered as optional "variants" — turning them off would break
#: joining or mark placement, not restyle the letters.
ALWAYS_ON = {
    "ccmp", "locl", "init", "medi", "fina", "isol", "rlig",
    "mark", "mkmk", "curs", "kern", "rvrn", "rclt",
}

#: Non-letterform features (digits, fractions, super/subscript). Present in
#: many fonts but irrelevant to jewellery lettering.
NON_LETTERFORM = {
    "dnom", "numr", "frac", "sups", "subs", "sinf", "ordn", "zero",
    "lnum", "onum", "pnum", "case", "aalt", "rtlm",
}


def optional_letterform_features(tags: set[str]) -> list[str]:
    """The subset a designer could meaningfully choose between."""
    return sorted(tags - ALWAYS_ON - NON_LETTERFORM)


@dataclass
class FontCapability:
    font_id: str
    family: str
    version: str
    file_sha256: str
    gsub_features: list[str] = field(default_factory=list)
    gpos_features: list[str] = field(default_factory=list)
    variation_axes: list[dict] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    optional_features: list[str] = field(default_factory=list)
    arabic_codepoints: int = 0
    supports_harakat: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _feature_tags(font: TTFont, table: str) -> set[str]:
    if table not in font:
        return set()
    return {r.FeatureTag for r in font[table].table.FeatureList.FeatureRecord}


def _script_langs(font: TTFont) -> tuple[list[str], list[str]]:
    scripts: set[str] = set()
    languages: set[str] = set()
    for table in ("GSUB", "GPOS"):
        if table not in font:
            continue
        for rec in font[table].table.ScriptList.ScriptRecord:
            scripts.add(rec.ScriptTag.strip())
            for lang in rec.Script.LangSysRecord or []:
                languages.add(lang.LangSysTag.strip())
    return sorted(scripts), sorted(languages)


#: Arabic combining marks (harakat) — presence in cmap proves the font can
#: carry vocalisation, rather than us asserting it in metadata.
HARAKAT = set(range(0x064B, 0x0653)) | {0x0670}


def discover(font_id: str, path: Path) -> FontCapability:
    """Inspect one font file and return its real capability record."""
    data = path.read_bytes()
    font = TTFont(path, lazy=True)
    names = {r.nameID: str(r) for r in font["name"].names if r.platformID == 3}
    gsub = _feature_tags(font, "GSUB")
    gpos = _feature_tags(font, "GPOS")
    scripts, languages = _script_langs(font)
    cmap = set(font.getBestCmap())
    axes = [
        {"tag": a.axisTag, "min": a.minValue, "default": a.defaultValue, "max": a.maxValue}
        for a in (font["fvar"].axes if "fvar" in font else [])
    ]
    return FontCapability(
        font_id=font_id,
        family=names.get(1, ""),
        version=names.get(5, ""),
        file_sha256=hashlib.sha256(data).hexdigest(),
        gsub_features=sorted(gsub),
        gpos_features=sorted(gpos),
        variation_axes=axes,
        scripts=scripts,
        languages=languages,
        optional_features=optional_letterform_features(gsub | gpos),
        arabic_codepoints=sum(1 for c in cmap if 0x0600 <= c <= 0x06FF),
        supports_harakat=bool(cmap & HARAKAT),
    )


def discover_all() -> dict[str, dict]:
    from .registry import get_registry

    return {
        record.font_id: discover(record.font_id, record.path).to_dict()
        for record in get_registry().list()
    }
