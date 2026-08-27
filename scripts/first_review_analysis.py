#!/usr/bin/env python3
"""P4 — first human-review wave analysis.

Derives only what the append-only review log supports. With zero reviews it
produces the same deliverables with every claim honestly blocked, so that
re-running after real reviews land yields the real analysis with no code
change.

Usage: python3 scripts/first_review_analysis.py [--write]
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.base import session_factory  # noqa: E402
from app.services.curation_analysis import (  # noqa: E402
    INSUFFICIENT, agreement_report, best_aesthetic_family_for_product,
    best_commercial_family_for_product, bracelet_coverage_gap,
    composition_diversity_audit, engineering_vs_human_comparison,
    golden_preliminary_signal, overall_claim_fairness,
    product_comparison_readiness, verify_review_evidence,
)
from app.services.review_items import build_wave_1  # noqa: E402

REVIEW_OUT = ROOT / "docs" / "evidence" / "human-aesthetic-review"
CURATION_OUT = ROOT / "docs" / "evidence" / "curation"


def _engineering_by_product() -> dict:
    path = ROOT / "docs" / "evidence" / "aesthetic-curation" / "scores.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text()).get("best_font_per_product", {})


def main(write: bool) -> int:
    wave = build_wave_1()
    items = wave["items"]
    session = session_factory()()
    try:
        evidence = verify_review_evidence(session, items)
        readiness = product_comparison_readiness(session, items)
        aesthetic = best_aesthetic_family_for_product(session, items)
        commercial = best_commercial_family_for_product(session, items)
        agreement = {
            i["item_id"]: agreement_report(session, i["item_id"])
            for i in items
            if i["item_id"] in set(evidence["reviews_per_item"])
        }
        golden = golden_preliminary_signal(session, items)
        overall = overall_claim_fairness(session, items)
    finally:
        session.close()

    engineering = _engineering_by_product()
    comparison = engineering_vs_human_comparison(engineering, aesthetic, commercial)
    bracelet = bracelet_coverage_gap(items)
    compositions = composition_diversity_audit(items)

    ready = [p for p, v in readiness.items() if v["status"] == "PRODUCT_COMPARISON_READY"]
    aes_winners = {p: v for p, v in aesthetic.items() if v.get("status") == "DERIVED"}
    com_winners = {p: v for p, v in commercial.items() if v.get("status") == "DERIVED"}
    disagreements = [a for a in agreement.values() if a.get("flag")]
    customer_claim = "INSUFFICIENT_CUSTOMER_EVIDENCE"

    matrix = {
        "wave": wave["wave"],
        "evidence": evidence,
        "comparison_readiness": readiness,
        "aesthetic_winners": aesthetic,
        "commercial_winners": commercial,
        "engineering_vs_human": comparison,
        "overall_best_aesthetic_family": overall,
        "golden_preliminary": golden,
        "bracelet_gap": bracelet,
        "composition_diversity": compositions,
        "best_customer_family": customer_claim,
    }

    if write:
        REVIEW_OUT.mkdir(parents=True, exist_ok=True)
        CURATION_OUT.mkdir(parents=True, exist_ok=True)
        (CURATION_OUT / "PRODUCT_COMPARISON_MATRIX.json").write_text(
            json.dumps(matrix, indent=1, ensure_ascii=False) + "\n")
        (CURATION_OUT / "REVIEWER_AGREEMENT_REPORT.json").write_text(json.dumps({
            "note": "Mean is never reported without median/min/max/spread and raw "
                    "values; critical disagreement is flagged, not averaged away.",
            "reviewed_items": len(agreement),
            "disagreement_flags": len(disagreements),
            "per_item": agreement,
        }, indent=1, ensure_ascii=False) + "\n")
        (CURATION_OUT / "FIRST_HUMAN_REVIEW_ANALYSIS.md").write_text(_analysis_md(
            wave, evidence, ready, aes_winners, com_winners, comparison,
            disagreements, bracelet, compositions, overall, golden), encoding="utf-8")
        (REVIEW_OUT / "first-wave-verification.json").write_text(
            json.dumps(evidence, indent=1, ensure_ascii=False) + "\n")

    print(f"review rows:        {evidence['total_review_rows']} "
          f"({len(evidence['distinct_reviewers'])} reviewers)")
    print(f"comparison ready:   {len(ready)}/{len(readiness)} "
          f"({', '.join(ready) if ready else 'none'})")
    print(f"aesthetic winners:  {len(aes_winners)}")
    print(f"commercial winners: {len(com_winners)}")
    print(f"disagreement flags: {len(disagreements)}")
    print(f"golden signal:      {golden['preliminary_signal']}")
    print(f"bracelet:           {bracelet['status']} "
          f"(+{bracelet['additional_manufacturable_families_required']} families needed)")
    print(f"overall claim:      {overall['status']}")
    print(f"customer claim:     {customer_claim}")
    if not write:
        print("\n(dry run — pass --write)")
    return 0


def _analysis_md(wave, evidence, ready, aes, com, comparison, disagreements,
                 bracelet, compositions, overall, golden) -> str:
    aes_rows = "\n".join(
        f"| {p} | {v['font_family']} | {v['mean_score']} | {v['independent_reviews']} "
        f"| {v['confidence']} |" for p, v in sorted(aes.items())
    ) or "| — | none derived | — | — | — |"
    comp_rows = "\n".join(
        f"| {p} | {v['scope']} |" for p, v in sorted(compositions.items()))
    return f"""# First Human Review Analysis ({wave['wave']})

**Status: {evidence['status']}** — {evidence['total_review_rows']} review rows from
{len(evidence['distinct_reviewers'])} reviewer(s) across
{evidence['distinct_reviewed_items']} of {wave['size']} wave items.

Nothing in this document is inferred, simulated or backfilled. With zero
reviews recorded, every derived claim below is blocked and says so.

## Comparison-ready products

{', '.join(ready) if ready else 'None. No product has three rival families each with two independent reviews.'}

## Aesthetic winners (human evidence only)

| product | family | human score | reviews | confidence |
|---|---|---|---|---|
{aes_rows}

Commercial winners derived: {len(com)}.

## Engineering vs human

{json.dumps({p: v['verdict'] for p, v in comparison.items()}, indent=1)}

## Reviewer disagreement

{len(disagreements)} item(s) flagged REVIEWER_DISAGREEMENT (critical dimension
spread >= 2). Disagreement is reported with raw values, never hidden by the mean.

## Golden pattern (preliminary only)

{golden['preliminary_signal']} — {golden['caveat']}

## Bracelet coverage gap

{bracelet['status']}: {len(bracelet['manufacturable_candidates'])} manufacturable
candidate(s), {len(bracelet['failing_candidates'])} failing.
**{bracelet['additional_manufacturable_families_required']} additional manufacturable
font families required** before a bracelet comparison is possible.

Proposal for a future generation slice (no items generated in this run):
sweep bracelet-envelope recipes (11×30mm) across the licensed families with the
connector strategies that already rescued necklace (`loops=left_right`,
`dot_strategy=bridge`, stroke 0.35–0.45), validate with the real mm gate, and
add the survivors to the review corpus.

## Composition diversity

| product | comparison scope |
|---|---|
{comp_rows}

Every product currently compares one composition, so any winner is the best
FONT FAMILY at that composition — not the best jewellery composition.

## Overall family claim

{overall['status']} — {overall.get('fairness_note', '')}

## Customer claim

INSUFFICIENT_CUSTOMER_EVIDENCE (0 responses; expert reviewers are not customers).
"""


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
