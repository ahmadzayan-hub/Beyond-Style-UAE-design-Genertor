"""Deterministic Arabic/Latin text shaping engine.

Pipeline: NFC normalization → directional run segmentation (BiDi categories)
→ HarfBuzz/OpenType shaping per run → glyph identity map back to codepoint
indices of the immutable source text → identity verification.

The engine never alters the source text. If glyph coverage cannot be proven
(missing glyphs, uncovered codepoints), verification fails and production
export must be blocked downstream.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import uharfbuzz as hb
from fontTools.ttLib import TTFont

from ..fonts.registry import FontRecord, get_registry
from ..schemas.jewellery_design import (
    GlyphIdentity,
    ShapedRun,
    TextIdentityProof,
)

ARABIC_BIDI_CATEGORIES = {"AL", "AN"}
RTL_BIDI_CATEGORIES = {"R", "AL", "AN"}
NEUTRAL_BIDI_CATEGORIES = {"WS", "ON", "CS", "ES", "ET", "NSM", "BN"}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def is_arabic_char(ch: str) -> bool:
    return unicodedata.bidirectional(ch) in ARABIC_BIDI_CATEGORIES or (
        unicodedata.bidirectional(ch) == "NSM" and "؀" <= ch <= "ۿ"
    )


def paragraph_direction(text: str) -> str:
    """RTL base direction if the first strong character is RTL."""
    for ch in text:
        cat = unicodedata.bidirectional(ch)
        if cat in ("L",):
            return "ltr"
        if cat in ("R", "AL"):
            return "rtl"
    return "ltr"


@dataclass(frozen=True)
class DirectionalRun:
    start: int  # codepoint index in normalized text
    end: int  # exclusive
    text: str
    direction: str  # "rtl" | "ltr"
    script: str  # "arab" | "latn"


def segment_runs(text: str) -> list[DirectionalRun]:
    """Split normalized text into directional runs.

    Neutrals (spaces, combining marks) attach to the current run; leading
    neutrals attach to the first strong run. This is a simplified UBA
    sufficient for single- and dual-script jewellery text.
    """
    if not text:
        return []
    runs: list[DirectionalRun] = []
    cur_dir: str | None = None
    start = 0
    for i, ch in enumerate(text):
        cat = unicodedata.bidirectional(ch)
        if cat in NEUTRAL_BIDI_CATEGORIES:
            continue
        d = "rtl" if cat in RTL_BIDI_CATEGORIES else "ltr"
        if cur_dir is None:
            cur_dir = d
        elif d != cur_dir:
            runs.append(_make_run(text, start, i, cur_dir))
            start = i
            cur_dir = d
    runs.append(_make_run(text, start, len(text), cur_dir or paragraph_direction(text)))
    return runs


def _make_run(text: str, start: int, end: int, direction: str) -> DirectionalRun:
    slice_ = text[start:end]
    script = "arab" if any(is_arabic_char(c) for c in slice_) else "latn"
    return DirectionalRun(start=start, end=end, text=slice_, direction=direction, script=script)


@lru_cache(maxsize=8)
def _hb_font(font_path: str) -> hb.Font:
    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    return hb.Font(face)


@lru_cache(maxsize=8)
def _glyph_order(font_path: str) -> list[str]:
    return TTFont(font_path, lazy=True).getGlyphOrder()


def upem(font: FontRecord) -> int:
    return _hb_font(str(font.path)).face.upem


def shape_run(run: DirectionalRun, font: FontRecord) -> ShapedRun:
    """Shape one directional run; cluster values are codepoint indices
    relative to the full normalized text (run.start offset applied)."""
    hb_font = _hb_font(str(font.path))
    buf = hb.Buffer()
    buf.add_str(run.text)
    buf.direction = run.direction
    buf.script = "Arab" if run.script == "arab" else "Latn"
    buf.language = "ar" if run.script == "arab" else "en"
    hb.shape(hb_font, buf, {"kern": True, "liga": True, "calt": True})

    order = _glyph_order(str(font.path))
    infos = buf.glyph_infos
    positions = buf.glyph_positions
    scale = 1.0  # font units; mm conversion happens in geometry engine

    # cluster -> end boundary: next distinct cluster in logical order
    clusters = sorted({info.cluster for info in infos})
    cluster_end = {}
    for idx, c in enumerate(clusters):
        cluster_end[c] = clusters[idx + 1] if idx + 1 < len(clusters) else len(run.text)

    glyphs: list[GlyphIdentity] = []
    for info, pos in zip(infos, positions):
        c_start = info.cluster
        c_end = cluster_end[info.cluster]
        glyphs.append(
            GlyphIdentity(
                glyph_id=info.codepoint,  # HarfBuzz: glyph index after shaping
                glyph_name=order[info.codepoint] if info.codepoint < len(order) else f"gid{info.codepoint}",
                cluster_start=run.start + c_start,
                cluster_end=run.start + c_end,
                source_codepoints=list(run.text[c_start:c_end]),
                x_offset_mm=pos.x_offset * scale,
                y_offset_mm=pos.y_offset * scale,
                x_advance_mm=pos.x_advance * scale,
            )
        )
    return ShapedRun(
        text_slice=run.text,
        direction=run.direction,
        script=run.script,
        font_id=font.font_id,
        glyphs=glyphs,
    )


def shape_text(text: str, font_id: str) -> list[ShapedRun]:
    """Shape full normalized text into visually ordered shaped runs."""
    font = get_registry().get(font_id)
    normalized = normalize(text)
    runs = segment_runs(normalized)
    base = paragraph_direction(normalized)
    # Visual order: RTL base reverses run order.
    visual_runs = list(reversed(runs)) if base == "rtl" else runs
    return [shape_run(r, font) for r in visual_runs]


def verify_identity(text: str, shaped_runs: list[ShapedRun]) -> TextIdentityProof:
    """Prove every codepoint of the normalized source text is consumed by
    exactly the shaped glyph clusters, with no missing (.notdef) glyphs.
    """
    normalized = normalize(text)
    n = len(normalized)
    covered: set[int] = set()
    notdef = 0
    for run in shaped_runs:
        for g in run.glyphs:
            if g.glyph_id == 0:
                notdef += 1
            covered.update(range(g.cluster_start, g.cluster_end))
    uncovered = [i for i in range(n) if i not in covered]
    verified = not uncovered and notdef == 0 and n > 0
    detail = "ok" if verified else (
        f"uncovered={uncovered[:20]} notdef={notdef} len={n}"
    )
    return TextIdentityProof(
        verified=verified,
        covered_codepoint_indices=sorted(covered),
        uncovered_codepoint_indices=uncovered,
        notdef_glyph_count=notdef,
        detail=detail,
    )
