# Arabic calligraphy sources — OpenType fonts and glyph libraries (2026-09-10)

Every Arabic style the customer can choose is backed by a **named OpenType source with a
verifiable licence**, or is honestly labelled as *inspired only* / *upload required*. The
engine never imitates a locked commercial font: a style is TRUE only when a rights-cleared
font of that script is in the registry, and *influenced* fonts are never presented as the
classical script (`tests/test_font_capability.py`, `test_source_registry.py`).

## Script families — status after the 2026-09-10 onboarding

| Style | Status | True sources | Inspired (bridge) sources | Customer-facing action |
|---|---|---|---|---|
| Thuluth / ثلث | **AVAILABLE** | amoshref-thulth | katibeh | Available |
| Jali Thuluth / ثلث جلي | **AVAILABLE** | amoshref-thulth | katibeh | Available |
| Diwani / ديواني | **INFLUENCED_ONLY** | — | lemonada | Inspired style only — install / upload the licensed source for the true script |
| Jali Diwani / ديواني جلي | **INFLUENCED_ONLY** | — | lemonada | Inspired style only — install / upload the licensed source for the true script |
| Ruq'ah / رقعة | **AVAILABLE** | aref-ruqaa, rakkas, aref-ruqaa-ink, aref-ruqaa-ink-bold | — | Available |
| Naskh / نسخ | **AVAILABLE** | amiri-regular, scheherazade-new, lateef, harmattan, noto-naskh-arabic, amiri-quran, markazi-text | — | Available |
| Traditional Kufi / كوفي تقليدي | **AVAILABLE** | reem-kufi, jomhuria, ruwudu, reem-kufi-ink, reem-kufi-fun | — | Available |
| Modern Kufi / كوفي حديث | **AVAILABLE** | kufam, changa, noto-kufi-arabic | reem-kufi, jomhuria, ruwudu, reem-kufi-ink, reem-kufi-fun | Available |
| Square Kufi / كوفي مربع | **PARAMETRIC_NOT_BUILT** | — | — | Geometric composer not built yet |
| Persian Nastaliq / نستعليق فارسي | **AVAILABLE** | noto-nastaliq-urdu, gulzar, mirza | — | Available |
| Levantine Nastaliq / نستعليق شامي | **INFLUENCED_ONLY** | — | noto-nastaliq-urdu, gulzar, mirza | Inspired style only — install / upload the licensed source for the true script |
| Fatimid foliated Kufi / كوفي فاطمي مورّق | **UPLOAD_REQUIRED** | — | — | Install / Upload Licensed Source |

**Thuluth is now TRUE** through *AMoshref Thulth* (Ali Moshref, SIL OFL 1.1 with Reserved
Font Name, licence embedded in the font's name table and shipped as
`AMoshrefThulth-OFL.txt`). Manufacturing sweep over the golden names: pass rate 1.00, two
recipes (bare 11 mm / 13 mm). **Diwani stays inspired-only**: the owner-supplied *Al Diwani
Al Majd* (1 & 2, 2015) carries no licence in its name table and the source page states
"we don't know any precise licence… use at your own risk"; under the rights rule it is
held out of the registry (see `docs/FONT_LICENSING.md`). Customers get Diwani-inspired
designs from the bridge fonts, clearly labelled.

## Registry — OpenType sources (all vendored files carry their licence text)

