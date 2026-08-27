"""Aesthetic and commercial curation derived from HUMAN review evidence.

The contamination this module exists to prevent: letting a manufacturing
score, a font metric or an AI guess stand in for taste. Every aesthetic and
commercial number here is computed from `design_reviews` rows — what people
actually said — and from nothing else. Engineering results appear only as
GATES (pass/fail), never as inputs to an aesthetic average.

When the evidence is thin, that is the answer: the best-family functions
return NOT_COMPARISON_READY or INSUFFICIENT_HUMAN_REVIEW_EVIDENCE rather
than a confident-looking number computed from one opinion.
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

#: --- Evidence model (P3) ---------------------------------------------------
#:
#: The previous model required ">=5 scored reviews across >=3 distinct items
#: per (product, family)". That was STRUCTURALLY IMPOSSIBLE: the review pack
#: deliberately carries at most ONE item per font family per product for
#: diversity, so the distinct-item clause could never be satisfied however
#: many reviews were entered. It is replaced, not quietly relaxed.
#:
#: Confidence is now a property of an ITEM (how many independent people
#: looked at it) and comparison readiness a property of a PRODUCT (are there
#: enough rival families, each independently reviewed).

ITEM_NO_CONFIDENCE = "ITEM_NO_REVIEW"
ITEM_LOW_CONFIDENCE = "ITEM_LOW_CONFIDENCE"
ITEM_MEDIUM_CONFIDENCE = "ITEM_MEDIUM_CONFIDENCE"
ITEM_HIGH_CONFIDENCE = "ITEM_HIGH_CONFIDENCE"

#: A product can only crown a winner when rivals exist AND each was seen by
#: more than one person.
MIN_FAMILIES_FOR_COMPARISON = 3
MIN_REVIEWS_PER_CANDIDATE = 2

#: A cross-product claim needs breadth as well as depth.
MIN_PRODUCTS_FOR_OVERALL_CLAIM = 3
MIN_TOTAL_REVIEWS_FOR_OVERALL_CLAIM = 6

#: Commercial recommendation demands more than "not bad".
COMMERCIAL_MIN_SCORES = {"CommercialAppeal": 4, "PremiumFeel": 4, "ProductFit": 4}

STRUCTURALLY_IMPOSSIBLE = "STRUCTURALLY_IMPOSSIBLE_THRESHOLD"
NOT_COMPARISON_READY = "NOT_COMPARISON_READY"

#: Which human dimensions feed which derived signal. Each is a subset of the
#: twelve a reviewer actually scored — no dimension is invented.
SIGNAL_DIMENSIONS = {
    "human_aesthetic_score": ["Elegance", "VisualBalance", "OverallAestheticQuality"],
    "commercial_appeal_score": ["CommercialAppeal", "WouldRecommend"],
    "premium_feel_score": ["PremiumFeel", "Uniqueness"],
    "readability_score": ["Legibility", "ArabicCorrectness"],
    "product_fit_score": ["ProductFit", "Wearability"],
}


def _text_category(text: str) -> str:
    words = text.split()
    if len(words) >= 5:
        return "multi_name"
    if len(words) > 1:
        return "phrase"
    return "single_letter" if len(text.strip()) <= 2 else "single_name"


def item_confidence(independent_reviews: int, agreement_ok: bool = True) -> str:
    """Confidence in ONE item, from how many independent people reviewed it.

    Two reviewers is MEDIUM, not HIGH: two people agreeing is not yet a
    consensus. HIGH needs three or more AND acceptable agreement."""
    if independent_reviews <= 0:
        return ITEM_NO_CONFIDENCE
    if independent_reviews == 1:
        return ITEM_LOW_CONFIDENCE
    if independent_reviews == 2:
        return ITEM_MEDIUM_CONFIDENCE
    return ITEM_HIGH_CONFIDENCE if agreement_ok else ITEM_MEDIUM_CONFIDENCE


def confidence_for(review_count: int, reviewer_count: int) -> str:
    """Coverage confidence for a GROUP (a product, a font family).

    Driven by how many DIFFERENT people looked, not by volume: one person
    reviewing nine items is still one opinion. The earlier "a second
    reviewer unlocks HIGH confidence" rule was wrong and is gone."""
    if review_count == 0:
        return "NONE"
    if reviewer_count <= 1:
        return "LOW"
    if reviewer_count == 2:
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
        if cov["reviews"] < MIN_REVIEWS_PER_CANDIDATE
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

