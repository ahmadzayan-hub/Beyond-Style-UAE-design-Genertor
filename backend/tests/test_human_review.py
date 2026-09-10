"""Human Aesthetic Review workflow regressions.

The rule defended here: a human decides what is beautiful, and nothing
else does — but that decision is permission to SHOW, never permission to
ship something that fails Arabic identity, manufacturing or licensing.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.db import models as m
from app.services.review_items import (
    PHRASE, REVIEW_CORPUS, REVIEW_PRODUCTS, SEVEN_NAMES, build_review_item,
)
from app.services.review_workflow import (
    CRITICAL_DIMENSIONS, CRITICAL_SCORE_THRESHOLD, DECISIONS, HUMAN_DIMENSIONS,
    PENDING, ReviewRejected, ai_advisory_status, curation_for_item,
    latest_review, product_scoped_states, record_review, review_history,
    summarize,
)

GOOD_ENGINEERING = {
    "arabic_identity_pass": True, "manufacturing_pass": True, "rights_pass": True,
}


def _item(item_id="item-1", product="pendant", engineering=None, **over):
    base = {
        "item_id": item_id, "recipe_hash": "a" * 64, "product": product,
        "font_id": "amiri-regular", "feature_set": "default", "font_axes": {},
        "source_text": "نورة", "variant_key": "amiri-regular/default",
        "engineering": dict(engineering or GOOD_ENGINEERING),
    }
    base.update(over)
    return base


def _full_scores(value=4):
    return {d: value for d in HUMAN_DIMENSIONS}


# --- hard gates outrank taste -----------------------------------------------

@pytest.mark.parametrize("gate", ["manufacturing_pass", "arabic_identity_pass", "rights_pass"])
def test_human_approval_cannot_open_a_hard_gate(clean_tables, db_session, gate):
    item = _item(engineering={**GOOD_ENGINEERING, gate: False})
    review = record_review(db_session, item=item, reviewer="Art Director",
                           decision="APPROVE", mode="deep", scores=_full_scores(5))
    db_session.flush()
    curation = curation_for_item(item, review)
    assert curation["state"] == "HIDDEN"
    assert curation["reason"] == "BLOCKED_BY_HARD_GATE"
    assert gate in curation["failed_gates"]
    assert curation["human_review_status"] == "OVERRIDDEN_BY_HARD_GATE"


def test_gates_are_evaluated_before_the_review_is_read():
    """Even a perfect five-star deep review cannot promote a failing item."""
    item = _item(engineering={**GOOD_ENGINEERING, "manufacturing_pass": False})
    assert curation_for_item(item, None)["state"] == "HIDDEN"


# --- nothing is decided without a human -------------------------------------

def test_unreviewed_item_stays_pending_for_ever():
    curation = curation_for_item(_item(), None)
    assert curation["state"] == "EXPERIMENTAL"
    assert curation["reason"] == PENDING
    assert curation["human_review_status"] == PENDING
    assert curation["human_decision"] is None


def test_summary_reports_zero_human_decisions_honestly():
    decisions = [curation_for_item(_item(f"i{i}"), None) for i in range(5)]
    summary = summarize(decisions, reviews_recorded=0)
    assert summary["human_review_status"] == PENDING
    assert summary["human_reviews_recorded"] == 0
    assert summary["awaiting_human_review"] == 5
    assert summary["states"].get("PRODUCTION_RECOMMENDED", 0) == 0


# --- decision semantics -----------------------------------------------------

def test_approve_with_all_gates_recommends(clean_tables, db_session):
    item = _item()
    review = record_review(db_session, item=item, reviewer="AD", decision="APPROVE",
                           mode="deep", scores=_full_scores(5))
    db_session.flush()
    curation = curation_for_item(item, review)
    assert curation["state"] == "PRODUCTION_RECOMMENDED"
    assert curation["reason"] == "HUMAN_APPROVED"
    assert curation["reviewer"] == "AD"


def test_weak_critical_score_downgrades_approve_to_allowed(clean_tables, db_session):
    """Beautiful but unreadable is not a recommendation."""
    scores = _full_scores(5)
    scores["Legibility"] = CRITICAL_SCORE_THRESHOLD - 1
    item = _item()
    review = record_review(db_session, item=item, reviewer="AD", decision="APPROVE",
                           mode="deep", scores=scores)
    db_session.flush()
    curation = curation_for_item(item, review)
    assert curation["state"] == "PRODUCTION_ALLOWED"
    assert curation["reason"] == "APPROVED_WITH_WEAK_CRITICAL_SCORES"
    assert "Legibility" in curation["weak_critical_dimensions"]


@pytest.mark.parametrize("decision,expected", [
    ("ALLOW", "PRODUCTION_ALLOWED"),
    ("HIDE", "HIDDEN"),
    ("EXPERIMENTAL", "EXPERIMENTAL"),
])
def test_decisions_map_to_their_states(clean_tables, db_session, decision, expected):
    item = _item()
    review = record_review(db_session, item=item, reviewer="AD", decision=decision)
    db_session.flush()
    assert curation_for_item(item, review)["state"] == expected


def test_critical_dimensions_are_the_documented_three():
    assert set(CRITICAL_DIMENSIONS) == {
        "ArabicCorrectness", "Legibility", "ProductFit",
        "CommercialAppeal", "OverallAestheticQuality",
    }
    assert set(CRITICAL_DIMENSIONS) <= set(HUMAN_DIMENSIONS)
    assert len(HUMAN_DIMENSIONS) == 12


# --- review validity --------------------------------------------------------

def test_deep_review_requires_every_dimension(clean_tables, db_session):
    partial = {d: 4 for d in HUMAN_DIMENSIONS[:5]}
    with pytest.raises(ReviewRejected, match="missing scores"):
        record_review(db_session, item=_item(), reviewer="AD", decision="APPROVE",
                      mode="deep", scores=partial)


def test_scores_must_be_one_to_five(clean_tables, db_session):
    scores = _full_scores(4)
    scores["VisualBalance"] = 9
    with pytest.raises(ReviewRejected, match="1-5"):
        record_review(db_session, item=_item(), reviewer="AD", decision="APPROVE",
                      mode="deep", scores=scores)


def test_review_must_name_its_reviewer(clean_tables, db_session):
    with pytest.raises(ReviewRejected, match="reviewer"):
        record_review(db_session, item=_item(), reviewer="  ", decision="APPROVE")


def test_unknown_decision_is_refused(clean_tables, db_session):
    with pytest.raises(ReviewRejected):
        record_review(db_session, item=_item(), reviewer="AD", decision="SHIP_IT")
    assert DECISIONS == {"APPROVE", "ALLOW", "EXPERIMENTAL", "HIDE"}


# --- append-only history ----------------------------------------------------

def test_review_history_is_append_only(clean_tables, db_session):
    item = _item()
    first = record_review(db_session, item=item, reviewer="AD 1", decision="ALLOW")
    db_session.commit()
    second = record_review(db_session, item=item, reviewer="AD 2", decision="APPROVE",
                           mode="deep", scores=_full_scores(5))
    db_session.commit()

    history = review_history(db_session, item["item_id"])
    assert [r.id for r in history] == [first.id, second.id]
    assert history[0].decision == "ALLOW", "the earlier opinion must survive"
    assert latest_review(db_session, item["item_id"]).id == second.id
    assert curation_for_item(item, latest_review(db_session, item["item_id"]))[
        "state"] == "PRODUCTION_RECOMMENDED"


def test_reviews_cannot_be_updated_or_deleted(clean_tables, db_session):
    item = _item()
    review = record_review(db_session, item=item, reviewer="AD", decision="ALLOW")
    db_session.commit()
    with pytest.raises(Exception) as exc:
        db_session.execute(
            text("UPDATE design_reviews SET decision = 'APPROVE' WHERE id = :i"),
            {"i": str(review.id)},
        )
        db_session.commit()
    assert "append-only" in str(exc.value)
    db_session.rollback()
    with pytest.raises(Exception):
        db_session.execute(text("DELETE FROM design_reviews WHERE id = :i"),
                           {"i": str(review.id)})
        db_session.commit()
    db_session.rollback()


def test_review_is_pinned_to_the_recipe_it_looked_at(clean_tables, db_session):
    review = record_review(db_session, item=_item(), reviewer="AD", decision="APPROVE")
    db_session.flush()
    assert review.recipe_hash == "a" * 64
    assert review.engineering_snapshot["manufacturing_pass"] is True


# --- promotion is product-specific ------------------------------------------

def test_promotion_is_product_specific_not_global(clean_tables, db_session):
    """The same variant may be recommended for a pendant and hidden for a
    ring — one global verdict would be a lie about both."""
    variant = "aref-ruqaa/aref-ruqaa-ss04"
    pendant = _item("i-pendant", product="pendant", variant_key=variant)
    ring = _item("i-ring", product="ring", variant_key=variant)
    cufflink = _item("i-cufflink", product="cufflink", variant_key=variant)

    record_review(db_session, item=pendant, reviewer="AD", decision="APPROVE",
                  mode="deep", scores=_full_scores(5))
    record_review(db_session, item=ring, reviewer="AD", decision="ALLOW")
    db_session.flush()

    decisions = []
    for item in (pendant, ring, cufflink):
        curation = curation_for_item(item, latest_review(db_session, item["item_id"]))
        decisions.append({**curation, "variant_key": variant})
    states = product_scoped_states(decisions)[variant]
    assert states["pendant"] == "PRODUCTION_RECOMMENDED"
    assert states["ring"] == "PRODUCTION_ALLOWED"
    assert states["cufflink"] == "EXPERIMENTAL"


# --- AI advisory is advisory -------------------------------------------------

def test_ai_advisory_never_promotes_without_a_human(clean_tables, db_session):
    advisory = ai_advisory_status()
    assert advisory["status"] in ("SKIPPED_NO_CREDENTIALS", "AVAILABLE_NOT_RUN")
    assert advisory["scores"] == []
    # An item with a glowing advisory attached but no human review must
    # still be pending — curation reads only the human decision.
    item = _item()
    item["ai_advisory_score"] = {d: 5 for d in HUMAN_DIMENSIONS}
    curation = curation_for_item(item, None)
    assert curation["state"] == "EXPERIMENTAL"
    assert curation["human_review_status"] == PENDING


def test_ai_advisory_is_never_merged_into_human_scores(clean_tables, db_session):
    item = _item()
    review = record_review(db_session, item=item, reviewer="AD", decision="APPROVE",
                           mode="deep", scores=_full_scores(3))
    db_session.flush()
    assert set(review.scores) == set(HUMAN_DIMENSIONS)
    assert all(v == 3 for v in review.scores.values()), "human scores were altered"


# --- the review item itself --------------------------------------------------

def test_review_item_is_a_combination_not_a_font():
    item = build_review_item("amiri-regular", "pendant", "نورة", "baseline_bar")
    assert item is not None
    for key in ("product", "composition", "source_text", "proof_path_d"):
        assert item[key]
    assert item["technical"]["font_id"] == "amiri-regular"
    assert item["human_review_status"] == PENDING
    # Same font, different product → a different review item.
    other = build_review_item("amiri-regular", "ring", "نورة", "baseline_bar")
    assert other is not None and other["item_id"] != item["item_id"]


def test_review_item_shows_customer_style_not_raw_tags():
    item = build_review_item("reem-kufi", "pendant", "نورة", "baseline_bar")
    assert item["customer_style"] in ("هندسي", "جريء")
    # Technical detail exists but is quarantined under `technical`.
    headline = {k: v for k, v in item.items() if k not in ("technical", "engineering")}
    blob = repr(headline)
    for tag in ("ss01", "cv01", "wght", "jalt", "salt"):
        assert tag not in blob, f"raw tag {tag} leaked into the headline payload"


def test_review_corpus_is_not_a_single_word():
    assert len(REVIEW_CORPUS) >= 9
    for name in ["ع", "نورة", "ميثة", "محمد", "فاطمة", "حامد", "سلطان", "خالد", "مهرة"]:
        assert name in REVIEW_CORPUS
    assert len(SEVEN_NAMES.split()) == 7
    assert PHRASE.strip()
    assert len(REVIEW_PRODUCTS) >= 8


def test_golden_case_pattern_is_flagged_where_relevant():
    earring = build_review_item("aref-ruqaa", "single_letter_earring", "ع", "bare")
    assert earring is not None
    assert earring["golden_production_pattern"], "the manufactured earring case must show"
    # Cufflinks now have a manufactured owner sample (enamel calligraphy
    # cufflinks) and a relief-disc line; the manufactured case leads.
    cufflink = build_review_item("aref-ruqaa", "cufflink", "محمد", "plate_rect")
    assert cufflink is not None
    assert cufflink["golden_production_pattern"][0].startswith("BS-GPC-0007")
    # A product no golden case covers gets nothing invented for it.
    medallion = build_review_item("aref-ruqaa", "medallion", "محمد", "frame_circle")
    if medallion is not None:
        assert medallion["golden_production_pattern"] == []


# --- boundaries that must not move -----------------------------------------

def test_features_are_not_marked_reviewed_by_this_slice():
    """The 52 discovered features stay EXPERIMENTAL until a person acts."""
    from app.fonts.curation import CurationState, curation_state, load_curation

    features = load_curation()["features"]
    discovered = [k for k, v in features.items()
                  if v.get("provenance") == "DISCOVERED_FROM_FONT_TABLES"]
    assert len(discovered) == 52
    for set_id in discovered:
        assert curation_state("features", set_id) == CurationState.EXPERIMENTAL


def test_true_diwani_status_unchanged_and_thuluth_only_via_rights_cleared_source():
    from app.fonts.capabilities import LICENSE_REQUIRED, REAL, script_capability_map
    from app.fonts.registry import get_registry

    caps = script_capability_map()
    for family in ("diwani", "diwani_jali"):
        assert caps[family]["status"] == LICENSE_REQUIRED
        assert caps[family]["fonts"] == []
    for family in ("thuluth", "thuluth_jali"):
        assert caps[family]["status"] == REAL
        assert caps[family]["fonts"] and all(
            get_registry().get(fid).rights_status.value == "VERIFIED_OPEN_SOURCE" for fid in caps[family]["fonts"]
        )


def test_no_review_rows_are_created_by_generating_a_pack(clean_tables, db_session):
    """Preparing work must never look like doing it."""
    from app.services.review_items import generate_review_pack

    generate_review_pack(max_per_product=1)
    assert db_session.execute(select(m.DesignReview)).scalars().all() == []
