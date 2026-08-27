# Curation Status

**Generated from the append-only review log, not from assumptions.**
Regenerate: `python3 scripts/curation_analysis.py --write`

## P4 — First-wave verification (latest run)

**The first review wave has NOT been reviewed.** Verified against the
append-only log before any derivation: 0 review rows, 0 reviewers, 0 customer
responses. Every §5–§12 claim is therefore blocked, and the analysis pipeline
(`python3 scripts/first_review_analysis.py --write`) emits that honestly:

| P4 claim | result |
|---|---|
| Comparison-ready products | 0 / 5 |
| `BEST_AESTHETIC_FAMILY_FOR_PRODUCT` | `NOT_COMPARISON_READY` everywhere |
| `BEST_COMMERCIAL_FAMILY_FOR_PRODUCT` | `NOT_COMPARISON_READY` everywhere |
| Engineering vs human | `NOT_COMPARABLE_NO_HUMAN_WINNER` everywhere |
| Golden pattern | `UNDETERMINED` (preliminary vocabulary only) |
| `OVERALL_BEST_AESTHETIC_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` |
| `BEST_CUSTOMER_FAMILY` | `INSUFFICIENT_CUSTOMER_EVIDENCE` |
| Bracelet | `BRACELET_COMPARISON_BLOCKED` (+2 manufacturable families needed) |
| Composition scope | `FONT_FAMILY_COMPARISON_ONLY` for every product |

P4 changes now in force:
- Critical dimensions expanded to **5** (Arabic correctness, Legibility,
  Product fit, Commercial appeal, Overall aesthetic quality) — done while zero
  reviews existed, so no recorded score changed meaning.
- Agreement reports now include the **median** and independent reviewer count
  per dimension alongside mean/min/max/spread/raw values.
- Golden analysis speaks only in preliminary-signal vocabulary
  (`PRELIMINARY_POSITIVE/NEGATIVE_SIGNAL`, `NO_OBSERVED_SIGNAL`, `UNDETERMINED`).
- The overall family claim is additionally blocked when family/product
  coverage is structurally unfair, even past the numeric threshold.

Deliverables: `docs/evidence/curation/FIRST_HUMAN_REVIEW_ANALYSIS.md`,
`PRODUCT_COMPARISON_MATRIX.json`, `REVIEWER_AGREEMENT_REPORT.json`.
Re-running the script after real reviews land produces the real analysis
with no code change.

## Threshold repair (P3)

The P2 evidence rule was **unsatisfiable by construction** and has been
retired, not quietly relaxed:

> ~~≥5 scored reviews across ≥3 **distinct items** per (product, family)~~
> → `STRUCTURALLY_IMPOSSIBLE_THRESHOLD`

The review pack deliberately carries **at most one item per font family per
product** for diversity. Measured: `max_items_per_product_family = 1` across
all 36 items. The distinct-item clause could therefore never be met, however
many reviews were entered — no aesthetic or commercial winner could ever have
been derived. That was a bug in the rule, not a high standard.

## Confidence model (replaces the old one)

**Per item** — how many independent people looked at it:

| reviews | verdict |
|---|---|
| 0 | `ITEM_NO_REVIEW` |
| 1 | `ITEM_LOW_CONFIDENCE` |
| 2 | `ITEM_MEDIUM_CONFIDENCE` |
| ≥3 with acceptable agreement | `ITEM_HIGH_CONFIDENCE` |

Three or more reviewers **who disagree on a critical dimension** stay at
MEDIUM. A reviewer revising their own opinion is still one person — only the
newest review per reviewer counts toward independence.

**Terminology corrected.** The earlier claim that "a second reviewer unlocks
HIGH confidence" was wrong and appeared in P2 docs and code. Two reviewers is
**MEDIUM**. Group coverage confidence is now driven by *how many different
people* looked, not by volume: nine reviews from one person is `LOW`.

**Per product** — `PRODUCT_COMPARISON_READY` requires ≥3 rival font families,
each with ≥2 independent reviews. Without rivals there is no comparison, only
a field of one.

`BEST_AESTHETIC_FAMILY_FOR_PRODUCT` = comparison ready · manufacturing pass ·
no Arabic-correctness issue · no hard-gate failure · no critical dimension
below 3 · highest human aesthetic score.