def agreement_report(session: Session, item_id: str) -> dict:
    """Spread between independent reviewers of one item.

    Disagreement is surfaced, never smoothed: a mean of 3 from scores of 2
    and 4 hides exactly the thing a person needs to look at."""
    from .review_workflow import DISAGREEMENT_DELTA, review_history

    rows = [r for r in review_history(session, item_id) if r.scores]
    # One review per reviewer — the newest — so a reviewer who revised their
    # opinion is not counted twice as "independent".
    newest: dict[str, object] = {}
    for r in rows:
        newest[r.reviewer] = r
    independent = list(newest.values())

    per_dimension = {}
    disagreements = []
    for dim in HUMAN_DIMENSIONS:
        values = [r.scores[dim] for r in independent if dim in (r.scores or {})]
        if not values:
            continue
        spread = max(values) - min(values)
        per_dimension[dim] = {
            "mean": round(statistics.fmean(values), 3),
            "min": min(values), "max": max(values), "spread": spread,
            "values": values,
        }
        if dim in CRITICAL_DIMENSIONS and spread >= DISAGREEMENT_DELTA:
            disagreements.append({"dimension": dim, "spread": spread, "values": values})

    return {
        "item_id": item_id,
        "independent_reviews": len(independent),
        "reviewers": sorted(newest),
        "per_dimension": per_dimension,
        "critical_disagreements": disagreements,
        "flag": "REVIEWER_DISAGREEMENT" if disagreements else None,
        "agreement_ok": not disagreements,
        "confidence": item_confidence(len(independent), not disagreements),
        "note": "Spread is reported alongside the mean so disagreement is visible.",
    }


def _candidate_stats(session: Session, items: list[dict], signal: str) -> dict:
    """Per (product, font family): independent reviews and mean signal."""
    from .review_workflow import review_history

    dims = SIGNAL_DIMENSIONS[signal]
    stats: dict[str, list] = defaultdict(list)
    for item in items:
        rows = [r for r in review_history(session, item["item_id"]) if r.scores]
        newest = {}
        for r in rows:
            newest[r.reviewer] = r
        independent = list(newest.values())
        if not independent:
            continue
        values = [s for r in independent for d in dims if (s := r.scores.get(d)) is not None]
        agreement = agreement_report(session, item["item_id"])
        critical_ok = all(
            statistics.fmean([r.scores[d] for r in independent if d in r.scores])
            >= CRITICAL_SCORE_THRESHOLD
            for d in CRITICAL_DIMENSIONS
            if any(d in (r.scores or {}) for r in independent)
        )
        stats[item["product"]].append({
            "font_family": item["technical"]["font_id"],
            "item_id": item["item_id"],
            "independent_reviews": len(independent),
            "reviewers": sorted(newest),
            "mean_score": round(statistics.fmean(values), 3) if values else None,
            "critical_scores_ok": critical_ok,
            "agreement_ok": agreement["agreement_ok"],
            "confidence": agreement["confidence"],
            "gates_pass": all(item["engineering"].get(g) for g in HARD_GATES),
            "commercial_means": {
                d: round(statistics.fmean(
                    [r.scores[d] for r in independent if d in r.scores]), 3)
                for d in COMMERCIAL_MIN_SCORES
                if any(d in (r.scores or {}) for r in independent)
            },
        })
    return stats


