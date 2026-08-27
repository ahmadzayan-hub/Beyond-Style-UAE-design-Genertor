# Variable-Font Axis Plumbing and Real-mm Geometry Validation

## One instance, both consumers

The failure this slice removes: shaping a run at one set of variation
coordinates while extracting outlines at another — plausible-looking geometry
that is quietly wrong. `app/fonts/instances.py` is now the single source of
truth. Both HarfBuzz and fontTools are built from the **same instanced font
bytes**, keyed by `(font_id, axes)`:

```
source_text → font → validated font_axes → FontInstance
                                          ├─ hb_font_for()   → shaping
                                          └─ glyphset_for()  → outlines
                                                             → mm geometry
```

## Validation, never clamping

`validate_axes()` gates in order: the axis must exist in the font's `fvar`,
the value must sit inside the font's own min/max, and — when a product is
named — inside the geometry-verified safe range. Failures raise
`UNSUPPORTED_AXIS` or `AXIS_VALUE_OUT_OF_RANGE` with the bounds attached.
Nothing is silently clamped.

The check lives in `build_geometry_for_recipe`, the one path both generation
and designer edits go through, so an unsupported coordinate is refused
cleanly instead of crashing inside fontTools.

## Identity and immutability

`font_axes` is part of the candidate identity hash — but **omitted from the
payload when empty**, so adding the field did not renumber a single existing
design and the immutable golden fixture is byte-identical. Once coordinates
are set, a different weight is a different candidate. `font_axes` is an
editable recipe field, so a weight change produces a **new immutable
DesignVersion**; the approved one keeps its geometry hash.

## Export traceability

SVG metadata and DXF custom vars now carry `font_id`, `font_axes`,
`ot_feature_set` and the **font binary sha256** alongside the existing design
id, source-text hash and geometry hash — enough to reconstruct the exact
piece from stored parameters.

## Real millimetres

`app/engines/geometry_metrics.py` measures the **final mm geometry**:
minimum material width, minimum gap, counter clearance, island areas, bridge
and attachment width, overall dimensions. Method is deterministic bisection
on erosion (eroding by e/2 removes anything narrower than e); gaps use exact
pairwise component distance, because dilation reports 0 as soon as any two
parts touch and hides the real spacing elsewhere.

`meets_workshop_rules()` is the manufacturing decision surface and consumes
only these mm values. The relative stroke figure in `app/fonts/axes.py`
remains an **aesthetic/relative metric over font units** and is asserted by
test never to appear here.

## Axis ranges revalidated on real geometry

The previously published font-unit ranges were **not promoted**. Every grid
point (min/25%/default/75%/max) was rebuilt as real jewellery geometry across
eight products and re-measured in mm, with two gates required — the existing
validator *and* the mm gate — plus a check that counters present at the
default instance survive the weight change.

Result: `wght` is `GEOMETRY_VERIFIED_SAFE` across its full 400–700 range for
all eight tested products, on all three variable fonts. This **contradicts
the earlier font-unit proxy**, which had flagged small-size Reem Kufi unsafe
above 400 on a fill-ratio ceiling. Real geometry disagrees: at earring scale
a single large letter keeps 2.4–2.5 mm counter clearance and only gains
material as weight rises. The proxy was measuring raw glyph fill, not the
manufactured piece — which is exactly why the brief said not to promote it.

Ranges are stored per font × axis × product with `evidence_level`,
`tested_values`, `manufacturing_profile` and a reason
(`backend/app/data/curation.json` → `product_axis_ranges`).

## Combinations revalidated

The five weight-bearing combinations were re-run through real geometry. A
combination is `PRODUCTION_CAPABLE` only when all five hold: shaping safe,
source identity safe, outline generated, geometry valid, mm gate passed.
Four qualify. Noto Nastaliq Urdu at `wght=700` stacked is
`NOT_PRODUCTION_CAPABLE` — it shapes cleanly and passes the mm gate but
fails the geometry validator, so both gates are genuinely required.

## Long text

The suitability probe no longer hand-builds recipes for long text: multi-name
and medallion now run through `generate_candidates`, the same production
long-text adaptation. All 12 products now have a manufacturable option
(previously 10). The seven-name result is unchanged at 16/48 valid via
stacked multi-line, with the source text preserved on every candidate.

## UI

Customers still choose words (كلاسيكي · ناعم · فاخر · هندسي · حديث ·
انسيابي · تراثي · جريء); `customer_style_options()` is asserted to contain no
`wght` and no `font_axes`. `customer_axis_for_style()` maps a label to a
coordinate **inside the verified range**. `designer_axis_bounds()` offers a
slider only where `evidence_level` is `GEOMETRY_VERIFIED_SAFE`; anything else
returns `available: false` with the reason, so unsafe range is visibly
unavailable rather than silently permitted.

## Human review

Unchanged and deliberately so: `CalligraphicGrace`, `LuxuryFeel` and
`OrnamentalPotential` remain `NOT_ASSESSED`, and all 52 discovered features
remain `EXPERIMENTAL`. The new proof sheets
(`docs/evidence/axis-plumbing/axis-proof-*.svg`, 10 safe instances per font)
are the input to the next Human Aesthetic Review slice, not a substitute
for it.

## True Diwani / Thuluth

Unchanged: `LICENSE_REQUIRED`, no font, and asserted by test.
