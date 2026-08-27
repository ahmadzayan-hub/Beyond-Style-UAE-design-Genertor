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


def _hb_font(font_path: str, font_axes: dict | None = None) -> hb.Font:
    """HarfBuzz font, at variation coordinates when given. Delegates to
    app.fonts.instances so outline extraction gets the SAME instance."""
    from ..fonts.instances import FontInstance, hb_font_for, normalize_axes

    return hb_font_for(FontInstance("", font_path, normalize_axes(font_axes)))


def _glyph_order(font_path: str, font_axes: dict | None = None) -> list[str]:
    from ..fonts.instances import FontInstance, glyphset_for, normalize_axes

    return glyphset_for(FontInstance("", font_path, normalize_axes(font_axes)))[1]


def upem(font: FontRecord) -> int:
    return _hb_font(str(font.path)).face.upem


def shape_run(run: DirectionalRun, font: FontRecord, extra_features: dict | None = None,
              font_axes: dict | None = None) -> ShapedRun:
    """Shape one directional run; cluster values are codepoint indices
    relative to the full normalized text (run.start offset applied).
    `extra_features` enables OpenType stylistic variants (Glyph Variant
    Library) — shaping/joining correctness is unaffected."""
    hb_font = _hb_font(str(font.path), font_axes)
    buf = hb.Buffer()
    buf.add_str(run.text)
    buf.direction = run.direction
    buf.script = "Arab" if run.script == "arab" else "Latn"
    buf.language = "ar" if run.script == "arab" else "en"
    features = {"kern": True, "liga": True, "calt": True}
    if extra_features:
        features.update(extra_features)
    hb.shape(hb_font, buf, features)

    order = _glyph_order(str(font.path), font_axes)
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


def shape_text(text: str, font_id: str, extra_features: dict | None = None,
               font_axes: dict | None = None) -> list[ShapedRun]:
    """Shape full normalized text into visually ordered shaped runs."""
    font = get_registry().get(font_id)
    normalized = normalize(text)
    runs = segment_runs(normalized)
    base = paragraph_direction(normalized)
    # Visual order: RTL base reverses run order.
    visual_runs = list(reversed(runs)) if base == "rtl" else runs
    return [shape_run(r, font, extra_features, font_axes) for r in visual_runs]


# Letters that do not join to the following (left-side) letter — no kashida
# can be inserted after them.
NON_LEFT_JOINING = set("اأإآٱدذرزوؤةىء")
TATWEEL = "ـ"


def apply_kashida(text: str, count: int) -> tuple[str, list[int]]:
    """Insert `count` tatweel (U+0640) elongation marks before the final
    letter of each Arabic word where joining permits — the classic
    nameplate elongation. This is a RENDERING transformation of the shaping
    input only: the immutable source text is untouched, and the returned
    index map lets glyph clusters be traced back to source indices so the
    identity proof still verifies against the original text exactly.
    """
    if count <= 0:
        return text, list(range(len(text)))
    out: list[str] = []
    index_map: list[int] = []  # display index -> source index
    words: list[tuple[int, str]] = []
    start = 0
    for i, ch in enumerate(text):
        if ch == " ":
            words.append((start, text[start:i]))
            words.append((i, " "))
            start = i + 1
    words.append((start, text[start:]))
    for w_start, word in words:
        if word == " " or len(word) < 2 or not any(is_arabic_char(c) for c in word):
            for k, ch in enumerate(word):
                out.append(ch)
                index_map.append(w_start + k)
            continue
        # insertion point: before the last letter, if the letter before it
        # can join leftward.
        ins = len(word) - 1
        if word[ins - 1] in NON_LEFT_JOINING:
            ins = None
        for k, ch in enumerate(word):
            if ins is not None and k == ins:
                for _ in range(count):
                    out.append(TATWEEL)
                    index_map.append(w_start + k - 1)  # elongation belongs to the joining letter
            out.append(ch)
            index_map.append(w_start + k)
    return "".join(out), index_map


def remap_runs_to_source(runs: list[ShapedRun], index_map: list[int], source: str) -> list[ShapedRun]:
    """Rewrite glyph cluster indices from display-text space back to
    source-text space (used after kashida insertion)."""
    remapped: list[ShapedRun] = []
    for run in runs:
        glyphs = []
        for g in run.glyphs:
            src_indices = sorted({index_map[i] for i in range(g.cluster_start, g.cluster_end)})
            s, e = src_indices[0], src_indices[-1] + 1
            glyphs.append(
                g.model_copy(
                    update={
                        "cluster_start": s,
                        "cluster_end": e,
                        "source_codepoints": list(source[s:e]),
                    }
                )
            )
        remapped.append(run.model_copy(update={"glyphs": glyphs}))
    return remapped


def break_lines(text: str, max_lines: int) -> list[str]:
    """Deterministic balanced line breaking on spaces (words never split).
    Greedy fill against the balanced target length."""
    words = normalize(text).split(" ")
    if max_lines <= 1 or len(words) <= 1:
        return [normalize(text)]
    n_lines = min(max_lines, len(words))
    target = sum(len(w) for w in words) / n_lines
    lines: list[list[str]] = [[]]
    length = 0.0
    for word in words:
        remaining_lines = n_lines - len(lines)
        if lines[-1] and length + len(word) > target and remaining_lines > 0:
            lines.append([])
            length = 0.0
        lines[-1].append(word)
        length += len(word)
    return [" ".join(ws) for ws in lines]


def shape_multiline(
    text: str, font_id: str, max_lines: int, extra_features: dict | None = None,
    font_axes: dict | None = None,
) -> tuple[list[list[ShapedRun]], TextIdentityProof]:
    """Shape text as stacked lines. Identity is proven per line and merged;
    the separator spaces consumed by line breaks count as covered by the
    line-break structure (they are layout, not glyph geometry)."""
    normalized = normalize(text)
    lines = break_lines(normalized, max_lines)
    line_runs: list[list[ShapedRun]] = []
    covered: set[int] = set()
    notdef = 0
    offset = 0
    for line in lines:
        runs = shape_text(line, font_id, extra_features, font_axes)
        line_runs.append(runs)
        proof = verify_identity(line, runs)
        notdef += proof.notdef_glyph_count
        covered.update(offset + i for i in proof.covered_codepoint_indices)
        offset += len(line)
        if offset < len(normalized):
            covered.add(offset)  # the separator space this break consumed
            offset += 1
    uncovered = [i for i in range(len(normalized)) if i not in covered]
    verified = not uncovered and notdef == 0 and len(normalized) > 0
    return line_runs, TextIdentityProof(
        verified=verified,
        covered_codepoint_indices=sorted(covered),
        uncovered_codepoint_indices=uncovered,
        notdef_glyph_count=notdef,
        detail="ok" if verified else f"uncovered={uncovered[:20]} notdef={notdef}",
    )


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
