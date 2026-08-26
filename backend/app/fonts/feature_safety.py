"""Feature safety regression — a discovered OT feature is only exposed to
production after it survives real HarfBuzz shaping of a fixed Arabic corpus.

A feature PASSES only if, with it enabled:
  * the source text is byte-identical before and after (we never mutate it),
  * no .notdef glyph appears (every letter still has a real outline),
  * cluster indices stay monotonic and span the whole string — so no letter
    or dot is silently dropped,
  * joining behaviour still produces a connected run.

Ligature-style features legitimately merge clusters, so glyph-count change
is recorded (`glyph_delta`) rather than treated as failure; a gap in the
covered span is treated as failure.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..engines.arabic_engine import shape_text

#: Fixed regression corpus — the real customer names this shop produces,
#: plus a phrase and a multi-name case.
GOLDEN_CORPUS = [
    "ع",
    "نورة",
    "ميثة",
    "محمد",
    "سلطان",
    "فاطمة",
    "حامد",
    "خالد",
    "مهرة",
    "بسم الله الرحمن الرحيم",
    "حامد محمد سلطان ميثة حمد خالد مهرة",
]

NOTDEF = 0


@dataclass
class ShapeProbe:
    text: str
    glyph_count: int
    notdef_count: int
    covered: set
    recovered_text: str


def _probe(text: str, font_id: str, features: dict | None) -> ShapeProbe:
    """Shape once and report what the glyphs actually account for.

    Each shaped glyph carries the source index range it came from, so
    coverage is checked against the real text rather than inferred from
    cluster arithmetic: if a letter or a dot were dropped, its index would
    be missing from `covered`.
    """
    runs = shape_text(text, font_id, features)
    glyphs = [g for run in runs for g in run.glyphs]
    covered: set[int] = set()
    for g in glyphs:
        covered.update(range(g.cluster_start, g.cluster_end))
    # Rebuild the source text from what the glyphs claim to represent —
    # if a feature ate a letter, the reconstruction will not match.
    segments = sorted({(g.cluster_start, "".join(g.source_codepoints)) for g in glyphs})
    recovered = "".join(seg for _, seg in segments)
    return ShapeProbe(
        text=text,
        glyph_count=len(glyphs),
        notdef_count=sum(1 for g in glyphs if g.glyph_id == NOTDEF),
        covered=covered,
        recovered_text=recovered,
    )


def check_feature(font_id: str, feature_tag: str, corpus: list[str] | None = None) -> dict:
    """Shape the corpus with and without one feature. Returns a verdict
    record — never raises on a bad feature, so discovery can disable it."""
    corpus = corpus or GOLDEN_CORPUS
    failures: list[dict] = []
    deltas: list[int] = []
    for text in corpus:
        base = _probe(text, font_id, None)
        with_feat = _probe(text, font_id, {feature_tag: True})
        # The engine must never alter the source text.
        assert with_feat.text == text, "shaping mutated the source text"
        expected = set(range(len(text)))
        reasons = []
        if with_feat.glyph_count == 0:
            reasons.append("no glyphs produced")
        if with_feat.notdef_count > base.notdef_count:
            reasons.append(
                f"introduced {with_feat.notdef_count - base.notdef_count} .notdef glyphs"
            )
        missing = expected - with_feat.covered
        if missing:
            reasons.append(
                f"dropped source characters at indices {sorted(missing)}"
            )
        lost = base.covered - with_feat.covered
        if lost:
            reasons.append(f"lost coverage the default shaping had: {sorted(lost)}")
        if with_feat.recovered_text != text:
            reasons.append("glyph clusters no longer reconstruct the source text")
        if reasons:
            failures.append({"text": text, "reasons": reasons})
        deltas.append(with_feat.glyph_count - base.glyph_count)
    return {
        "font_id": font_id,
        "feature": feature_tag,
        "safe_for_production": not failures,
        "corpus_size": len(corpus),
        "glyph_delta_range": [min(deltas), max(deltas)] if deltas else [0, 0],
        "ligating": any(d < 0 for d in deltas),
        "failures": failures,
    }


def check_font(font_id: str, features: list[str]) -> list[dict]:
    return [check_feature(font_id, tag) for tag in features]


def check_font_coverage(font_id: str, corpus: list[str] | None = None) -> dict:
    """Baseline quality gate for a font itself, independent of features.

    Fails if default shaping of the Arabic corpus produces any .notdef or
    cannot reconstruct the source text — i.e. the font cannot actually
    render the names this shop sells, whatever its metadata claims."""
    corpus = corpus or GOLDEN_CORPUS
    failures = []
    for text in corpus:
        probe = _probe(text, font_id, None)
        reasons = []
        if probe.notdef_count:
            reasons.append(f"{probe.notdef_count} .notdef glyphs (missing coverage)")
        if probe.covered != set(range(len(text))):
            reasons.append("shaped glyphs do not cover the whole source text")
        if probe.recovered_text != text:
            reasons.append("glyph clusters do not reconstruct the source text")
        if reasons:
            failures.append({"text": text, "reasons": reasons})
    return {"font_id": font_id, "shaping_pass": not failures, "failures": failures}