| font_id | Family | Script | Capability | Rights | Licence | Licence file | Arabic codepoints | Sweep score |
|---|---|---|---|---|---|---|---|---|
| `jomhuria` | Jomhuria | kufi | KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Jomhuria-OFL.txt` | 272 | 1.0 |
| `kufam` | Kufam | kufi | MODERN_KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Kufam-OFL.txt` | 273 | 0.8 |
| `noto-kufi-arabic` | Noto Kufi Arabic | kufi | MODERN_KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `NotoKufiArabic-OFL.txt` | 1028 | 1.0 |
| `qahiri` | Qahiri | kufi | GEOMETRIC_KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Qahiri-OFL.txt` | 100 | 1.0 |
| `reem-kufi` | Reem Kufi | kufi | KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ReemKufi-OFL.txt` | 118 | — |
| `reem-kufi-fun` | Reem Kufi Fun | kufi | KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ReemKufiFun-OFL.txt` | 119 | 1.0 |
| `reem-kufi-ink` | Reem Kufi Ink | kufi | KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ReemKufiInk-OFL.txt` | 119 | 1.0 |
| `ruwudu` | Ruwudu | kufi | KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Ruwudu-OFL.txt` | 131 | 1.0 |
| `almarai` | Almarai | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Almarai-OFL.txt` | 254 | 1.0 |
| `baloo-bhaijaan-2` | Baloo Bhaijaan 2 | modern_arabic | BOLD | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `BalooBhaijaan2-OFL.txt` | 164 | 1.0 |
| `beiruti` | Beiruti | modern_arabic | LOGO | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Beiruti-OFL.txt` | 342 | 1.0 |
| `blaka` | Blaka | modern_arabic | DISPLAY | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Blaka-OFL.txt` | 219 | 1.0 |
| `blaka-ink` | Blaka Ink | modern_arabic | DISPLAY | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `BlakaInk-OFL.txt` | 219 | 1.0 |
| `cairo` | Cairo | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Cairo-OFL.txt` | 102 | 1.0 |
| `changa` | Changa | modern_arabic | MODERN_KUFI | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Changa-OFL.txt` | 277 | 1.0 |
| `el-messiri` | El Messiri | modern_arabic | LOGO | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ElMessiri-OFL.txt` | 258 | 0.8 |
| `lalezar` | Lalezar | modern_arabic | DISPLAY | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Lalezar-OFL.txt` | 379 | 1.0 |
| `mada` | Mada | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Mada-OFL.txt` | 226 | 1.0 |
| `marhey` | Marhey | modern_arabic | DISPLAY | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Marhey-OFL.txt` | 121 | 0.8 |
| `tajawal` | Tajawal | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Tajawal-OFL.txt` | 67 | — |
| `vazirmatn` | Vazirmatn | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Vazirmatn-OFL.txt` | 355 | 0.6 |
| `zain` | Zain | modern_arabic | MODERN_ARABIC | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Zain-OFL.txt` | 252 | 0.8 |
| `amiri-quran` | Amiri Quran | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `AmiriQuran-OFL.txt` | 117 | 1.0 |
| `amiri-regular` | Amiri | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Amiri-OFL.txt` | 255 | 1.0 |
| `harmattan` | Harmattan | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Harmattan-OFL.txt` | 280 | 1.0 |
| `katibeh` | Katibeh | naskh | THULUTH_INFLUENCED | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Katibeh-OFL.txt` | 243 | — |
| `lateef` | Lateef | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Lateef-OFL.txt` | 303 | 1.0 |
| `lemonada` | Lemonada | naskh | DIWANI_INFLUENCED | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Lemonada-OFL.txt` | 101 | — |
| `markazi-text` | Markazi Text | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `MarkaziText-OFL.txt` | 301 | 1.0 |
| `noto-naskh-arabic` | Noto Naskh Arabic | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `NotoNaskhArabic-OFL.txt` | 1028 | 0.6 |
| `scheherazade-new` | Scheherazade New | naskh | NASKH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ScheherazadeNew-OFL.txt` | 256 | 1.0 |
| `gulzar` | Gulzar | nastaliq | NASTALIQ | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Gulzar-OFL.txt` | 123 | 1.0 |
| `mirza` | Mirza | nastaliq | NASTALIQ | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Mirza-OFL.txt` | 480 | 1.0 |
| `noto-nastaliq-urdu` | Noto Nastaliq Urdu | nastaliq | NASTALIQ | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `NotoNastaliqUrdu-OFL.txt` | 214 | — |
| `aref-ruqaa` | Aref Ruqaa | ruqaa | RUQAA | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ArefRuqaa-OFL.txt` | 111 | — |
| `aref-ruqaa-ink` | Aref Ruqaa Ink | ruqaa | RUQAA | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ArefRuqaaInk-OFL.txt` | 113 | 1.0 |
| `aref-ruqaa-ink-bold` | Aref Ruqaa Ink | ruqaa | RUQAA | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `ArefRuqaaInkBold-OFL.txt` | 114 | 1.0 |
| `rakkas` | Rakkas | ruqaa | RUQAA | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 | `Rakkas-OFL.txt` | 278 | 1.0 |
| `amoshref-thulth` | AMoshref Thulth | thuluth | THULUTH | VERIFIED_OPEN_SOURCE | SIL OFL 1.1 (Reserved Font Name AMoshref-Thulth) | `AMoshrefThulth-OFL.txt` | 646 | 1.0 |

Sweep score = share of the golden-name sweep (`scripts/sweep_font_recipes.py`) that passed
the real manufacturing validator; recipes with the best pass rate are what the generator
offers when a script is requested (`app/data/script_recipes.json`).

## Glyph libraries

- **Base glyphs** come from the OpenType `glyf/CFF` outlines of the fonts above, shaped
  with HarfBuzz (`init/medi/fina/isol`, `rlig/calt/liga`, mark positioning). Shaping of the
  golden names is verified per font at onboarding (`app/fonts/onboarding.py::shape_check`).
- **Glyph Variant Library** (`app/data/glyph_variants.json`): OpenType stylistic sets, dot
  styles (round / diamond / square / petal), swashes and kashida with identity remap —
  documented per font and curated (`CURATION_STATUS.md`).
- **Decorative symbols** (`app/engines/decorative`): ♥ and ornaments as parametric vectors,
  never text.
- **Composition archetypes** (`app/data/design_recipes.json`, `script_recipes.json`) and
  the multi-name layouts of the Vector Composition Engine (ADR-0006).

## How a new source is added (owner path)

```
python3 scripts/add_font.py --file Foundry.otf --font-id foundry-diwani --family "Foundry Diwani" \
  --license "Foundry EULA (product use)" --license-file EULA.txt --source-url https://foundry.example \
  --rights COMMERCIAL_LICENSED --script-family diwani --capability DIWANI --write
```
or `POST /api/admin/fonts` (multipart, admin token). Both inspect the binary (format, glyph
coverage, contextual features, embedding bits), shape the golden names, require the licence
text as evidence, and only a `VERIFIED_OPEN_SOURCE` / `COMMERCIAL_LICENSED` /
`CUSTOMER_OWNED` rights status activates production use.