`BEST_COMMERCIAL_FAMILY_FOR_PRODUCT` = the above **plus** CommercialAppeal ≥4,
PremiumFeel ≥4, ProductFit ≥4.

`OVERALL_BEST_AESTHETIC_FAMILY` = evidence across ≥3 products, ≥6 independent
reviews total, no hard-gate failure.

`BEST_ENGINEERING_FAMILY` stays separate and unchanged.

## Review dimensions (12)

Arabic correctness · Legibility · Elegance · Visual balance · Premium feel ·
Uniqueness · Product fit · Commercial appeal · Wearability · Emotional appeal ·
Overall aesthetic quality · Would recommend to customer.

Critical: **Arabic correctness, Legibility, Product fit** — none may sit below
3 in anything recommended. The human Arabic-correctness score sits *alongside*
the deterministic identity proof; the hard gate still decides what may ship.

## Reviewer independence and agreement

The pack is **blinded**: prior reviewers' decisions, scores and names are
withheld until you have submitted for that item. Engineering state stays
visible — that is fact, not opinion. After submission, `GET
/api/admin/review/agreement/{item_id}` shows mean, min, max, spread and raw
values per dimension. A critical dimension differing by ≥2 points raises
`REVIEWER_DISAGREEMENT`; the mean is never shown without its spread.

Reviews remain append-only, timestamped, attributed internally, immutable.

## HUMAN_REVIEW_WAVE_1

13 items, awaiting review. **Not curated winners** — a diverse manufacturable
slate chosen so each product can actually reach comparison-ready.

| product | items | font families | can reach comparison-ready |
|---|---|---|---|
| necklace | 3 | amiri-regular, aref-ruqaa, scheherazade-new | yes |
| pendant | 3 | amiri-regular, aref-ruqaa, scheherazade-new | yes |
| single-letter earring | 3 | aref-ruqaa, noto-nastaliq-urdu, reem-kufi | yes |
| cufflink | 3 | amiri-regular, aref-ruqaa, cairo | yes |
| **bracelet** | **1** | cairo | **no** |

**Bracelet is blocked**: only 1 of its 4 corpus items passes manufacturing, so
it can field one family, not three. It cannot be made comparison-ready by
reviewing harder — it needs more manufacturable bracelet candidates, which is
new generation and out of scope for this slice.

Composition diversity *within* a product is 1 across the corpus (each product
carries a single composition). Also a generation question, not a review one.

## Current evidence

| claim | status |
|---|---|
| Human reviews recorded | **0** |
| Customer responses recorded | **0** |
| Products comparison-ready | **0 / 9** |
| `BEST_AESTHETIC_FAMILY` | `NOT_COMPARISON_READY` (0/9) |
| `BEST_COMMERCIAL_FAMILY` | `NOT_COMPARISON_READY` (0/9) |
| `OVERALL_BEST_AESTHETIC_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` |
| `BEST_CUSTOMER_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` (0/9) |
| `BEST_ENGINEERING_FAMILY` | DERIVED (engineering only) |
| Golden pattern predictive? | `UNDETERMINED` |
| Commercial curation | 0 RECOMMENDED · 0 CANDIDATE · 25 DESIGN_EXPERIMENT · 11 HIDDEN |

All 11 HIDDEN are blocked on engineering gates, not taste.

## Customer validation

The 13-item customer board is **unchanged** from P2 and remains completely
separate from expert review. `BEST_CUSTOMER_FAMILY` needs 10 genuine
responses per product family. No test or synthetic response counts.

## Next human action

1. Open `/admin/review` (needs `ADMIN_API_TOKEN`) and work
   **HUMAN_REVIEW_WAVE_1** — 13 items.
2. Get **two independent reviewers** through the 12 items in the four
   unblocked products. That makes necklace, pendant, single-letter earring
   and cufflink comparison-ready and unlocks their aesthetic winners.
3. A **third reviewer** raises those items to HIGH confidence, provided the
   critical dimensions agree.
4. For `OVERALL_BEST_AESTHETIC_FAMILY`, the same family needs coverage in ≥3
   products with ≥6 independent reviews.
5. Bracelet needs more manufacturable candidates before it can be compared —
   a generation slice, not a review one.
6. Re-run `python3 scripts/curation_analysis.py --write`.
