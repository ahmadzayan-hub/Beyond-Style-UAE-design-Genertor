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


## 2026-09-10 — owner-supplied fonts (arfonts.net downloads)

| File | Family (name table) | Licence evidence | Decision |
|---|---|---|---|
| `amoshref-thulth.ttf` | AMoshref-Thulth v0.1, Ali Moshref | OFL 1.1 in name IDs 13/14 + `OFL.txt` in the download, Reserved Font Name "AMoshref-Thulth" | **Vendored** as `amoshref-thulth` (`VERIFIED_OPEN_SOURCE`, capability THULUTH). OFL permits bundling and commercial use; the Reserved Font Name is not used for any modified version. |
| `aref-ruqaa-ink-bold.ttf` | Aref Ruqaa Ink Bold v1.008, Abdullah Aref | OFL 1.1 in name table + `OFL.txt`; Google Fonts family | **Vendored** as `aref-ruqaa-ink-bold` (`VERIFIED_OPEN_SOURCE`, capability RUQAA). |
| `al-diwani-al-majd.ttf`, `al-diwani-al-majd-2.ttf` (three zips, same 2015 family "الديواني المجد") | no designer, no licence fields | `about_this_font.txt`: "We don't know any precise license for this font… Use it at your own risk." | **Not vendored, not registered.** Unknown rights can never back production; it is not even used for previews because a preview would show the customer a style we cannot manufacture. If a licence is obtained (or the designer grants one in writing), onboard it with `scripts/add_font.py --rights COMMERCIAL_LICENSED --capability DIWANI`. |
| arfonts.net "Diwani Bent" (link only) | — | page not reachable from this environment (egress blocked); no file supplied | Not evaluated. Supply the file + its licence text and it goes through the same path. |
