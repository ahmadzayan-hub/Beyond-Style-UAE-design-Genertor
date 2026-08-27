"""Customer validation pack — real customers reacting to real proofs.

Kept deliberately apart from expert review. A customer answers "would I buy
this"; an Art Director answers "is this well made". Averaging the two would
destroy the meaning of both, so the responses live in their own table and
`BEST_CUSTOMER_FAMILY` is derived only from them.

Selection honesty: with no expert reviews recorded, the pack cannot be
"human-preferred". It is selected on manufacturing pass plus diversity, and
`selection_basis` says exactly that rather than implying curation that has
not happened.
"""
from __future__ import annotations

import hashlib
import statistics
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from .curation_analysis import INSUFFICIENT, confidence_for
from .review_workflow import HARD_GATES, latest_review

WOULD_BUY = ("yes", "maybe", "no")
PRICE_BANDS = ("under_300_aed", "300_600_aed", "600_1200_aed", "over_1200_aed", "unsure")

#: Minimum responses before a customer-derived claim is made at all.
MIN_RESPONSES_PER_ITEM = 5
MIN_RESPONSES_FOR_FAMILY_CLAIM = 10


class ResponseRejected(ValueError):
    """A customer response that cannot be recorded as given."""


def pack_id_for(item_ids: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(item_ids)).encode()).hexdigest()[:16]


def select_customer_pack(session: Session, items: list[dict],
                         target: int = 15, max_per_product: int = 2) -> dict:
    """Choose 12–18 items for customer testing.

    Only manufacturing-passing items are eligible — a customer must never be
    asked to react to something the workshop cannot make. Expert-approved
    items are preferred WHERE THEY EXIST; with none recorded the basis is
    stated plainly rather than dressed up as curation."""
    eligible = [i for i in items if all(i["engineering"].get(g) for g in HARD_GATES)]
    expert_approved: set[str] = set()
    for item in eligible:
        review = latest_review(session, item["item_id"])
        if review and review.decision in ("APPROVE", "ALLOW"):
            expert_approved.add(item["item_id"])

    # Approved first (when any exist), then Golden-relevant, then wider
    # material margin — all deterministic.
    eligible.sort(key=lambda i: (
        i["item_id"] not in expert_approved,
        not i["golden_production_pattern"],
        -(i["engineering"].get("min_material_width_mm") or 0),
        i["item_id"],
    ))

    per_product: Counter = Counter()
    per_font: Counter = Counter()
    chosen: list[dict] = []
    # Two passes: the first caps each font family so one face cannot fill
    # the board; the second tops up to target if the cap left us short.
    for font_cap in (2, 99):
        for item in eligible:
            if len(chosen) >= target:
                break
            if item in chosen:
                continue
            product = item["product"]
            font_id = item["technical"]["font_id"]
            if per_product[product] >= max_per_product or per_font[font_id] >= font_cap:
                continue
            chosen.append(item)
            per_product[product] += 1
            per_font[font_id] += 1

    return {
        "pack_id": pack_id_for([i["item_id"] for i in chosen]),
        "items": chosen,
        "size": len(chosen),
        "selection_basis": (
            "EXPERT_APPROVED_FIRST" if expert_approved
            else "MANUFACTURING_PASS_AND_DIVERSITY_ONLY"
        ),
        "expert_reviewed_items": len(expert_approved),
        "note": (
            "No expert aesthetic review exists yet, so this pack is NOT "
            "aesthetically curated. It is a manufacturable, diverse sample."
            if not expert_approved else
            "Expert-approved items were preferred, then diversity applied."
        ),
        "product_spread": dict(per_product),
        "font_spread": dict(per_font),
    }


