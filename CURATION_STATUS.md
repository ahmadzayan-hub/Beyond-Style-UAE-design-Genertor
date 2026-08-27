# Curation Status

**Generated from the append-only review log, not from assumptions.**
Regenerate: `python3 scripts/curation_analysis.py --write`

## Headline

| claim | status |
|---|---|
| Human aesthetic reviews recorded | **0** |
| Review items prepared | 36 across 9 products |
| Customer responses recorded | **0** |
| `BEST_ENGINEERING_FAMILY` | DERIVED (engineering only) |
| `BEST_AESTHETIC_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` (0/9 products) |
| `BEST_COMMERCIAL_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` (0/9 products) |
| `BEST_CUSTOMER_FAMILY` | `INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` (0/9 products) |
| Golden pattern predictive? | `UNDETERMINED` — no reviewed items to compare |

Nothing has been aesthetically approved. The machinery to derive these
claims is built and tested; the evidence it needs does not exist yet.

## What the four claims mean

They answer four different questions and are never collapsed into one
ranking:

- **BEST_ENGINEERING_FAMILY** — measured geometry. Says nothing about taste.
- **BEST_AESTHETIC_FAMILY** — from Art Director scores only
  (CalligraphicGrace, LetterformBeauty, Balance, Rhythm, NegativeSpace).
- **BEST_COMMERCIAL_FAMILY** — from Art Director scores only
  (CommercialAppeal, Originality).
- **BEST_CUSTOMER_FAMILY** — from anonymous customer responses only
  (would-buy rate, premium feel).

Engineering values, font metrics and AI advisory scores are structurally
excluded from the aesthetic and commercial signals — asserted by test, and
recorded in each output as `excluded_inputs`.

## Evidence thresholds

A family claim is only made when, for one (product, font family):

- at least **5** scored reviews, and
- across at least **3** distinct review items.

Confidence is `HIGH` only with two or more reviewers — one person's
consistent opinion is not consensus. Below threshold the answer is
`INSUFFICIENT_HUMAN_REVIEW_EVIDENCE` with the shortfall itemised, never a
number computed from too little data.

For customer claims: **10** responses per (product, family), **5** per item.

## Commercial curation (current)

| state | items |
|---|---|
| PRODUCTION_RECOMMENDED | 0 |
| COMMERCIAL_CANDIDATE | 0 |
| DESIGN_EXPERIMENT | 25 |
| HIDDEN | 11 |

All 11 HIDDEN are blocked on engineering grounds alone (hard gates), not on
taste. All 25 DESIGN_EXPERIMENT are awaiting review.

`PRODUCTION_RECOMMENDED` requires manufacturing pass, human APPROVE, no
critical dimension (Readability, JewellerySuitability, ProductFit) below 3,
Arabic identity pass and no hard-gate failure. Hard gates are read **before**
the review, so an approval can never open one.

## Customer validation pack

13 items ready at `docs/evidence/customer-validation/`
(`review-board.html`, printable `proofs/*.svg`, `pack.json`).

**Selection basis: `MANUFACTURING_PASS_AND_DIVERSITY_ONLY`.** With no expert
review recorded, this pack is *not* aesthetically curated — it is a
manufacturable, diverse sample, and it says so. Spread: at most 2 per product
across 7 products, at most 2 per font family across 7 families.

The board shows customer style words only. Font ids, OpenType tags, axis
values and manufacturing internals are absent — verified by test.

Responses are anonymous by construction: the table has no name, email, phone
or customer-id column, only an opaque grouping token, and it is append-only
at the database.

## Review quality

No contradictions, incomplete reviews, or wrongly-promoted items — because
there are no reviews. The checks run and report cleanly; they will become
meaningful once decisions exist. No reviewer decision is ever modified by
this analysis (`reviewer_decisions_modified: 0`).

## Next human action

1. Open `/admin/review` (needs `ADMIN_API_TOKEN`) or work through
   `docs/evidence/human-aesthetic-review/review-pack/*.svg`.
2. Aim for **5 scored reviews across 3+ items per (product, font family)**
   you care about — start with the products you sell most.
3. A second reviewer on the same items unlocks `HIGH` confidence.
4. Run the customer board with real customers; 10 responses per product
   family unlocks `BEST_CUSTOMER_FAMILY`.
5. Re-run `python3 scripts/curation_analysis.py --write`.
