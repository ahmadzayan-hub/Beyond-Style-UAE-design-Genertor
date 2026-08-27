"""Aesthetic and commercial curation derived from HUMAN review evidence.

The contamination this module exists to prevent: letting a manufacturing
score, a font metric or an AI guess stand in for taste. Every aesthetic and
commercial number here is computed from `design_reviews` rows — what people
actually said — and from nothing else. Engineering results appear only as
GATES (pass/fail), never as inputs to an aesthetic average.

When the evidence is thin, that is the answer. `best_family` returns
INSUFFICIENT_HUMAN_REVIEW_EVIDENCE rather than a confident-looking number
computed from two opinions.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from .review_workflow import (
    CRITICAL_DIMENSIONS, CRITICAL_SCORE_THRESHOLD, HARD_GATES,
    HUMAN_DIMENSIONS, PENDING, latest_review,
)

INSUFFICIENT = "INSUFFICIENT_HUMAN_REVIEW_EVIDENCE"

#: Evidence thresholds for a defensible "best family" claim. Deliberately
#: strict: a family claim shapes what the shop sells, so it should not rest
#: on one person glancing at one item.
MIN_DEEP_REVIEWS_FOR_CLAIM = 5      # scored reviews backing one (product, font)
MIN_DISTINCT_ITEMS_FOR_CLAIM = 3    # across at least this many review items
MIN_REVIEWERS_FOR_HIGH_CONFIDENCE = 2

#: Which human dimensions feed which derived signal. Each is a subset of the
#: twelve a reviewer actually scored — no dimension is invented.
SIGNAL_DIMENSIONS = {
    "human_aesthetic_score": [
        "CalligraphicGrace", "LetterformBeauty", "Balance", "Rhythm", "NegativeSpace",
    ],
    "commercial_appeal_score": ["CommercialAppeal", "Originality"],
    "premium_feel_score": ["LuxuryFeel", "OrnamentalPotential"],
    "readability_score": ["Readability"],
    "product_fit_score": ["ProductFit", "JewellerySuitability"],
}


def _text_category(text: str) -> str:
    words = text.split()
    if len(words) >= 5:
        return "multi_name"
    if len(words) > 1:
        return "phrase"
    return "single_letter" if len(text.strip()) <= 2 else "single_name"


def confidence_for(review_count: int, reviewer_count: int) -> str:
    """Confidence is about how much was seen and by how many people —
    never about how good the scores were."""
    if review_count == 0:
        return "NONE"
    if review_count < 3:
        return "LOW"
    if review_count < MIN_DEEP_REVIEWS_FOR_CLAIM or reviewer_count < MIN_REVIEWERS_FOR_HIGH_CONFIDENCE:
        return "MEDIUM"
    return "HIGH"


# ---------------------------------------------------------------------------
# 1. Load human review evidence
# ---------------------------------------------------------------------------

def load_review_evidence(session: Session, items: list[dict]) -> dict:
    """Everything the append-only review log actually contains."""
    reviews = list(session.execute(
        select(m.DesignReview).order_by(m.DesignReview.created_at)
    ).scalars())
    reviewed_items = {r.item_id for r in reviews}
    item_ids = {i["item_id"] for i in items}

    by_product: dict[str, dict] = defaultdict(lambda: {"reviews": 0, "reviewers": set(), "items": set()})
    by_font: dict[str, dict] = defaultdict(lambda: {"reviews": 0, "reviewers": set(), "items": set()})
    for r in reviews:
        for bucket, key in ((by_product, r.product), (by_font, r.font_id)):
            bucket[key]["reviews"] += 1
            bucket[key]["reviewers"].add(r.reviewer)
            bucket[key]["items"].add(r.item_id)

    def _coverage(bucket, universe):
        out = {}
        for key in universe:
            entry = bucket.get(key, {"reviews": 0, "reviewers": set(), "items": set()})
            out[key] = {
                "reviews": entry["reviews"],
                "reviewers": sorted(entry["reviewers"]),
                "items_reviewed": len(entry["items"]),
                "confidence": confidence_for(entry["reviews"], len(entry["reviewers"])),
            }
        return out

    products = sorted({i["product"] for i in items})
    fonts = sorted({i["technical"]["font_id"] for i in items})
    decisions = Counter(r.decision for r in reviews)

    missing = [p for p, c in _coverage(by_product, products).items() if c["reviews"] == 0]
    return {
        "total_reviews": len(reviews),
        "reviewed_items": len(reviewed_items & item_ids),
        "unreviewed_items": len(item_ids - reviewed_items),
        "distinct_reviewers": sorted({r.reviewer for r in reviews}),
        "decisions": {d: decisions.get(d, 0) for d in ("APPROVE", "ALLOW", "EXPERIMENTAL", "HIDE")},
        "coverage_by_product": _coverage(by_product, products),
        "coverage_by_font": _coverage(by_font, fonts),
        "overall_confidence": confidence_for(len(reviews), len({r.reviewer for r in reviews})),
        "missing_areas": missing,
        "status": PENDING if not reviews else "IN_PROGRESS",
    }


# ---------------------------------------------------------------------------
# 2. Review quality check — observations only, never edits
# ---------------------------------------------------------------------------

def review_quality_check(session: Session, items: list[dict]) -> dict:
    """Flags problems in the review record. Never modifies a decision:
    a reviewer's opinion is theirs, and a contradiction is something for a
    person to resolve, not for code to average away."""
    reviews = list(session.execute(select(m.DesignReview)).scalars())
    by_item: dict[str, list] = defaultdict(list)
    for r in reviews:
        by_item[r.item_id].append(r)

    contradictions, incomplete = [], []
    for item_id, rows in by_item.items():
        # Different reviewers landing on opposite ends for the same item.
        decisions = {r.decision for r in rows if r.decision in ("APPROVE", "HIDE")}
        if len(decisions) > 1:
            contradictions.append({
                "item_id": item_id,
                "decisions": [{"reviewer": r.reviewer, "decision": r.decision} for r in rows],
                "note": "Opposite verdicts on the same item — needs human resolution.",
            })
        # A deep review is only useful if it actually scored the dimensions.
        for r in rows:
            if r.review_mode == "deep" and (
                not r.scores or any(d not in (r.scores or {}) for d in HUMAN_DIMENSIONS)
            ):
                incomplete.append({"item_id": item_id, "reviewer": r.reviewer,
                                   "note": "Deep review missing dimensions."})

    by_item_meta = {i["item_id"]: i for i in items}
    thin = [
        product for product, cov in
        load_review_evidence(session, items)["coverage_by_product"].items()
        if cov["reviews"] < MIN_DEEP_REVIEWS_FOR_CLAIM
    ]

    # Integrity checks against the curation rules themselves.
    promoted_without_human, unsafe_allowed = [], []
    for item_id, rows in by_item.items():
        item = by_item_meta.get(item_id)
        if item is None:
            continue
        newest = sorted(rows, key=lambda r: r.created_at)[-1]
        gates_ok = all(item["engineering"].get(g) for g in HARD_GATES)
        if newest.decision in ("APPROVE", "ALLOW") and not gates_ok:
            unsafe_allowed.append({
                "item_id": item_id, "decision": newest.decision,
                "failed_gates": [g for g in HARD_GATES if not item["engineering"].get(g)],
                "resolved_state": "HIDDEN",
                "note": "Human decision recorded, but hard gates keep it hidden.",
            })
    for item in items:
        if item["item_id"] not in by_item and item.get("curation_state") in (
            "PRODUCTION_RECOMMENDED", "PRODUCTION_ALLOWED"
        ):
            promoted_without_human.append({"item_id": item["item_id"]})

    return {
        "contradictory_reviews": contradictions,
        "incomplete_reviews": incomplete,
        "products_with_thin_evidence": thin,
        "promoted_without_human_approval": promoted_without_human,
        "manufacturing_failing_but_allowed": unsafe_allowed,
        "reviewer_decisions_modified": 0,
        "note": "Observations only. No reviewer decision was altered.",
    }


# ---------------------------------------------------------------------------
# 3. Derive aesthetic signals — from human scores alone
# ---------------------------------------------------------------------------

def _signals_from(scored: list[dict]) -> dict:
    """Average each derived signal over its own human dimensions."""
    out = {}
    for signal, dims in SIGNAL_DIMENSIONS.items():
        values = [s[d] for s in scored for d in dims if d in s]
        out[signal] = round(statistics.fmean(values), 3) if values else None
    return out


def derive_aesthetic_signals(session: Session, items: list[dict]) -> dict:
    """Signals grouped by product, font family, composition, feature set and
    source-text category. Engineering values are deliberately absent."""
    reviews = [r for r in session.execute(select(m.DesignReview)).scalars() if r.scores]
    meta = {i["item_id"]: i for i in items}

    groups: dict[str, dict[str, list]] = {
        "product": defaultdict(list), "font_family": defaultdict(list),
        "composition": defaultdict(list), "feature_set": defaultdict(list),
        "source_text_category": defaultdict(list),
    }
    reviewers: dict[str, dict[str, set]] = {k: defaultdict(set) for k in groups}

    for r in reviews:
        item = meta.get(r.item_id, {})
        keys = {
            "product": r.product,
            "font_family": r.font_id,
            "composition": item.get("composition", "unknown"),
            "feature_set": r.feature_set,
            "source_text_category": _text_category(r.source_text),
        }
        for dimension, key in keys.items():
            groups[dimension][key].append(r.scores)
            reviewers[dimension][key].add(r.reviewer)

    result = {}
    for dimension, buckets in groups.items():
        result[dimension] = {
            key: {
                **_signals_from(scored),
                "review_count": len(scored),
                "reviewer_count": len(reviewers[dimension][key]),
                "confidence": confidence_for(len(scored), len(reviewers[dimension][key])),
            }
            for key, scored in buckets.items()
        }
    result["basis"] = "HUMAN_REVIEW_SCORES_ONLY"
    result["excluded_inputs"] = [
        "engineering suitability", "geometry metrics", "font metrics", "AI advisory",
    ]
    return result


# ---------------------------------------------------------------------------
# 4. Commercial curation
# ---------------------------------------------------------------------------

PRODUCTION_RECOMMENDED = "PRODUCTION_RECOMMENDED"
COMMERCIAL_CANDIDATE = "COMMERCIAL_CANDIDATE"
DESIGN_EXPERIMENT = "DESIGN_EXPERIMENT"
HIDDEN = "HIDDEN"


def commercial_class(item: dict, review) -> dict:
    """Four-way commercial classification.

    Hard gates are read first, so nothing a reviewer says can promote an
    item that fails Arabic identity, manufacturing or rights."""
    failed = [g for g in HARD_GATES if not item["engineering"].get(g)]
    if failed:
        return {"item_id": item["item_id"], "product": item["product"],
                "state": HIDDEN, "reason": "BLOCKED_BY_HARD_GATE",
                "failed_gates": failed}
    if review is None:
        return {"item_id": item["item_id"], "product": item["product"],
                "state": DESIGN_EXPERIMENT, "reason": PENDING, "failed_gates": []}
    if review.decision == "HIDE":
        return {"item_id": item["item_id"], "product": item["product"],
                "state": HIDDEN, "reason": "HUMAN_REJECTED", "failed_gates": []}
    if review.decision == "EXPERIMENTAL":
        return {"item_id": item["item_id"], "product": item["product"],
                "state": DESIGN_EXPERIMENT, "reason": "HUMAN_MARKED_EXPERIMENTAL",
                "failed_gates": []}

    weak = [d for d in CRITICAL_DIMENSIONS
            if (review.scores or {}).get(d, 0) < CRITICAL_SCORE_THRESHOLD] if review.scores else []
    if review.decision == "APPROVE" and not weak:
        return {"item_id": item["item_id"], "product": item["product"],
                "state": PRODUCTION_RECOMMENDED, "reason": "HUMAN_APPROVED_ALL_GATES_PASS",
                "failed_gates": [], "reviewer": review.reviewer}
    return {"item_id": item["item_id"], "product": item["product"],
            "state": COMMERCIAL_CANDIDATE,
            "reason": "APPROVED_WITH_WEAK_CRITICAL_SCORES" if weak else "HUMAN_ALLOWED",
            "weak_critical_dimensions": weak, "failed_gates": [],
            "reviewer": review.reviewer}


def commercial_curation(session: Session, items: list[dict]) -> list[dict]:
    return [commercial_class(i, latest_review(session, i["item_id"])) for i in items]


# ---------------------------------------------------------------------------
# 5. Best family — only with enough evidence
# ---------------------------------------------------------------------------

def best_family(session: Session, items: list[dict], signal: str) -> dict:
    """Best font family per product for one human signal.

    Returns INSUFFICIENT_HUMAN_REVIEW_EVIDENCE per product wherever the
    thresholds are not met, and says exactly what is missing."""
    if signal not in SIGNAL_DIMENSIONS:
        raise ValueError(f"Unknown signal '{signal}'")
    reviews = [r for r in session.execute(select(m.DesignReview)).scalars() if r.scores]
    dims = SIGNAL_DIMENSIONS[signal]

    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for r in reviews:
        grouped[(r.product, r.font_id)].append(r)

    per_product: dict[str, list] = defaultdict(list)
    for (product, font_id), rows in grouped.items():
        values = [s for r in rows for d in dims if (s := (r.scores or {}).get(d)) is not None]
        if not values:
            continue
        per_product[product].append({
            "font_family": font_id,
            "average_score": round(statistics.fmean(values), 3),
            "review_count": len(rows),
            "distinct_items": len({r.item_id for r in rows}),
            "reviewers": sorted({r.reviewer for r in rows}),
            "confidence": confidence_for(len(rows), len({r.reviewer for r in rows})),
            "supporting_reviews": [
                {"item_id": r.item_id, "reviewer": r.reviewer, "decision": r.decision}
                for r in rows
            ],
        })

    products = sorted({i["product"] for i in items})
    out = {}
    for product in products:
        candidates = per_product.get(product, [])
        eligible = [
            c for c in candidates
            if c["review_count"] >= MIN_DEEP_REVIEWS_FOR_CLAIM
            and c["distinct_items"] >= MIN_DISTINCT_ITEMS_FOR_CLAIM
        ]
        if not eligible:
            out[product] = {
                "status": INSUFFICIENT,
                "signal": signal,
                "reviews_available": sum(c["review_count"] for c in candidates),
                "required": {
                    "scored_reviews_per_family": MIN_DEEP_REVIEWS_FOR_CLAIM,
                    "distinct_items_per_family": MIN_DISTINCT_ITEMS_FOR_CLAIM,
                },
                "exclusions": [
                    {"font_family": c["font_family"], "reason": "below evidence threshold",
                     "review_count": c["review_count"], "distinct_items": c["distinct_items"]}
                    for c in candidates
                ],
            }
            continue
        eligible.sort(key=lambda c: (-c["average_score"], c["font_family"]))
        winner = eligible[0]
        out[product] = {
            "status": "DERIVED",
            "signal": signal,
            "product": product,
            **winner,
            "exclusions": [
                {"font_family": c["font_family"], "reason": "below evidence threshold",
                 "review_count": c["review_count"], "distinct_items": c["distinct_items"]}
                for c in candidates if c not in eligible
            ],
        }
    return out


# ---------------------------------------------------------------------------
# 6. Golden pattern validation
# ---------------------------------------------------------------------------

def golden_pattern_validation(session: Session, items: list[dict]) -> dict:
    """Does Golden-Case relevance actually predict human preference?

    Reported as an open question, not an assumption. A Golden case is
    historical fact; whether it predicts taste on NEW items is exactly what
    this measures, and it is allowed to come out negative."""
    meta = {i["item_id"]: i for i in items}
    reviews = list(session.execute(select(m.DesignReview)).scalars())
    golden_pref, plain_pref = [], []
    for r in reviews:
        item = meta.get(r.item_id)
        if item is None:
            continue
        preferred = r.decision in ("APPROVE", "ALLOW")
        (golden_pref if item["golden_production_pattern"] else plain_pref).append(preferred)

    def rate(values):
        return round(sum(values) / len(values), 3) if values else None

    golden_rate, plain_rate = rate(golden_pref), rate(plain_pref)
    if golden_rate is None or plain_rate is None:
        verdict = INSUFFICIENT
        note = ("Not enough reviewed items in both groups to say whether Golden "
                "relevance predicts human preference.")
    elif golden_rate > plain_rate:
        verdict, note = "CORRELATED", "Golden-relevant items were preferred more often."
    elif golden_rate < plain_rate:
        verdict, note = "NOT_CORRELATED", "Golden-relevant items were preferred LESS often."
    else:
        verdict, note = "NO_DIFFERENCE", "Golden relevance made no measurable difference."

    return {
        "golden_relevant_reviewed": len(golden_pref),
        "non_golden_reviewed": len(plain_pref),
        "golden_preference_rate": golden_rate,
        "non_golden_preference_rate": plain_rate,
        "verdict": verdict,
        "predictive_or_historical": (
            "UNDETERMINED" if verdict == INSUFFICIENT else
            "PREDICTIVE" if verdict == "CORRELATED" else "HISTORICAL_ONLY"
        ),
        "note": note,
        "golden_cases_were_not_favoured": True,
    }
