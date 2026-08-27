#!/usr/bin/env python3
"""P2 curation analysis and customer validation pack.

Reads the append-only human review log and derives aesthetic and commercial
recommendations from it — and from nothing else. Where evidence is thin the
output says INSUFFICIENT_HUMAN_REVIEW_EVIDENCE. No rating, decision,
customer answer or AI score is ever invented here.

Usage: python3 scripts/curation_analysis.py [--write]
"""
from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.base import session_factory  # noqa: E402
from app.services.curation_analysis import (  # noqa: E402
    INSUFFICIENT, SIGNAL_DIMENSIONS, best_aesthetic_family_for_product,
    best_commercial_family_for_product, commercial_curation,
    derive_aesthetic_signals, golden_pattern_validation, load_review_evidence,
    overall_best_aesthetic_family, product_comparison_readiness,
    review_quality_check, threshold_audit,
)
from app.services.customer_validation import (  # noqa: E402
    PRICE_BANDS, WOULD_BUY, best_customer_family, customer_signals,
    select_customer_pack,
)
from app.services.review_items import generate_review_pack  # noqa: E402

REVIEW_OUT = ROOT / "docs" / "evidence" / "human-aesthetic-review"
CUSTOMER_OUT = ROOT / "docs" / "evidence" / "customer-validation"
PROOFS = CUSTOMER_OUT / "proofs"


def _engineering_best_family() -> dict:
    """The existing engineering ranking, carried through unchanged and still
    labelled ENGINEERING_ONLY so it is never mistaken for taste."""
    path = ROOT / "docs" / "evidence" / "aesthetic-curation" / "scores.json"
    if not path.is_file():
        return {"status": "NOT_GENERATED"}
    data = json.loads(path.read_text())
    return {
        "status": "DERIVED",
        "basis": "ENGINEERING_ONLY",
        "note": "Measured geometry only. Carries no aesthetic or commercial meaning.",
        "by_product": data.get("best_font_per_product", {}),
    }


def _proof_svg(item: dict) -> str:
    w, h = item["proof_view"]
    pad = max(w, h) * 0.08
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} '
        f'{w + 2 * pad} {h + 2 * pad}" width="420" height="300">'
        f'<rect x="{-pad}" y="{-pad}" width="{w + 2 * pad}" height="{h + 2 * pad}" fill="#fff"/>'
        f'<path d="{item["proof_path_d"]}" fill="#111" fill-rule="evenodd"/></svg>'
    )


