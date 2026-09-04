# ADR-0004 — Reference study: arabicdesign.ai (owner request, 2026-09-04)

## Context
The owner shared arabicdesign.ai (a UAE company's AI Arabic-calligraphy generator, advertised to
GCC buyers) as the bar for "real jewellery design". The site itself is unreachable from this
build environment (egress blocked), so the study relies on its public descriptions and search
listings: the customer enters a name/phrase/prayer, picks a **script** (Naskh, Thuluth, Diwani,
Nastaliq, modern), picks a **visual direction**, applies **visual treatments** to turn plain
lettering into a finished-looking result, **refines**, then downloads **high-resolution or SVG**.
Pricing is per-credit per action. It is a design/art tool: no product, material, size, weight,
manufacturing or approval concepts.

## What we adopt (this slice)
1. **Script first.** The Golden Path start step now has a script picker (Naskh, Ruqaa, Kufi,
   Nastaliq, Modern, Thuluth-inspired, Diwani-inspired). The choice is resolved through the
   existing rights-gated capability map: an unlicensed true script returns
   `STYLE_NOT_AVAILABLE` with the closest licensed face and a customer-visible note — never a
   silent substitution or a false "Thuluth" label. The chosen script's curated recipes join the
   candidate pool (additive; the hint-less pool and its golden fixtures are unchanged) and its
   faces get a transparent ranking bonus so they reach the diverse top 10.
2. **Finished-looking pieces.** The 10 proofs and the studio 2D view render the customer's chosen
   metal (silver 925, 18K yellow/rose/white gold, platinum) with SVG gradients, a bevel
   (`feSpecularLighting`) and a soft shadow on a neutral studio ground — deterministic, no raster,
   no paid model, no credentials. The path data is byte-identical to the flat proof (tested), so
   the render can never drift from manufacturing truth; the agreement proof stays the dimensioned
   technical drawing.
3. **Metal chosen at the start** and carried as `material_preference` into the brief, the 3D
   viewer and the photoreal request.

## What we deliberately do not copy
- Raster-first output. Their deliverable is an image; ours is a manufacturable vector with mm,
  hashes, validation and a workshop pack. The metal render is presentation only.
- Generative "treatments" that may rewrite letterforms. Text truth stays deterministic (HarfBuzz
  shaping + identity proof); no treatment may alter spelling, dots or order.
- Their artwork or styles as assets. Nothing is traced or copied; only the product flow is a
  reference (CLAUDE.md: no third-party protected artwork).
- Per-action credits. Pricing here is the workshop's, on the approved production version.

## Consequences
- New API surface: `?material=` on both preview-SVG endpoints; `script_family` on the brief.
- Honest gaps that remain: no licensed true Thuluth/Diwani cut (a font purchase decision), and
  photoreal (GPT-Image-2) remains `PHOTOREAL_PREVIEW_UNAVAILABLE` until the owner runs it with
  credentials — the deterministic render is the always-available tier beneath it.
