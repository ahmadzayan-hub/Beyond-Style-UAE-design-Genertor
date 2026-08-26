# Font Capability, Rights and Glyph Variants

What we advertise must equal what we can render. This document is generated
from, and kept honest by, `backend/tests/test_font_capability.py`.

## Vendored fonts

All nine are SIL OFL 1.1 with the licence file vendored beside the binary in
`backend/app/assets/fonts/`. `file_sha256` is recorded in
`backend/app/fonts/fonts.json` and re-verified against the binary by
`test_recorded_hash_matches_the_binary_on_disk`.

| font_id | family | version | script_family | style_influence | production_capability |
|---|---|---|---|---|---|
| `amiri-regular` | Amiri | 1.002 | naskh | — | NASKH |
| `scheherazade-new` | Scheherazade New | 4.500 | naskh | — | NASKH |
| `cairo` | Cairo | 3.130 | modern_arabic | kufi | MODERN_ARABIC |
| `aref-ruqaa` | Aref Ruqaa | 1.003 | ruqaa | — | RUQAA |
| `reem-kufi` | Reem Kufi | 2.000 | kufi | — | KUFI |
| `noto-nastaliq-urdu` | Noto Nastaliq Urdu | 3.009 | nastaliq | — | NASTALIQ |
| `tajawal` | Tajawal | 1.700 | modern_arabic | — | MODERN_ARABIC |
| `katibeh` | Katibeh | 1.0010g | naskh | thuluth | **THULUTH_INFLUENCED** |
| `lemonada` | Lemonada | 4.005 | naskh | diwani | **DIWANI_INFLUENCED** |

**Bridge fonts.** Katibeh and Lemonada are Naskh-based. They approximate the
*feel* of Thuluth and Diwani and must never be presented as those scripts —
enforced by `test_bridge_fonts_are_never_labelled_as_the_classical_script`.

**Provenance caveat.** Binaries were retrieved from the `google/fonts`
distribution at ref `main` on 2026-08-26. `api.github.com` is blocked by this
environment's egress proxy, so the upstream commit SHA could not be resolved:
each record carries `upstream_commit: null` with
`upstream_commit_status: "UNRESOLVED_GITHUB_API_BLOCKED"`. Integrity is
anchored on our own recorded `file_sha256`, not on an upstream ref.

## Four separate concepts

| concept | question it answers |
|---|---|
| `script_family` | which script system the font genuinely **is** |
| `font_family` | the typeface |
| `style_influence` | a classical style it merely leans toward |
| `production_capability` | what may be **promised to a customer** |

`SCRIPT_FAMILIES` in `app/ai/design_dna.py` is a **classification** vocabulary
and is deliberately unchanged: Reference Intelligence must stay free to label a
customer's photo as Diwani, because that is what the photo is. What we *build*
is decided separately by `app/fonts/capabilities.py`.

## Script coverage

| script family | status | fonts |
|---|---|---|
| naskh | REAL | amiri-regular, scheherazade-new |
| ruqaa | REAL | aref-ruqaa |
| kufi / geometric_kufi | REAL | reem-kufi |
| nastaliq | REAL | noto-nastaliq-urdu |
| modern_arabic / minimal | REAL | cairo, tajawal |
| latin_script | REAL | Latin coverage of the above |
| **thuluth, thuluth_jali** | **LICENSE_REQUIRED** | influenced only: katibeh |
| **diwani, diwani_jali** | **LICENSE_REQUIRED** | influenced only: lemonada |
| farsi | LICENSE_REQUIRED | influenced only: noto-nastaliq-urdu |
| square_kufi, monogram | PARAMETRIC_ONLY | a construction, not a typeface |

A request for a true classical script we do not hold returns
`STYLE_NOT_AVAILABLE` with the closest licensed alternative named — it is never
silently served by Amiri (`test_diwani_request_is_never_silently_served_by_amiri`).

### Adding a licensed true Diwani/Thuluth later

Data only, no code change: vendor the font with its licence, add a registry
record with `production_capability: "DIWANI"` and
`rights_status: "COMMERCIAL_LICENSED"`, and add `"DIWANI"` to that family's
`true` list in `SCRIPT_REQUIREMENTS`. Proven by
`test_registry_accepts_a_future_licensed_font_without_code_changes`.

## Rights gate

`VERIFIED_OPEN_SOURCE`, `COMMERCIAL_LICENSED`, `CUSTOMER_OWNED` may reach
commercial production export. `INTERNAL_ONLY` and `UNKNOWN_RIGHTS` may not —
unchanged by this slice, and re-asserted as a rule rather than as a fact about
today's registry.

## OpenType discovery and the safety gate

`app/fonts/ot_discovery.py` enumerates GSUB/GPOS features, variation axes and
script/language systems **from the font binary**. Nothing is hand-written:
`test_every_registered_feature_exists_in_the_font_binary` fails if a feature set
claims a tag the font does not have.

Always-on shaping features (`init`, `medi`, `fina`, `isol`, `rlig`, `ccmp`,
`mark`, `mkmk`, `curs`, `kern`, `locl`, `rvrn`, `rclt`) are never offered as
variants — disabling them would break joining, not restyle letters. Digit and
fraction features are excluded as non-letterform.

Each discovered feature is then shaped with HarfBuzz over the fixed corpus
(`ع نورة ميثة محمد سلطان فاطمة حامد خالد مهرة` + one phrase + the seven-name
case). A feature passes only if it introduces no `.notdef`, drops no source
character, and still lets the glyph clusters **reconstruct the source text**.
52 features were discovered and 52 passed; regenerate with:

```
python3 scripts/discover_font_features.py --write
```

## Glyph Variant Library

59 feature sets: 52 `DISCOVERED_FROM_FONT_TABLES` and 7 pre-existing
`CURATED_VERIFIED_AGAINST_FONT_TABLES`. Each exposes `font_id`, `feature_tags`,
supported values, label, provenance, `safe_for_production` and affected scripts
via `GET /api/fonts/{font_id}/variants`. Reem Kufi's `cv01–cv03` character
variants and Aref Ruqaa's `ss01–ss08` + `jalt` are real, selectable axes.

## Fonts are raw material, not the design

A font supplies letterform outlines. The jewellery is still produced by the
deterministic composer — kashida, swashes, tails, stacking, dot strategy,
bridges, negative space, frames, loops and product topology. The new families
are kept **out of the default candidate pool** (`app/data/script_recipes.json`,
selected on demand) so the ranked-10 Golden Path and its immutable golden
fixture are unchanged.

## Benchmark evidence

`python3 scripts/font_benchmark.py` → `docs/evidence/font-capability/`
(`benchmark.json` plus a proof SVG per family). Every font passes shaping,
source-text identity, SVG generation, licence and integrity on all five
benchmark inputs. Residual `manufacturing_pass` failures are `OVERSIZE` on the
seven-name string at a fixed target height — the documented "blocked, not
repaired" behaviour, which the pre-existing families show too.