def _review_board(pack: dict) -> str:
    """Customer-facing board. Style words only — no font ids, no OpenType
    tags, no axis numbers, no manufacturing internals."""
    cards = []
    for n, item in enumerate(pack["items"], start=1):
        style = html.escape(item["customer_style"] or "—")
        cards.append(f"""
    <article class="card">
      <div class="proof">{_proof_svg(item)}</div>
      <h2>#{n} · {html.escape(item['product'].replace('_', ' '))}</h2>
      <p class="style">{style}</p>
      <p class="text" dir="rtl">{html.escape(item['source_text'])}</p>
      <p class="code">ID {html.escape(item['item_id'][:8])}</p>
    </article>""")

    buy = "".join(f'<label><input type="radio" name="buy-N"> {b}</label>' for b in WOULD_BUY)
    bands = "".join(f"<option>{b.replace('_', ' ')}</option>" for b in PRICE_BANDS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Beyond Style — design review board</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px; color: #111; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }}
 .lede {{ color: #555; max-width: 60ch; margin: 0 0 24px; }}
 .grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }}
 .card {{ border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
 .proof {{ background: #fff; display: flex; justify-content: center; padding: 8px; }}
 .proof svg {{ width: 100%; height: auto; max-height: 260px; }}
 .card h2 {{ font-size: 15px; margin: 8px 12px 2px; }}
 .style {{ margin: 0 12px; font-size: 14px; color: #333; }}
 .text {{ margin: 4px 12px; font-size: 15px; }}
 .code {{ margin: 4px 12px 12px; font-size: 11px; color: #999; font-family: monospace; }}
 form {{ margin-top: 32px; border-top: 1px solid #ddd; padding-top: 20px; max-width: 60ch; }}
 label {{ display: block; margin: 6px 0; font-size: 14px; }}
 .row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
 @media print {{ form {{ page-break-before: always; }} }}
</style></head><body>
<h1>Beyond Style — design review board</h1>
<p class="lede">Please tell us what you think of these pieces. There are no right
answers, and your response is anonymous — we do not record your name or contact
details.</p>
<div class="grid">{''.join(cards)}</div>

<form>
  <h2>Rating form — one per design</h2>
  <p class="lede">Write the design number, then answer for that design.</p>
  <label>Design number <input type="text" name="design" style="width:6em"></label>
  <p><strong>Would you buy this?</strong></p>
  <div class="row">{buy}</div>
  <label>How premium does it look? (1–5) <input type="number" min="1" max="5"></label>
  <label>How readable is it? (1–5) <input type="number" min="1" max="5"></label>
  <label>How unique is it? (1–5) <input type="number" min="1" max="5"></label>
  <label>Which product would you want it as?
    <input type="text" placeholder="necklace, earring, ring…"></label>
  <label>What would you expect to pay? <select>{bands}</select></label>
  <label>Anything else? <textarea rows="3" style="width:100%"></textarea></label>
</form>
</body></html>
"""


def main(write: bool) -> int:
    items = generate_review_pack(max_per_product=4)
    session = session_factory()()
    try:
        evidence = load_review_evidence(session, items)
        quality = review_quality_check(session, items)
        signals = derive_aesthetic_signals(session, items)
        commercial = commercial_curation(session, items)
        audit = threshold_audit(items)
        readiness = product_comparison_readiness(session, items)
        aesthetic_family = best_aesthetic_family_for_product(session, items)
        commercial_family = best_commercial_family_for_product(session, items)
        overall_aesthetic = overall_best_aesthetic_family(session, items)
        golden = golden_pattern_validation(session, items)
        pack = select_customer_pack(session, items)
        cust_signals = customer_signals(session, items)
        cust_family = best_customer_family(session, items)
    finally:
        session.close()

    engineering_family = _engineering_best_family()
    from collections import Counter
    states = Counter(c["state"] for c in commercial)

    families = {
        "note": "Four distinct claims. They answer different questions and are "
                "never collapsed into one ranking.",
        "BEST_ENGINEERING_FAMILY": engineering_family,
        "BEST_AESTHETIC_FAMILY": {"basis": "HUMAN_REVIEW_ONLY", "by_product": aesthetic_family},
        "OVERALL_BEST_AESTHETIC_FAMILY": overall_aesthetic,
        "BEST_COMMERCIAL_FAMILY": {"basis": "HUMAN_REVIEW_ONLY", "by_product": commercial_family},
        "BEST_CUSTOMER_FAMILY": {"basis": "CUSTOMER_RESPONSES_ONLY", "by_product": cust_family},
    }

    if write:
        REVIEW_OUT.mkdir(parents=True, exist_ok=True)
        CUSTOMER_OUT.mkdir(parents=True, exist_ok=True)
        PROOFS.mkdir(parents=True, exist_ok=True)
        (REVIEW_OUT / "review-evidence.json").write_text(
            json.dumps(evidence, indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "review-quality-check.json").write_text(
            json.dumps(quality, indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "aesthetic-signals.json").write_text(
            json.dumps(signals, indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "commercial-curation.json").write_text(json.dumps(
            {"states": dict(states), "decisions": commercial}, indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "threshold-audit.json").write_text(
            json.dumps({"audit": audit, "comparison_readiness": readiness},
                       indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "best-families.json").write_text(
            json.dumps(families, indent=1, ensure_ascii=False) + "\n")
        (REVIEW_OUT / "golden-pattern-validation.json").write_text(
            json.dumps(golden, indent=1, ensure_ascii=False) + "\n")

        (CUSTOMER_OUT / "review-board.html").write_text(_review_board(pack), encoding="utf-8")
        for n, item in enumerate(pack["items"], start=1):
            (PROOFS / f"{n:02d}-{item['product']}-{item['item_id'][:8]}.svg").write_text(
                _proof_svg(item), encoding="utf-8")
        (CUSTOMER_OUT / "pack.json").write_text(json.dumps({
            "pack_id": pack["pack_id"], "size": pack["size"],
            "selection_basis": pack["selection_basis"], "note": pack["note"],
            "expert_reviewed_items": pack["expert_reviewed_items"],
            "product_spread": pack["product_spread"], "font_spread": pack["font_spread"],
            "items": [{"n": n, "item_id": i["item_id"], "product": i["product"],
                       "customer_style": i["customer_style"], "source_text": i["source_text"],
                       "width_mm": i["width_mm"], "height_mm": i["height_mm"]}
                      for n, i in enumerate(pack["items"], start=1)],
        }, indent=1, ensure_ascii=False) + "\n")
        (CUSTOMER_OUT / "customer-responses.json").write_text(json.dumps({
            "status": "NO_CUSTOMER_RESPONSES_RECORDED" if not cust_signals["total_responses"]
            else "IN_PROGRESS",
            "question_model": {
                "would_buy": list(WOULD_BUY), "premium_feel": "1-5",
                "readability": "1-5", "uniqueness": "1-5",
                "preferred_product": "free text", "price_band": list(PRICE_BANDS),
            },
            **cust_signals,
        }, indent=1, ensure_ascii=False) + "\n")

    print(f"human reviews:        {evidence['total_reviews']} "
          f"({evidence['unreviewed_items']} items unreviewed)")
    print(f"decisions:            {evidence['decisions']}")
    print(f"overall confidence:   {evidence['overall_confidence']}")
    print(f"commercial states:    {dict(states)}")
    print(f"retired rule:         {audit['retired_rule']['status']}")
    ready = sum(1 for v in readiness.values() if v['status'] == 'PRODUCT_COMPARISON_READY')
    print(f"comparison ready:     {ready}/{len(readiness)} products")
    print(f"overall aesthetic:    {overall_aesthetic['status']}")
    for name in ("BEST_AESTHETIC_FAMILY", "BEST_COMMERCIAL_FAMILY", "BEST_CUSTOMER_FAMILY"):
        derived = sum(1 for v in families[name]["by_product"].values()
                      if v.get("status") == "DERIVED")
        print(f"{name:24} {derived}/{len(families[name]['by_product'])} products derived")
    print(f"golden validation:    {golden['verdict']} ({golden['predictive_or_historical']})")
    print(f"customer pack:        {pack['size']} items · basis {pack['selection_basis']}")
    print(f"customer responses:   {cust_signals['total_responses']}")
    if not write:
        print("\n(dry run — pass --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
