# Licensed fonts — buying and onboarding a true Thuluth / Diwani cut

The registry ships nine rights-cleared open fonts (SIL OFL). None is a true Thuluth or Diwani:
Katibeh and Lemonada are *influenced* faces and are always labelled that way to the customer.
Turning the "Thuluth (inspired)" chip into real Thuluth is a purchase decision plus a ten-minute
install. Nothing in the code needs to change.

## 1. What to buy (owner)
- A **commercial font license** whose EULA explicitly allows converting glyphs to outlines and
  using them in **physical products sold commercially** (often called a "product", "merchandise"
  or "commercial goods" license — a plain desktop license usually is *not* enough).
- Arabic coverage with **contextual OpenType features** (`init`/`medi`/`fina`, `rlig`, `mark`) —
  the onboarding kit refuses fonts that cannot join letters.
- Keep the **EULA and invoice** as text files; they are stored beside the font as license
  evidence and every production export records the font's SHA-256.
- Redistribution: if the EULA forbids redistributing the font file, pass `--no-redistribution`
  (the font stays server-side; outlines in exports are fine when the EULA allows products).

## 2. Onboard it (ten minutes)
```bash
python3 scripts/add_font.py \
  --file ~/fonts/FoundryThuluth.otf --font-id foundry-thuluth --family "Foundry Thuluth" \
  --license "Foundry EULA 2026 (desktop + product)" --license-file ~/fonts/Foundry-EULA.txt \
  --source-url https://foundry.example/thuluth --rights COMMERCIAL_LICENSED \
  --script-family thuluth --capability THULUTH --no-redistribution          # dry run
# read the report: usable=true, contextual_forms=true, shaping ok, no missing Arabic letters
python3 scripts/add_font.py ... --write                                    # copies + registers
cd backend && python3 -m pytest -q tests/test_seven_name_golden_fixture.py tests/test_font_capability.py
git add backend/app/fonts/fonts.json backend/app/assets/fonts && git commit -m "fonts: add licensed Thuluth"
```
For Diwani use `--script-family diwani --capability DIWANI`.

## 3. What happens automatically
- `production_capability_map()` reports `THULUTH: REAL`; the start-step chip stops saying
  "(inspired)" once the resolution outcome is `AVAILABLE`; the script's face receives the
  customer-choice ranking bonus and appears in the ten proofs.
- The identity proof (`verify_identity`) is re-run on the golden names through the real registry
  during `--write`; a font that fails it is not registered.
- The new font gets the next `diversity_index`, so no existing design is re-ranked.

## 4. What the kit refuses
`UNKNOWN_RIGHTS` / `INTERNAL_ONLY` rights, missing Arabic letters, fonts without contextual
forms, golden names shaping to `.notdef`, and duplicate `font_id`s.
