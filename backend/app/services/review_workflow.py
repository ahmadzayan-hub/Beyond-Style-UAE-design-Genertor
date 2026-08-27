"""Human Aesthetic Review workflow.

What this module does: prepare review items, record what a human decided,
and derive curation from those decisions. What it deliberately does NOT do:
decide. No function here produces an aesthetic verdict, and an item with no
human review stays HUMAN_REVIEW_PENDING for ever rather than drifting into
approval.

Three separations are load-bearing:

  * A review item is a (font, features, axes, product, composition, text)
    COMBINATION, never a font. The same face can be right for a pendant and
    wrong for a ring, so promotion is product-scoped.
  * Human scores live in `design_reviews` and nowhere else. Deterministic
    engineering scores and any AI advisory score are kept separate and are
    never averaged together.
  * Human approval is permission to SHOW something, never permission to
    ship something unsafe. Arabic identity, manufacturing and rights are
    hard gates that a five-star review cannot open.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..fonts.curation import CurationState

#: The twelve human dimensions, scored 1-5. No deterministic proxy exists
#: for any of them — that is precisely why a person is asked.
#:
#: `ArabicCorrectness` is the reviewer's VISUAL judgement that the letters
#: read correctly. It sits alongside, and never replaces, the deterministic
#: identity proof: the hard gate still decides what may ship.
HUMAN_DIMENSIONS = [
    "ArabicCorrectness", "Legibility", "Elegance", "VisualBalance",
    "PremiumFeel", "Uniqueness", "ProductFit", "CommercialAppeal",
    "Wearability", "EmotionalAppeal", "OverallAestheticQuality", "WouldRecommend",
]

#: Human-readable labels for the review UI.
DIMENSION_LABELS = {
    "ArabicCorrectness": "Arabic correctness",
    "Legibility": "Legibility",
    "Elegance": "Elegance",
    "VisualBalance": "Visual balance",
    "PremiumFeel": "Premium feel",
    "Uniqueness": "Uniqueness",
    "ProductFit": "Product fit",
    "CommercialAppeal": "Commercial appeal",
    "Wearability": "Wearability",
    "EmotionalAppeal": "Emotional appeal",
    "OverallAestheticQuality": "Overall aesthetic quality",
    "WouldRecommend": "Would recommend to customer",
}

#: Dimensions that may not be weak in anything recommended for production:
#: letters that do not read, or a piece that does not suit its product, is
#: not a recommendation however elegant it looks.
CRITICAL_DIMENSIONS = ["ArabicCorrectness", "Legibility", "ProductFit"]
CRITICAL_SCORE_THRESHOLD = 3

#: A critical dimension where two reviewers differ by this much is a real
#: disagreement, surfaced rather than averaged away.
DISAGREEMENT_DELTA = 2

DECISIONS = {"APPROVE", "ALLOW", "EXPERIMENTAL", "HIDE"}
QUICK, DEEP = "quick", "deep"

PENDING = "HUMAN_REVIEW_PENDING"


class ReviewRejected(ValueError):
    """A review that cannot be recorded as given."""


def item_id(font_id: str, feature_set: str, font_axes: dict | None,
            product: str, composition: str, source_text: str) -> str:
    """Deterministic id of one reviewable combination."""
    payload = json.dumps(
        {"font_id": font_id, "feature_set": feature_set,
         "font_axes": dict(sorted((font_axes or {}).items())),
         "product": product, "composition": composition, "source_text": source_text},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def recipe_hash(recipe: dict) -> str:
    return hashlib.sha256(
        json.dumps(recipe, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Recording a human decision
# ---------------------------------------------------------------------------

def record_review(
    session: Session,
    *,
    item: dict,
    reviewer: str,
    decision: str,
    mode: str = QUICK,
    scores: dict | None = None,
    note: str | None = None,
) -> m.DesignReview:
    """Append one human review. Never updates an earlier one.

    The engineering state is snapshotted alongside, so a later reader can
    see what the reviewer was actually looking at rather than what the
    pipeline produces today."""
    if decision not in DECISIONS:
        raise ReviewRejected(f"Unknown decision '{decision}'. Expected one of {sorted(DECISIONS)}.")
    if not reviewer or not reviewer.strip():
        raise ReviewRejected("A review must name its reviewer — decisions are attributable.")
    if mode not in (QUICK, DEEP):
        raise ReviewRejected(f"Unknown review mode '{mode}'.")
    if mode == DEEP:
        if not scores:
            raise ReviewRejected("Deep review requires all twelve dimension scores.")
        missing = [d for d in HUMAN_DIMENSIONS if d not in scores]
        if missing:
            raise ReviewRejected(f"Deep review is missing scores for: {missing}")
        bad = {k: v for k, v in scores.items()
               if k in HUMAN_DIMENSIONS and not (isinstance(v, int) and 1 <= v <= 5)}
        if bad:
            raise ReviewRejected(f"Scores must be integers 1-5; got {bad}")

    row = m.DesignReview(
        item_id=item["item_id"],
        recipe_hash=item["recipe_hash"],
        product=item["product"],
        font_id=item["font_id"],
        feature_set=item.get("feature_set", "default"),
        font_axes=item.get("font_axes") or {},
        source_text=item["source_text"],
        reviewer=reviewer.strip(),
        decision=decision,
        review_mode=mode,
        scores={k: scores[k] for k in HUMAN_DIMENSIONS} if scores else None,
        note=note,
        engineering_snapshot=item.get("engineering", {}),
    )
    session.add(row)
    session.flush()
    return row


def review_history(session: Session, item: str) -> list[m.DesignReview]:
    """Every review of one item, oldest first. Nothing is ever removed."""
    return list(session.execute(
        select(m.DesignReview)
        .where(m.DesignReview.item_id == item)
        .order_by(m.DesignReview.created_at, m.DesignReview.id)
    ).scalars())


def latest_review(session: Session, item: str) -> m.DesignReview | None:
    history = review_history(session, item)
    return history[-1] if history else None


# ---------------------------------------------------------------------------
# Curation — what the human decision means, given the hard gates
# ---------------------------------------------------------------------------

#: Gates a human may never open. Each is a correctness or legal fact about
#: the design, not a matter of taste.
HARD_GATES = ("arabic_identity_pass", "manufacturing_pass", "rights_pass")


def curation_for_item(item: dict, review: m.DesignReview | None) -> dict:
    """The curation state of one item, from its gates and its newest review.

    Order matters: gates are evaluated BEFORE the review is consulted, so an
    APPROVE on a design that fails Arabic identity, manufacturing or rights
    can only ever produce HIDDEN with the blocking reason recorded."""
    engineering = item.get("engineering", {})
    blocked = [gate for gate in HARD_GATES if not engineering.get(gate)]
    if blocked:
        return {
            "item_id": item["item_id"],
            "product": item["product"],
            "state": CurationState.HIDDEN.value,
            "reason": "BLOCKED_BY_HARD_GATE",
            "failed_gates": blocked,
            "human_decision": review.decision if review else None,
            "human_review_status": "OVERRIDDEN_BY_HARD_GATE" if review else PENDING,
            "note": "Human aesthetic approval cannot open a safety, identity or rights gate.",
        }

    if review is None:
        return {
            "item_id": item["item_id"],
            "product": item["product"],
            "state": CurationState.EXPERIMENTAL.value,
            "reason": PENDING,
            "failed_gates": [],
            "human_decision": None,
            "human_review_status": PENDING,
        }

    weak = []
    if review.scores:
        weak = [d for d in CRITICAL_DIMENSIONS
                if review.scores.get(d, 0) < CRITICAL_SCORE_THRESHOLD]

    if review.decision == "APPROVE" and not weak:
        state, reason = CurationState.PRODUCTION_RECOMMENDED.value, "HUMAN_APPROVED"
    elif review.decision == "APPROVE" and weak:
        # Approved overall, but a critical dimension is weak — allowed, not
        # recommended, and the reason says which.
        state, reason = CurationState.PRODUCTION_ALLOWED.value, "APPROVED_WITH_WEAK_CRITICAL_SCORES"
    elif review.decision == "ALLOW":
        state, reason = CurationState.PRODUCTION_ALLOWED.value, "HUMAN_ALLOWED"
    elif review.decision == "HIDE":
        state, reason = CurationState.HIDDEN.value, "HUMAN_REJECTED"
    else:
        state, reason = CurationState.EXPERIMENTAL.value, "HUMAN_MARKED_EXPERIMENTAL"

    return {
        "item_id": item["item_id"],
        "product": item["product"],
        "state": state,
        "reason": reason,
        "failed_gates": [],
        "weak_critical_dimensions": weak,
        "human_decision": review.decision,
        "human_review_status": "REVIEWED",
        "reviewer": review.reviewer,
        "reviewed_at": review.created_at.isoformat(),
        "review_mode": review.review_mode,
    }


def curation_decisions(session: Session, items: list[dict]) -> list[dict]:
    return [curation_for_item(i, latest_review(session, i["item_id"])) for i in items]


def product_scoped_states(decisions: list[dict]) -> dict:
    """{font/feature key: {product: state}} — promotion is never global."""
    out: dict[str, dict[str, str]] = {}
    for decision in decisions:
        key = decision.get("variant_key") or decision["item_id"]
        out.setdefault(key, {})[decision["product"]] = decision["state"]
    return out


# ---------------------------------------------------------------------------
# AI advisory — stored beside human scores, never inside them
# ---------------------------------------------------------------------------

def ai_advisory_status() -> dict:
    """Whether a real visual model is configured to pre-annotate sheets.

    With no credentials this reports SKIPPED_NO_CREDENTIALS. It never
    fabricates a score, and an advisory score can never promote anything:
    `curation_for_item` reads only the human decision."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "available": False,
            "status": "SKIPPED_NO_CREDENTIALS",
            "note": "No ANTHROPIC_API_KEY configured; no advisory scores were produced.",
            "scores": [],
        }
    return {
        "available": True,
        "status": "AVAILABLE_NOT_RUN",
        "note": "Advisory scoring is opt-in per review pack and is stored as "
                "AI_ADVISORY_SCORE, never merged into HUMAN_SCORE.",
        "scores": [],
    }


def summarize(decisions: list[dict], reviews_recorded: int) -> dict:
    from collections import Counter

    states = Counter(d["state"] for d in decisions)
    pending = sum(1 for d in decisions if d["human_review_status"] == PENDING)
    return {
        "review_items": len(decisions),
        "human_reviews_recorded": reviews_recorded,
        "human_review_status": PENDING if reviews_recorded == 0 else "IN_PROGRESS",
        "states": dict(states),
        "awaiting_human_review": pending,
        "blocked_by_hard_gate": sum(
            1 for d in decisions if d["reason"] == "BLOCKED_BY_HARD_GATE"),
    }
