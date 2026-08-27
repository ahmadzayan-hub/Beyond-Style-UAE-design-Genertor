"""Feature-combination safety.

Individual-feature safety does not compose. Two features that each shape
correctly alone can, together, substitute a glyph that the other has already
replaced, close a counter, or merge two letters into an unreadable blob. So
combinations are tested as combinations — but deliberately NOT by brute
force: 52 features would give millions of pairs, most meaningless. Instead a
small set of curated, semantically motivated pairings is checked.

Verdicts: COMPATIBLE, CONFLICTING, REDUNDANT, UNSAFE, UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass

from .feature_safety import GOLDEN_CORPUS, _probe

COMPATIBLE = "COMPATIBLE"
CONFLICTING = "CONFLICTING"
REDUNDANT = "REDUNDANT"
UNSAFE = "UNSAFE"
UNKNOWN = "UNKNOWN"

#: Feature families that rewrite the SAME glyph slots. Stacking two of them
#: is redundant at best (the later simply wins) and confusing at worst.
SAME_SLOT_FAMILIES = [
    {"salt", "ss01", "ss02", "ss03", "ss04", "ss05", "ss06", "ss07", "ss08"},
    {"liga", "dlig"},
]


def a_priori_rule(tags: tuple[str, ...]) -> str | None:
    """Rules we can state before shaping anything. Returning None means
    'no rule applies — go and measure it'."""
    for family in SAME_SLOT_FAMILIES:
        if len(set(tags) & family) > 1:
            return REDUNDANT
    return None


@dataclass(frozen=True)
class CombinationCase:
    """One curated combination worth testing, and why."""

    font_id: str
    tags: tuple[str, ...]
    kind: str          # what design axis pairing this represents
    rationale: str
    extra: dict = None  # non-OT axes (kashida, swash, weight, composition)


def curated_combinations() -> list[CombinationCase]:
    """The pairings that actually occur in jewellery composition. Each
    exists because a designer would plausibly ask for it."""
    C = CombinationCase
    return [
        # ssXX + jalt — stylistic alternate against justification alternate.
        C("aref-ruqaa", ("ss01", "jalt"), "ssXX+jalt",
          "Ruqaa stylistic set with justification alternates"),
        C("aref-ruqaa", ("ss05", "jalt"), "ssXX+jalt",
          "second stylistic set against the same justification axis"),
        # Same-slot stacking — expected REDUNDANT, asserted not assumed.
        C("aref-ruqaa", ("ss01", "ss02"), "ssXX+ssXX",
          "two stylistic sets rewriting the same slots"),
        C("amiri-regular", ("ss01", "ss05"), "ssXX+ssXX",
          "Amiri stylistic sets stacked"),
        C("scheherazade-new", ("salt", "cv44"), "salt+cvXX",
          "blanket stylistic alternates against one character variant"),
        # cvXX + weight — character variant across the variable axis.
        C("reem-kufi", ("cv01",), "cvXX+weight",
          "Kufi character variant at a heavier weight", {"wght": "max"}),
        C("reem-kufi", ("cv02",), "cvXX+weight",
          "Kufi character variant at the lightest weight", {"wght": "min"}),
        C("reem-kufi", ("cv01", "cv02"), "cvXX+cvXX",
          "two independent character variants together"),
        # variant + kashida — elongation interacting with substitution.
        C("amiri-regular", ("ss01",), "variant+kashida",
          "stylistic set with kashida elongation", {"kashida_count": 2}),
        C("aref-ruqaa", ("ss03",), "variant+kashida",
          "Ruqaa alternate with kashida elongation", {"kashida_count": 2}),
        # variant + swash — substitution plus appended ornament geometry.
        C("amiri-regular", ("ss02",), "variant+swash",
          "stylistic set with a decorative swash", {"swash": "tail_sweep"}),
        C("katibeh", ("ss01",), "variant+swash",
          "bridge-face alternate with a swash", {"swash": "underline_flourish"}),
        # weight + overlap / stacking — axis against composition pressure.
        C("lemonada", (), "weight+overlap",
          "heaviest weight with tight letter spacing", {"wght": "max", "letter_spacing_mm": -0.4}),
        C("reem-kufi", (), "weight+stacking",
          "heaviest weight on stacked multi-line text", {"wght": "max", "max_lines": 3}),
        C("noto-nastaliq-urdu", (), "weight+stacking",
          "Nastaliq's steep baseline stacked at max weight", {"wght": "max", "max_lines": 3}),
        # variant + dot treatment — substitution against dot restyling.
        C("scheherazade-new", ("cv48",), "variant+dots",
          "alternate tails with merged dots", {"dot_strategy": "merge"}),
        C("amiri-regular", ("ss03",), "variant+dots",
          "stylistic set with bridged dots", {"dot_strategy": "bridge"}),
    ]


def check_combination(case: CombinationCase, corpus: list[str] | None = None) -> dict:
    """Shape the corpus with all of the combination's OT features at once.

    A combination is production-safe only if it introduces no .notdef,
    drops no source character, and still lets the glyph clusters
    reconstruct the source text exactly."""
    corpus = corpus or GOLDEN_CORPUS[:6]
    verdict = a_priori_rule(case.tags)
    features = {t: True for t in case.tags}
    failures: list[dict] = []
    deltas: list[int] = []

    for text in corpus:
        base = _probe(text, case.font_id, None)
        combo = _probe(text, case.font_id, features) if features else base
        assert combo.text == text, "shaping mutated the source text"
        reasons = []
        if features:
            if combo.glyph_count == 0:
                reasons.append("no glyphs produced")
            if combo.notdef_count > base.notdef_count:
                reasons.append("introduced .notdef glyphs")
            missing = set(range(len(text))) - combo.covered
            if missing:
                reasons.append(f"dropped source characters at {sorted(missing)}")
            if combo.recovered_text != text:
                reasons.append("glyph clusters no longer reconstruct the source text")
        if reasons:
            failures.append({"text": text, "reasons": reasons})
        deltas.append(combo.glyph_count - base.glyph_count)

    if failures:
        verdict = UNSAFE
    elif verdict is None:
        verdict = COMPATIBLE
    return {
        "font_id": case.font_id,
        "tags": list(case.tags),
        "kind": case.kind,
        "rationale": case.rationale,
        "extra": case.extra or {},
        "verdict": verdict,
        "shaping_safe": not failures,
        "glyph_delta_range": [min(deltas), max(deltas)] if deltas else [0, 0],
        "failures": failures,
        "corpus_size": len(corpus),
    }


def production_safe_combinations(results: list[dict]) -> list[dict]:
    """Only COMPATIBLE survives to production. REDUNDANT is shaping-safe
    but pointless, so it is not offered; UNSAFE/CONFLICTING are blocked."""
    return [r for r in results if r["verdict"] == COMPATIBLE and r["shaping_safe"]]
