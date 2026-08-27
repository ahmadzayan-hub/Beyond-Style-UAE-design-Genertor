# Aesthetic Curation, Combination Safety and Variable-Axis Safety

## The honesty boundary

Ten of the thirteen suitability dimensions are **measured** from real built
geometry, each recording its method. Three — `CalligraphicGrace`,
`OrnamentalPotential`, `LuxuryFeel` — are genuine aesthetic judgements that no
deterministic function can make. They are returned as `None` /`NOT_ASSESSED`
and **await human review**. No taste score is invented anywhere in this slice.

Consequently all **52 discovered OT features remain EXPERIMENTAL** and are
hidden from customers until Beyond Style reviews the proof sheets.

## Curation states

| state | meaning | customer-visible |
|---|---|---|
| `PRODUCTION_RECOMMENDED` | reviewed and preferred | yes |
| `PRODUCTION_ALLOWED` | safe and selectable, not promoted | yes |
| `EXPERIMENTAL` | shaping-safe, aesthetically unreviewed | **no** |
| `HIDDEN` | never offered | no |

Current: 1 recommended, 6 allowed, 52 experimental. An unknown key resolves to
`EXPERIMENTAL` — never silently promoted.

## Product-specific suitability

Twelve products, each with its own envelope and representative text. A font is
built into each envelope across a spread of compositions, stroke deltas and
**connector strategies** (`loops`/`dot_strategy`) — because letters left
unjoined fail `DISCONNECTED_COMPONENT` regardless of the face, and judging a
font on one unlucky layout would be measuring the layout.

`aesthetic_gate()` is the hard rule: a candidate that fails manufacturing is
unselectable whatever it scores. `best_font_per_product()` only ever ranks
manufacturable builds.

## Feature combinations

Individual safety does not compose, so combinations are tested as
combinations — but **not** by brute force (52 features would give millions of
meaningless pairs). Seventeen curated pairings covering `ssXX+jalt`,
`cvXX+weight`, `variant+kashida`, `variant+swash`, `weight+overlap`,
`weight+stacking` and `variant+dots` are checked against the Arabic corpus.

Verdicts: `COMPATIBLE` · `CONFLICTING` · `REDUNDANT` · `UNSAFE` · `UNKNOWN`.
Only `COMPATIBLE` reaches production. Features rewriting the same glyph slots
(two `ssXX`, or `liga`+`dlig`) are `REDUNDANT` by rule and excluded.

## Variable axes

Reem Kufi, Noto Nastaliq Urdu and Lemonada each expose `wght`. Each is swept at
min / 25% / default / 75% / max by **really instancing the font** with fontTools
and re-measuring glyph outlines: counter closure, relative stroke change,
negative space, island creation, bbox growth. A safe range is the widest
contiguous safe span **containing the default** — a safe island unreachable
from the default is not offered.

> **Limit stated plainly:** `arabic_engine.py` and `outline_extractor.py` load
> every font at its **default instance** and have no axis plumbing. These
> ranges are honest measurements of the design space but the generator
> **cannot yet render a non-default weight**. They are stored as
> `NOT_YET_REACHABLE_BY_GENERATOR` and must not be advertised as selectable.

The stroke figure is a **relative proxy** (perimeter is summed over control
points, not true curve length). It compares grid points of the same glyph; it
is not a millimetre width. The real stroke gate remains the manufacturing
validator on built geometry.

## Customer style language

Eight Arabic labels — كلاسيكي · ناعم · فاخر · هندسي · حديث · انسيابي · تراثي ·
جريء — map internally to curated font + feature sets + axis ranges. The
customer endpoint `GET /api/fonts/styles` is asserted by test to contain **no
raw OpenType tag**. The internal bundle lives behind the admin token.

## Seven names

Resolved **without weakening any constraint**, through the real production path
(`generate_candidates`, which applies the deterministic long-text adaptation):
16 of 48 internal candidates valid, all via stacked multi-line, source text
unchanged on every one. Had none passed, the outcome would be
`BLOCK_PRODUCTION_EXPORT`.

## Golden Production influence

Evidence priority: manufactured + customer-approved > workshop-approved >
designer-approved > **AI aesthetic opinion (last, advisory only)**. The
pearl-earring case informs single-letter and drop earrings; the ADAM/OMAR case
informs necklace, pendant and multi-name. Construction principles transfer;
geometry never does.

## Evidence

`docs/evidence/aesthetic-curation/` — family sheets per font, product sheet,
long-text sheet, `combination-matrix.json`, `variable-axis-safety.json`,
`seven-name-report.json`, `golden-production-influence.json`, `scores.json`,
`curation.json`. Regenerate with `python3 scripts/aesthetic_curation.py --write`.

## True Diwani / Thuluth

Unchanged: `LICENSE_REQUIRED`. Katibeh stays `THULUTH_INFLUENCED`, Lemonada
`DIWANI_INFLUENCED`, and a test proves curation cannot become a back door to
selecting the unlicensed classical scripts.