def product_comparison_readiness(session: Session, items: list[dict]) -> dict:
    """Is a product ready for a winner to be named at all?

    Requires at least three rival font families, each with at least two
    independent reviews. Anything less and the honest answer is that we do
    not know which is best — not a winner chosen from a field of one."""
    stats = _candidate_stats(session, items, "human_aesthetic_score")
    families_available = defaultdict(set)
    for item in items:
        families_available[item["product"]].add(item["technical"]["font_id"])

    out = {}
    for product in sorted({i["product"] for i in items}):
        candidates = stats.get(product, [])
        qualified = [c for c in candidates
                     if c["independent_reviews"] >= MIN_REVIEWS_PER_CANDIDATE]
        ready = len(qualified) >= MIN_FAMILIES_FOR_COMPARISON
        out[product] = {
            "product": product,
            "status": "PRODUCT_COMPARISON_READY" if ready else NOT_COMPARISON_READY,
            "families_in_corpus": len(families_available[product]),
            "families_reviewed": len(candidates),
            "families_with_enough_reviews": len(qualified),
            "required_families": MIN_FAMILIES_FOR_COMPARISON,
            "required_reviews_per_family": MIN_REVIEWS_PER_CANDIDATE,
            "corpus_can_support_comparison":
                len(families_available[product]) >= MIN_FAMILIES_FOR_COMPARISON,
            "shortfall": (
                None if ready else
                f"{MIN_FAMILIES_FOR_COMPARISON - len(qualified)} more font "
                f"famil{'y' if MIN_FAMILIES_FOR_COMPARISON - len(qualified) == 1 else 'ies'} "
                f"need >= {MIN_REVIEWS_PER_CANDIDATE} independent reviews"
            ),
        }
    return out


def best_aesthetic_family_for_product(session: Session, items: list[dict]) -> dict:
    """Winner per product on the human aesthetic signal, or why not."""
    readiness = product_comparison_readiness(session, items)
    stats = _candidate_stats(session, items, "human_aesthetic_score")
    out = {}
    for product, ready in readiness.items():
        readiness_detail = {k: v for k, v in ready.items() if k != "status"}
        if ready["status"] != "PRODUCT_COMPARISON_READY":
            out[product] = {"status": NOT_COMPARISON_READY, **readiness_detail}
            continue
        eligible = [
            c for c in stats[product]
            if c["independent_reviews"] >= MIN_REVIEWS_PER_CANDIDATE
            and c["gates_pass"] and c["critical_scores_ok"] and c["mean_score"] is not None
        ]
        if not eligible:
            out[product] = {"status": INSUFFICIENT,
                            "reason": "no candidate passed gates and critical-score floor",
                            **readiness_detail}
            continue
        eligible.sort(key=lambda c: (-c["mean_score"], c["font_family"]))
        out[product] = {"status": "DERIVED", "signal": "human_aesthetic_score",
                        "product": product, **eligible[0],
                        "runners_up": eligible[1:]}
    return out


def best_commercial_family_for_product(session: Session, items: list[dict]) -> dict:
    """As above, plus explicit commercial floors on CommercialAppeal,
    PremiumFeel and ProductFit — a design can be beautiful and still not be
    something to build a product line on."""
    readiness = product_comparison_readiness(session, items)
    stats = _candidate_stats(session, items, "commercial_appeal_score")
    out = {}
    for product, ready in readiness.items():
        readiness_detail = {k: v for k, v in ready.items() if k != "status"}
        if ready["status"] != "PRODUCT_COMPARISON_READY":
            out[product] = {"status": NOT_COMPARISON_READY, **readiness_detail}
            continue
        eligible = []
        for c in stats[product]:
            if not (c["independent_reviews"] >= MIN_REVIEWS_PER_CANDIDATE
                    and c["gates_pass"] and c["critical_scores_ok"]
                    and c["mean_score"] is not None):
                continue
            below = {d: c["commercial_means"].get(d) for d, floor in COMMERCIAL_MIN_SCORES.items()
                     if (c["commercial_means"].get(d) or 0) < floor}
            if below:
                c = {**c, "below_commercial_floor": below}
            else:
                eligible.append(c)
        if not eligible:
            out[product] = {"status": INSUFFICIENT,
                            "reason": "no candidate met the commercial floors",
                            "commercial_floors": COMMERCIAL_MIN_SCORES,
                            **readiness_detail}
            continue
        eligible.sort(key=lambda c: (-c["mean_score"], c["font_family"]))
        out[product] = {"status": "DERIVED", "signal": "commercial_appeal_score",
                        "product": product, "commercial_floors": COMMERCIAL_MIN_SCORES,
                        **eligible[0], "runners_up": eligible[1:]}
    return out


