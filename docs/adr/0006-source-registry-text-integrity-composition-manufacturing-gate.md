# ADR-0006 — Arabic Calligraphy Source Registry + Text Integrity Engine + Vector Composition Engine + Jewelry Manufacturing Gate (2026-09-05)

## Context
Owner specification ("BEYOND STYLE ARABIC JEWELRY DESIGNER", 33 sections) with the pipeline
**correct text → correct font → artistic composition → manufacturing**, and the instruction to
audit first, preserve every working feature, remove dead/duplicate architecture and implement
incrementally with tests. Audit findings that drove the design:
- Text truth already existed (NFC, HarfBuzz shaping, cluster-level identity proof) but nothing
  inspected the *input* for invisible/bidi/tatweel/presentation-form characters, and there was no
  single "TEXT INTEGRITY: PASS/FAIL" certificate carried to the version and the exports.
- Calligraphy styles were shown as locked chips ("Install / Upload Licensed Source") although 37
  rights-cleared OFL families were available to vendor; Thuluth/Diwani have no OFL source.
- Multi-name text (the seven-name acceptance case) was treated as one 202 mm line and produced
  0 valid candidates.
- Exports were SVG/DXF only, never re-imported, and readiness was a label rather than a ladder
  derived from facts.
- Designer refinement was recipe-only; no true vector operations existed, and a "repair" was a
  single hard-coded thicken.

## Decisions
1. **Text Integrity Engine** (`engines/text_integrity.py`): NFC only (never NFKC), inspection of
   the raw input (invisible/control/bidi/zero-width, tatweel, presentation forms, composition
   drift), rasm-group classification of differences (dot change, hamza change, diacritic change,
   character change, order), and `certify()` that binds source sha256 + shaping identity proof +
   outline issues + the text carried by the artefact into one verdict. A dot/hamza/taa-marbuta
   change is a FAIL by construction — ميثه can never be reported as ميثة. AI never touches text.
2. **Source Registry** (`fonts/registry.py`, `fonts/styles.py`, `fonts/onboarding.py`,
   `admin.py::POST /api/admin/fonts`): 37 vendored OFL fonts with capability tokens; a style
   catalogue with honest statuses (`AVAILABLE`, `INFLUENCED_ONLY`, `UPLOAD_REQUIRED`,
   `PARAMETRIC_NOT_BUILT`); uploaded private fonts live outside the public assets, are inspected
   (format, glyph coverage, shaping smoke test, licence declaration) and never served by URL.
   Thuluth/Diwani remain INFLUENCED_ONLY: the engine states it, it does not imitate a locked
   commercial font.
3. **Vector Composition Engine** (`engines/composition_engine.py`): every name is shaped and
   outlined once; six layouts (interwoven stack, family tree, oval, arch, circular, horizontal
   flow) only move/scale/tilt those vectors, weld them with solder fillets, add reinforced
   bridges, heal pinch points locally and solder two discreet upper chain rings whose holes are
   always clear of the letters. Identity proof covers the whole text through per-name offsets.
4. **Material system + weight from area** (`data/materials.json`, `services/materials.py`): 11
   materials with density, thickness limits, minimum bridge/stroke, process, finishes and
   allowances; weight = actual metal area × thickness × density, with target/tolerance and the
   thickness that reaches a target. Enamel is Visual Preview Only.
5. **Jewelry Manufacturing Gate** (`exporters/pdf_exporter.py`, `exporters/fidelity.py`,
   `services/jewelry_qa.py`, `services/readiness_ladder.py`): PDF joins SVG/DXF as a true-scale
   vector export; every export is re-imported and compared with the master vector (dimensions,
   part count, holes, area, symmetric difference, attachment holes) — the Export Fidelity Gate —
   and the verdict is stored on the export record and returned in `X-Export-Fidelity`. "JEWELRY
   QA: PASS/FAIL" explains each violation in plain Arabic/English. The readiness ladder
   (`DRAFT → TEXT_VERIFIED → DESIGN_VALID → INTERNALLY_APPROVED → EXPORT_VERIFIED →
   WORKSHOP_READY`) is derived from recorded facts only; approval is labelled INTERNAL_UI because
   there is no secure customer link yet.
6. **Vector edit operations** (`engines/vector_edit.py`, `POST /api/versions/{id}/vector-edit`
   + `/preview`, `GET /vector-ops`): translate/rotate/uniform scale/add bridge/add ring/union
   shape/cut shape on real mm polygons. Fail-safes: letters are protected (a cut that touches the
   confirmed text outline is refused, mirroring is refused because it reverses the reading
   direction), workshop minimums are enforced, bridges/rings must touch the design, results must
   be valid non-empty polygons. Ops are stored as a cumulative ordered list on the version and
   replayed on the deterministic base whenever the recipe is edited; a text change drops them
   (recorded) rather than carrying mm-anchored ops onto different letters. Node editing and a pen
   tool are listed as *not available* — never as clickable fakes.
7. **Real repair**: validator-proposed fixes become vector ops (bridges anchored inside both
   parts, rings rebuilt at workshop size); every repair option is dry-run and offered only when it
   reduces the manufacturing error count. The legacy thicken option remains as a recipe repair.

## Consequences
- One canonical vector master per version; SVG/DXF/PDF are proven equal to it before the
  workshop sees them.
- Multi-name pendants are first-class (composition class 9, loops `upper_left_right`, the shared
  `EXPECTED_LOOPS` map is used by edit/change-text/AI tools/workshop BOM — a hard-coded map in
  those paths previously raised on multi-name versions).
- Removed duplication: the two `/api/fonts/styles` routes were merged; hard-coded loop maps were
  replaced by the generator's single map; repair logic lives in one service function used by both
  the options and the apply endpoints.
- Secure customer approval links (added after the first acceptance run): single-use, expiring,
  bound to the geometry hash, retype-to-confirm, `approval_method=SECURE_LINK`; internal approvals
  stay labelled INTERNAL_UI.
- Not done (honest): OTP/identity check on the link holder, node/pen editing, Thuluth/Diwani true
  sources (need a licensed upload), server-side rendering of the actual-size preview at true DPI.
