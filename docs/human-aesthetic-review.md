# Human Aesthetic Review Workflow

## What this slice does and does not do

It builds the workflow, the review pack and the evidence. It makes **no
aesthetic decisions**. All 52 discovered OT features remain `EXPERIMENTAL`,
every review item reports `HUMAN_REVIEW_PENDING`, and `human-scores.json`
contains zero reviews — because no one at Beyond Style has reviewed anything
yet. The software prepares the work; the judgement is yours.

## The review unit

A review item is never a font. It is a **combination**:

```
font + OT features + axis values + product + composition + source text
     → rendered jewellery proof
```

The same face can be right for a pendant and wrong for a ring, so promotion
is product-scoped throughout (`product_scoped_states`). `item_id` is a
deterministic hash of that whole tuple, and `recipe_hash` pins a review to
the exact recipe that was looked at — a review cannot transfer to a
different design.

## The twelve human dimensions

CalligraphicGrace · LetterformBeauty · LuxuryFeel · OrnamentalPotential ·
Readability · Balance · Rhythm · NegativeSpace · JewellerySuitability ·
ProductFit · Originality · CommercialAppeal — each 1–5.

Human scores live in `design_reviews` and nowhere else. Deterministic
engineering scores and any AI advisory score are stored separately and are
never averaged together.

## Two modes

- **Quick curation** — APPROVE · ALLOW · EXPERIMENTAL · HIDE.
- **Deep review** — all twelve scores plus an optional note. A deep review
  missing any dimension, or with a score outside 1–5, is refused.

Every review must name its reviewer: decisions are attributable.

## What a human may and may not decide

Approval is permission to **show**, never permission to **ship something
unsafe**. `curation_for_item` evaluates the hard gates —
`arabic_identity_pass`, `manufacturing_pass`, `rights_pass` — **before** it
reads the review. A five-star APPROVE on an item failing any of them
resolves to `HIDDEN` with `reason: BLOCKED_BY_HARD_GATE` and the blocking
gate named. Verified over real HTTP, not only in unit tests.

`PRODUCTION_RECOMMENDED` requires all of: Arabic identity PASS, rights PASS,
manufacturing PASS, a human APPROVE, **and** no critical dimension
(Readability, JewellerySuitability, ProductFit) below 3. An APPROVE with a
weak critical dimension lands at `PRODUCTION_ALLOWED` with the weak
dimension recorded — beautiful but unreadable is not a recommendation.

## Append-only history

A review is a record of what a person judged at a moment. A revised opinion
is a **new row**; the earlier one survives. Enforced by database triggers on
UPDATE and DELETE, not only in the service layer. The current verdict is the
newest row for that item.

## Prioritisation

Not every combination is generated — that would waste the scarcest resource
here, an Art Director's attention. Items are ranked by manufacturing PASS,
then Golden Production relevance, then material margin, with an explicit
diversity rule (at most one item per font family per product) so the pack
cannot fill with variations of one face.

Products reviewed first: single-letter earring · pendant · necklace ·
cufflink · ring · bracelet · multi-name · medallion · openwork.

Corpus: ع نورة ميثة محمد فاطمة حامد سلطان خالد مهرة, plus the phrase
كن ما تبحث عنه في عيون الآخرين and the seven-name string. A font is never
judged on one word.

## Golden Production indicator

Items carry `golden_production_pattern` where a real manufactured,
customer-approved case applies: the Arabic pearl-earring case for
single-letter and drop earrings, the ADAM/OMAR case for necklace, pendant
and multi-name. The reviewer sees a "proven production pattern" badge. No
geometry is copied.

## AI advisory

`SKIPPED_NO_CREDENTIALS` in this environment — no `ANTHROPIC_API_KEY`, so
no advisory scores were produced and none were invented. When configured, an
advisory score is stored as `AI_ADVISORY_SCORE` beside the human scores and
**never inside them**. `curation_for_item` reads only the human decision, so
an advisory score cannot promote anything on its own.

## Customer-facing styles

Customers choose كلاسيكي · ناعم · فاخر · هندسي · حديث · انسيابي · تراثي ·
جريء. They never see `ss01`, `cv02`, `jalt` or `wght=625`. The review card
shows the customer style word as its label and keeps the OpenType/axis
detail in a collapsed technical block, asserted by test not to leak into the
headline payload.

## Best-family claims stay separate

The existing "best family by product" is **ENGINEERING_ONLY** and is
labelled as such. `BEST_AESTHETIC_FAMILY` and `BEST_COMMERCIAL_FAMILY`
cannot be produced until human reviews exist; they are deliberately absent
rather than approximated from engineering numbers.

## Admin screen

`/admin/review` — internal, admin-token gated. Large proof first, filters by
product / font / status / Golden-Case relevance, quick decision buttons and
an optional twelve-dimension scoring panel. A reviewer never opens raw JSON.

## Evidence

`docs/evidence/human-aesthetic-review/` — `review-items.json`,
`human-scores.json`, `curation-decisions.json`, `product-style-map.json`,
`AI-advisory.json`, `summary.md`, and `review-pack/<product>.svg` sheets.
Regenerate with `python3 scripts/human_review_pack.py --write`.

## True Diwani / Thuluth

Unchanged: `LICENSE_REQUIRED`, no font, asserted by test.
