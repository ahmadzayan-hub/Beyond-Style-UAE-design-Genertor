# ADR-0005 — Jewellery realism in the parametric construction (2026-09-04)

## Context
Owner review of the 10 proofs: «ما عجبني التصميمات لأنها غير حقيقية» — the designs did not look
like real jewellery. Rendering the top-10 for ميثة / نورة in gold and measuring them confirmed
the causes were in the geometry, not the shading:
- mean stroke 1.0–1.7 mm on 8–15 mm names (up to 0.135 of the height; fine name jewellery sits
  near 0.08): a fixed positive buffer on top of typographic weights melted the letters;
- attachment loops floated beside the bounding box and were reached by a bridge stalk
  ("ring on a stick");
- frames connected to the name with straight spokes; plates were sharp slabs;
- dots were sub-millimetre specks joined by thin necks, reading as spikes.

## Decision
Deterministic construction changes in `engines/geometry_engine.py` (no AI, no new fonts):
1. **Stroke normalisation, never eroding**: the buffer is the larger of (a) what lifts the
   thinnest hairline/neck class present (probed with coarse openings) to the 0.85 mm neck
   minimum and (b) what brings a light face toward the 0.082·height mean-stroke target; the
   recipe's `stroke_delta_mm` is the upper bound. Two rejected variants, both measured: erosion
   of heavy faces opened the joins between letters (محمد 39→15 valid of 48), and a local
   "thicken only the thin parts" pass seeded slivers next to neighbours (ميثة 47→28). Lighter
   Kufi comes from a lighter font instance instead: Cairo recipes use `wght=300`.
2. **Fused attachments** (`attachment_ring_centers`): the bail sits on the top of the central
   band of the main body (never a side ascender, a dot, or a bar corner); chain rings sit on the
   true ends of the metal in the hanging band. Rings overlap the metal by 85 % of their wall —
   soldered, not bridged.
3. **Frames without spokes**: the name is inscribed so its farthest point kisses the medallion's
   inner wall (30 % of a heavier 1.1 mm ring); rectangular frames fuse with the name's ends;
   plates get rounded corners; the underline bar fuses into the letter bottoms.
4. **Dots normalised** to crisp circles ≥ 1.25 mm before bridging (identity-preserving: the dot
   is still the source glyph's dot). Bridges and frame junctions get solder fillets (the
   region within reach of both parts) so a bar meeting a curved tail never leaves a neck
   under the minimum.
6. **Ranking**: stroke weight joins the visual heuristic (weight fit 1.0 at ≤0.10·height, 0 at
   0.18) so the lighter, more jewellery-like candidates surface in the ten proofs.
5. Render: crisper bevel (0.06–0.16 mm) and lighter shadow so metal edges read as edges.

## Consequences
- Every geometry hash moved. `tests/golden/golden_visual.json` was regenerated deliberately
  (`e2e/generate_golden.py`) on the owner's explicit rejection of the previous look; the
  seven-name text-truth fixture is untouched. Identity proofs, validator and export paths are
  unchanged.
- Validity of the internal pool improved everywhere (of 48: ميثة 34→45, نورة 27→42, محمد 39→42,
  seven names 32→34, long phrase 24→35); ten valid diverse proofs for every golden text
  (asserted). Generation costs ~1.7× the previous time (morphological probes per candidate;
  ~6–8 s per name on this box).
- Regression: `tests/test_jewellery_realism.py` (stroke ratio band, fused rings, ring never
  pierced, dot normalisation, hairline-only thickening).
- Still honest: this is parametric lettering from licensed print fonts, not hand-drawn
  jewellery calligraphy; a purchased jewellery-grade face (ADR-0004, `scripts/add_font.py`)
  would raise the ceiling further.