def record_customer_response(
    session: Session, *, item_id: str, pack_id: str, respondent_token: str,
    would_buy: str, premium_feel: int, readability: int, uniqueness: int,
    preferred_product: str | None = None, price_band: str | None = None,
    comment: str | None = None,
) -> m.CustomerValidationResponse:
    if would_buy not in WOULD_BUY:
        raise ResponseRejected(f"would_buy must be one of {WOULD_BUY}")
    for name, value in (("premium_feel", premium_feel), ("readability", readability),
                        ("uniqueness", uniqueness)):
        if not (isinstance(value, int) and 1 <= value <= 5):
            raise ResponseRejected(f"{name} must be an integer 1-5; got {value!r}")
    if price_band is not None and price_band not in PRICE_BANDS:
        raise ResponseRejected(f"price_band must be one of {PRICE_BANDS}")
    if not respondent_token or not respondent_token.strip():
        raise ResponseRejected("A respondent token is required to group answers.")

    row = m.CustomerValidationResponse(
        item_id=item_id, pack_id=pack_id, respondent_token=respondent_token.strip(),
        would_buy=would_buy, premium_feel=premium_feel, readability=readability,
        uniqueness=uniqueness, preferred_product=preferred_product,
        price_band=price_band, comment=comment,
    )
    session.add(row)
    session.flush()
    return row


def customer_signals(session: Session, items: list[dict]) -> dict:
    """Per-item and per-family customer signals. Never mixed with expert
    scores — a separate question deserves a separate answer."""
    responses = list(session.execute(select(m.CustomerValidationResponse)).scalars())
    meta = {i["item_id"]: i for i in items}
    by_item: dict[str, list] = defaultdict(list)
    for r in responses:
        by_item[r.item_id].append(r)

    per_item = {}
    for item_id, rows in by_item.items():
        buy = Counter(r.would_buy for r in rows)
        per_item[item_id] = {
            "responses": len(rows),
            "respondents": len({r.respondent_token for r in rows}),
            "would_buy_yes_rate": round(buy["yes"] / len(rows), 3),
            "premium_feel": round(statistics.fmean(r.premium_feel for r in rows), 3),
            "readability": round(statistics.fmean(r.readability for r in rows), 3),
            "uniqueness": round(statistics.fmean(r.uniqueness for r in rows), 3),
            "price_bands": dict(Counter(r.price_band for r in rows if r.price_band)),
            "sufficient": len(rows) >= MIN_RESPONSES_PER_ITEM,
        }

    by_family: dict[tuple[str, str], list] = defaultdict(list)
    for item_id, rows in by_item.items():
        item = meta.get(item_id)
        if item:
            by_family[(item["product"], item["technical"]["font_id"])].extend(rows)

    per_product: dict[str, list] = defaultdict(list)
    for (product, font_id), rows in by_family.items():
        per_product[product].append({
            "font_family": font_id,
            "responses": len(rows),
            "respondents": len({r.respondent_token for r in rows}),
            "would_buy_yes_rate": round(
                sum(1 for r in rows if r.would_buy == "yes") / len(rows), 3),
            "premium_feel": round(statistics.fmean(r.premium_feel for r in rows), 3),
            "confidence": confidence_for(len(rows), len({r.respondent_token for r in rows})),
        })

    return {
        "basis": "CUSTOMER_RESPONSES_ONLY",
        "excluded_inputs": ["expert human review scores", "engineering", "AI advisory"],
        "total_responses": len(responses),
        "per_item": per_item,
        "per_product_family": dict(per_product),
    }


def best_customer_family(session: Session, items: list[dict]) -> dict:
    """BEST_CUSTOMER_FAMILY per product, or INSUFFICIENT with what's needed."""
    signals = customer_signals(session, items)
    out = {}
    for product in sorted({i["product"] for i in items}):
        candidates = signals["per_product_family"].get(product, [])
        eligible = [c for c in candidates if c["responses"] >= MIN_RESPONSES_FOR_FAMILY_CLAIM]
        if not eligible:
            out[product] = {
                "status": INSUFFICIENT,
                "responses_available": sum(c["responses"] for c in candidates),
                "required_responses_per_family": MIN_RESPONSES_FOR_FAMILY_CLAIM,
            }
            continue
        eligible.sort(key=lambda c: (-c["would_buy_yes_rate"], -c["premium_feel"],
                                     c["font_family"]))
        out[product] = {"status": "DERIVED", "product": product, **eligible[0]}
    return out