def overall_best_aesthetic_family(session: Session, items: list[dict]) -> dict:
    """A cross-product claim: evidence across >=3 products and >=6
    independent reviews in total, with no hard-gate failure."""
    stats = _candidate_stats(session, items, "human_aesthetic_score")
    by_family: dict[str, dict] = defaultdict(
        lambda: {"products": set(), "reviews": 0, "scores": [], "gates_ok": True})
    for product, candidates in stats.items():
        for c in candidates:
            entry = by_family[c["font_family"]]
            entry["products"].add(product)
            entry["reviews"] += c["independent_reviews"]
            if c["mean_score"] is not None:
                entry["scores"].append(c["mean_score"])
            entry["gates_ok"] = entry["gates_ok"] and c["gates_pass"]

    eligible = [
        {"font_family": family, "products": sorted(e["products"]),
         "product_count": len(e["products"]), "independent_reviews": e["reviews"],
         "mean_score": round(statistics.fmean(e["scores"]), 3) if e["scores"] else None}
        for family, e in by_family.items()
        if len(e["products"]) >= MIN_PRODUCTS_FOR_OVERALL_CLAIM
        and e["reviews"] >= MIN_TOTAL_REVIEWS_FOR_OVERALL_CLAIM
        and e["gates_ok"] and e["scores"]
    ]
    if not eligible:
        return {
            "status": INSUFFICIENT,
            "required": {
                "products": MIN_PRODUCTS_FOR_OVERALL_CLAIM,
                "independent_reviews": MIN_TOTAL_REVIEWS_FOR_OVERALL_CLAIM,
            },
            "candidates": [
                {"font_family": f, "products": len(e["products"]), "reviews": e["reviews"]}
                for f, e in by_family.items()
            ],
        }
    eligible.sort(key=lambda c: (-c["mean_score"], c["font_family"]))
    return {"status": "DERIVED", **eligible[0], "runners_up": eligible[1:]}


def threshold_audit(items: list[dict]) -> dict:
    """Can the corpus, in principle, satisfy each rule? A threshold nothing
    could ever meet is a bug, not a high standard."""
    families_per_product = defaultdict(set)
    items_per_pair = Counter()
    for item in items:
        product, font_id = item["product"], item["technical"]["font_id"]
        families_per_product[product].add(font_id)
        items_per_pair[(product, font_id)] += 1

    max_items_per_pair = max(items_per_pair.values()) if items_per_pair else 0
    retired = {
        "rule": ">=5 scored reviews across >=3 DISTINCT ITEMS per (product, family)",
        "status": STRUCTURALLY_IMPOSSIBLE,
        "reason": (
            f"the corpus holds at most {max_items_per_pair} item(s) per "
            "(product, family) by design — the review pack keeps one item per "
            "font family per product for diversity — so the distinct-item "
            "clause can never be satisfied."
        ),
        "replaced_by": "PRODUCT_COMPARISON_READY + per-item independent review counts",
    }
    comparable = {
        p: {"families": len(f), "can_compare": len(f) >= MIN_FAMILIES_FOR_COMPARISON}
        for p, f in sorted(families_per_product.items())
    }
    return {
        "items": len(items),
        "items_per_product": {p: sum(
            1 for i in items if i["product"] == p) for p in sorted(families_per_product)},
        "families_per_product": comparable,
        "items_per_product_family": {f"{p}/{f}": n for (p, f), n in sorted(items_per_pair.items())},
        "max_items_per_product_family": max_items_per_pair,
        "retired_rule": retired,
        "achievable_rules": [
            f"PRODUCT_COMPARISON_READY (>={MIN_FAMILIES_FOR_COMPARISON} families, "
            f">={MIN_REVIEWS_PER_CANDIDATE} independent reviews each)",
            "ITEM_LOW/MEDIUM/HIGH_CONFIDENCE (1 / 2 / 3+ independent reviews)",
            f"OVERALL_BEST_AESTHETIC_FAMILY (>={MIN_PRODUCTS_FOR_OVERALL_CLAIM} products, "
            f">={MIN_TOTAL_REVIEWS_FOR_OVERALL_CLAIM} reviews)",
        ],
        "impossible_rules": [retired["rule"]],
    }


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
