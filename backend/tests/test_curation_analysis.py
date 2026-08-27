"""P2 curation analysis and customer validation regressions.

The contamination this file guards against: taste inferred from geometry,
customer opinion averaged with expert opinion, or a confident family claim
built on two reviews.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services.curation_analysis import (
    INSUFFICIENT, ITEM_HIGH_CONFIDENCE, ITEM_LOW_CONFIDENCE,
    ITEM_MEDIUM_CONFIDENCE, ITEM_NO_CONFIDENCE, MIN_FAMILIES_FOR_COMPARISON,
    MIN_REVIEWS_PER_CANDIDATE, NOT_COMPARISON_READY, SIGNAL_DIMENSIONS,
    STRUCTURALLY_IMPOSSIBLE, agreement_report, best_aesthetic_family_for_product,
    best_commercial_family_for_product, commercial_class, commercial_curation,
    confidence_for, derive_aesthetic_signals, golden_pattern_validation,
    item_confidence, load_review_evidence, overall_best_aesthetic_family,
    product_comparison_readiness, review_quality_check, threshold_audit,
)
from app.services.customer_validation import (
    MIN_RESPONSES_FOR_FAMILY_CLAIM, ResponseRejected, best_customer_family,
    customer_signals, record_customer_response, select_customer_pack,
)
from app.services.review_workflow import HUMAN_DIMENSIONS, PENDING, record_review

GOOD = {"arabic_identity_pass": True, "manufacturing_pass": True, "rights_pass": True}


def _item(item_id="i1", product="pendant", font_id="amiri-regular",
          engineering=None, golden=None, **over):
    base = {
        "item_id": item_id, "recipe_hash": "a" * 64, "product": product,
        "font_id": font_id, "feature_set": "default", "font_axes": {},
        "source_text": "نورة", "composition": "baseline_bar",
        "technical": {"font_id": font_id, "feature_set": "default", "font_axes": {}},
        "engineering": dict(engineering or GOOD),
        "golden_production_pattern": golden or [],
        "customer_style": "كلاسيكي", "width_mm": 20.0, "height_mm": 12.0,
        "proof_path_d": "M0 0 L1 0 L1 1 Z", "proof_view": [20.0, 12.0],
    }
    base.update(over)
    return base


def _scores(value=4, **over):
    s = {d: value for d in HUMAN_DIMENSIONS}
    s.update(over)
    return s


def _review(session, item, reviewer="AD", decision="APPROVE", scores=None):
    return record_review(session, item=item, reviewer=reviewer, decision=decision,
                         mode="deep" if scores else "quick", scores=scores)


# --- 1. evidence loading ----------------------------------------------------

def test_evidence_reports_zero_honestly_when_nothing_is_reviewed(clean_tables, db_session):
    items = [_item(f"i{n}") for n in range(4)]
    evidence = load_review_evidence(db_session, items)
    assert evidence["total_reviews"] == 0
    assert evidence["unreviewed_items"] == 4
    assert evidence["overall_confidence"] == "NONE"
    assert evidence["status"] == PENDING
    assert evidence["decisions"] == {"APPROVE": 0, "ALLOW": 0, "EXPERIMENTAL": 0, "HIDE": 0}


def test_coverage_is_reported_per_product_and_font(clean_tables, db_session):
    items = [_item("i1", product="ring"), _item("i2", product="pendant", font_id="cairo")]
    _review(db_session, items[0], reviewer="AD 1", decision="ALLOW")
    db_session.flush()
    evidence = load_review_evidence(db_session, items)
    assert evidence["coverage_by_product"]["ring"]["reviews"] == 1
    assert evidence["coverage_by_product"]["pendant"]["reviews"] == 0
    assert "pendant" in evidence["missing_areas"]
    assert evidence["coverage_by_font"]["cairo"]["reviews"] == 0


def test_confidence_is_driven_by_reviewer_count_not_volume():
    """One person reviewing nine items is still one opinion."""
    assert confidence_for(0, 0) == "NONE"
    assert confidence_for(9, 1) == "LOW", "volume from one reviewer is not confidence"
    assert confidence_for(4, 2) == "MEDIUM"
    assert confidence_for(6, 3) == "HIGH"


def test_item_confidence_two_reviewers_is_medium_not_high():
    """The retired model claimed a second reviewer unlocked HIGH."""
    assert item_confidence(0) == ITEM_NO_CONFIDENCE
    assert item_confidence(1) == ITEM_LOW_CONFIDENCE
    assert item_confidence(2) == ITEM_MEDIUM_CONFIDENCE
    assert item_confidence(3) == ITEM_HIGH_CONFIDENCE
    assert item_confidence(4, agreement_ok=False) == ITEM_MEDIUM_CONFIDENCE


# --- 2. quality check --------------------------------------------------------

def test_contradictory_reviews_are_flagged_not_resolved(clean_tables, db_session):
    item = _item()
    _review(db_session, item, reviewer="AD 1", decision="APPROVE")
    _review(db_session, item, reviewer="AD 2", decision="HIDE")
    db_session.flush()
    report = review_quality_check(db_session, [item])
    assert len(report["contradictory_reviews"]) == 1
    assert report["reviewer_decisions_modified"] == 0


def test_manufacturing_failing_but_approved_is_flagged(clean_tables, db_session):
    item = _item(engineering={**GOOD, "manufacturing_pass": False})
    _review(db_session, item, reviewer="AD", decision="APPROVE")
    db_session.flush()
    report = review_quality_check(db_session, [item])
    flagged = report["manufacturing_failing_but_allowed"]
    assert len(flagged) == 1
    assert flagged[0]["resolved_state"] == "HIDDEN"
    assert "manufacturing_pass" in flagged[0]["failed_gates"]


# --- 3. aesthetic signals come from humans only -----------------------------

def test_signals_derive_only_from_human_dimensions(clean_tables, db_session):
    item = _item()
    _review(db_session, item, scores=_scores(4))
    db_session.flush()
    signals = derive_aesthetic_signals(db_session, [item])
    assert signals["basis"] == "HUMAN_REVIEW_SCORES_ONLY"
    assert "engineering suitability" in signals["excluded_inputs"]
    for dims in SIGNAL_DIMENSIONS.values():
        assert set(dims) <= set(HUMAN_DIMENSIONS), "a signal used a non-human dimension"
    assert signals["product"]["pendant"]["human_aesthetic_score"] == 4.0


def test_engineering_values_never_move_an_aesthetic_signal(clean_tables, db_session):
    """Same human scores, opposite engineering — the signal must not budge."""
    strong = _item("i-strong", engineering={**GOOD})
    weak = _item("i-weak", product="ring", engineering={**GOOD})
    strong["engineering"]["min_material_width_mm"] = 9.9
    weak["engineering"]["min_material_width_mm"] = 0.7
    _review(db_session, strong, scores=_scores(3))
    _review(db_session, weak, scores=_scores(3))
    db_session.flush()
    signals = derive_aesthetic_signals(db_session, [strong, weak])
    assert (signals["product"]["pendant"]["human_aesthetic_score"]
            == signals["product"]["ring"]["human_aesthetic_score"] == 3.0)


def test_unscored_quick_reviews_do_not_create_signals(clean_tables, db_session):
    item = _item()
    _review(db_session, item, decision="APPROVE")  # quick, no scores
    db_session.flush()
    signals = derive_aesthetic_signals(db_session, [item])
    assert signals["product"] == {}, "a quick decision is not an aesthetic score"


# --- 4. commercial curation --------------------------------------------------

def test_hard_gate_beats_approval_in_commercial_class():
    item = _item(engineering={**GOOD, "rights_pass": False})

    class R:
        decision, scores, reviewer = "APPROVE", None, "AD"

    result = commercial_class(item, R)
    assert result["state"] == "HIDDEN"
    assert result["reason"] == "BLOCKED_BY_HARD_GATE"


def test_unreviewed_item_is_a_design_experiment(clean_tables, db_session):
    item = _item()
    states = commercial_curation(db_session, [item])
    assert states[0]["state"] == "DESIGN_EXPERIMENT"
    assert states[0]["reason"] == PENDING


def test_weak_critical_score_yields_commercial_candidate(clean_tables, db_session):
    item = _item()
    _review(db_session, item, scores=_scores(5, Legibility=2))
    db_session.flush()
    result = commercial_curation(db_session, [item])[0]
    assert result["state"] == "COMMERCIAL_CANDIDATE"
    assert "Legibility" in result["weak_critical_dimensions"]


def test_full_approval_reaches_production_recommended(clean_tables, db_session):
    item = _item()
    _review(db_session, item, scores=_scores(5))
    db_session.flush()
    assert commercial_curation(db_session, [item])[0]["state"] == "PRODUCTION_RECOMMENDED"


# --- 5. threshold audit + comparison readiness -------------------------------

def test_audit_detects_the_structurally_impossible_threshold():
    """One item per (product, family) makes ">=3 distinct items" unmeetable."""
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    audit = threshold_audit(items)
    assert audit["max_items_per_product_family"] == 1
    assert audit["retired_rule"]["status"] == STRUCTURALLY_IMPOSSIBLE
    assert audit["impossible_rules"]
    assert audit["achievable_rules"]


def test_product_not_comparison_ready_without_three_reviewed_families(
    clean_tables, db_session
):
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    for item in items[:2]:
        for reviewer in ("AD 1", "AD 2"):
            _review(db_session, item, reviewer=reviewer, scores=_scores(5))
    db_session.flush()
    ready = product_comparison_readiness(db_session, items)["pendant"]
    assert ready["status"] == NOT_COMPARISON_READY
    assert ready["families_with_enough_reviews"] == 2
    assert ready["required_families"] == MIN_FAMILIES_FOR_COMPARISON
    assert "1 more font family" in ready["shortfall"]


def test_one_reviewer_per_family_is_not_comparison_ready(clean_tables, db_session):
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    for item in items:
        _review(db_session, item, reviewer="AD 1", scores=_scores(5))
    db_session.flush()
    ready = product_comparison_readiness(db_session, items)["pendant"]
    assert ready["status"] == NOT_COMPARISON_READY
    assert ready["required_reviews_per_family"] == MIN_REVIEWS_PER_CANDIDATE


def test_best_aesthetic_family_derives_when_comparison_ready(clean_tables, db_session):
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    for n, item in enumerate(items):
        for reviewer in ("AD 1", "AD 2"):
            _review(db_session, item, reviewer=reviewer, scores=_scores(3 + n))
    db_session.flush()
    result = best_aesthetic_family_for_product(db_session, items)["pendant"]
    assert result["status"] == "DERIVED"
    assert result["font_family"] == "reem-kufi", "highest mean must win"
    assert result["independent_reviews"] == 2
    assert result["runners_up"]


def test_weak_critical_score_excludes_a_candidate_from_winning(clean_tables, db_session):
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    for n, item in enumerate(items):
        # The otherwise-highest scorer is illegible.
        scores = _scores(5, Legibility=2) if n == 2 else _scores(4)
        for reviewer in ("AD 1", "AD 2"):
            _review(db_session, item, reviewer=reviewer, scores=scores)
    db_session.flush()
    result = best_aesthetic_family_for_product(db_session, items)["pendant"]
    assert result["status"] == "DERIVED"
    assert result["font_family"] != "reem-kufi"


def test_commercial_family_needs_the_commercial_floors(clean_tables, db_session):
    items = [_item(f"i{n}", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi"])]
    for item in items:  # good aesthetics, weak commercial appeal
        for reviewer in ("AD 1", "AD 2"):
            _review(db_session, item, reviewer=reviewer,
                    scores=_scores(5, CommercialAppeal=2, PremiumFeel=2))
    db_session.flush()
    result = best_commercial_family_for_product(db_session, items)["pendant"]
    assert result["status"] == INSUFFICIENT
    assert result["commercial_floors"]["CommercialAppeal"] == 4


def test_overall_claim_needs_breadth_across_products(clean_tables, db_session):
    items = [_item("i1", product="pendant"), _item("i2", product="ring")]
    for item in items:
        for reviewer in ("AD 1", "AD 2"):
            _review(db_session, item, reviewer=reviewer, scores=_scores(5))
    db_session.flush()
    result = overall_best_aesthetic_family(db_session, items)
    assert result["status"] == INSUFFICIENT, "two products is not breadth"
    assert result["required"]["products"] == 3


# --- 6. golden validation is allowed to say "no" ----------------------------

def test_golden_validation_reports_insufficient_without_reviews(clean_tables, db_session):
    items = [_item("i1", golden=["BS-GPC-0001"]), _item("i2")]
    result = golden_pattern_validation(db_session, items)
    assert result["verdict"] == INSUFFICIENT
    assert result["predictive_or_historical"] == "UNDETERMINED"


def test_golden_can_be_reported_as_not_predictive(clean_tables, db_session):
    """Golden cases are never forced to win."""
    golden = _item("i-golden", golden=["BS-GPC-0001"])
    plain = _item("i-plain", product="ring")
    _review(db_session, golden, decision="HIDE")
    _review(db_session, plain, decision="APPROVE")
    db_session.flush()
    result = golden_pattern_validation(db_session, [golden, plain])
    assert result["verdict"] == "NOT_CORRELATED"
    assert result["predictive_or_historical"] == "HISTORICAL_ONLY"


# --- 7-8. customer validation stays separate --------------------------------

def test_customer_pack_only_contains_manufacturable_items(clean_tables, db_session):
    items = [_item(f"i{n}", product=p) for n, p in enumerate(
        ["pendant", "ring", "necklace"])]
    items.append(_item("bad", product="cufflink",
                       engineering={**GOOD, "manufacturing_pass": False}))
    pack = select_customer_pack(db_session, items)
    assert all(i["engineering"]["manufacturing_pass"] for i in pack["items"])
    assert "bad" not in {i["item_id"] for i in pack["items"]}


def test_pack_selection_basis_is_honest_without_expert_review(clean_tables, db_session):
    items = [_item(f"i{n}", product=p) for n, p in enumerate(["pendant", "ring"])]
    pack = select_customer_pack(db_session, items)
    assert pack["selection_basis"] == "MANUFACTURING_PASS_AND_DIVERSITY_ONLY"
    assert pack["expert_reviewed_items"] == 0
    assert "NOT" in pack["note"]


def test_pack_caps_items_per_product(clean_tables, db_session):
    items = [_item(f"i{n}", product="pendant", font_id=f) for n, f in enumerate(
        ["amiri-regular", "cairo", "reem-kufi", "tajawal"])]
    pack = select_customer_pack(db_session, items, max_per_product=2)
    assert pack["product_spread"]["pendant"] <= 2


def test_customer_responses_are_validated(clean_tables, db_session):
    with pytest.raises(ResponseRejected):
        record_customer_response(db_session, item_id="i1", pack_id="p", respondent_token="t",
                                 would_buy="definitely", premium_feel=3, readability=3,
                                 uniqueness=3)
    with pytest.raises(ResponseRejected):
        record_customer_response(db_session, item_id="i1", pack_id="p", respondent_token="t",
                                 would_buy="yes", premium_feel=9, readability=3, uniqueness=3)
    with pytest.raises(ResponseRejected):
        record_customer_response(db_session, item_id="i1", pack_id="p", respondent_token="",
                                 would_buy="yes", premium_feel=3, readability=3, uniqueness=3)


def test_customer_scores_never_enter_expert_signals(clean_tables, db_session):
    item = _item()
    _review(db_session, item, scores=_scores(2))
    for n in range(6):
        record_customer_response(db_session, item_id=item["item_id"], pack_id="p",
                                 respondent_token=f"tok{n}", would_buy="yes",
                                 premium_feel=5, readability=5, uniqueness=5)
    db_session.flush()
    expert = derive_aesthetic_signals(db_session, [item])
    assert expert["product"]["pendant"]["human_aesthetic_score"] == 2.0, (
        "enthusiastic customers must not lift the expert signal"
    )
    customer = customer_signals(db_session, [item])
    assert customer["basis"] == "CUSTOMER_RESPONSES_ONLY"
    assert "expert human review scores" in customer["excluded_inputs"]
    assert customer["per_item"][item["item_id"]]["premium_feel"] == 5.0


def test_customer_responses_are_anonymous_and_append_only(clean_tables, db_session):
    row = record_customer_response(db_session, item_id="i1", pack_id="p",
                                   respondent_token="tok", would_buy="maybe",
                                   premium_feel=4, readability=4, uniqueness=3)
    db_session.commit()
    columns = {c.name for c in row.__table__.columns}
    for identifying in ("name", "email", "phone", "customer_id", "ip"):
        assert identifying not in columns, f"{identifying} would de-anonymise a respondent"
    with pytest.raises(Exception) as exc:
        db_session.execute(
            text("UPDATE customer_validation_responses SET would_buy='no' WHERE id=:i"),
            {"i": str(row.id)})
        db_session.commit()
    assert "append-only" in str(exc.value)
    db_session.rollback()


def test_best_customer_family_needs_enough_responses(clean_tables, db_session):
    item = _item()
    for n in range(3):
        record_customer_response(db_session, item_id=item["item_id"], pack_id="p",
                                 respondent_token=f"t{n}", would_buy="yes",
                                 premium_feel=5, readability=5, uniqueness=5)
    db_session.flush()
    result = best_customer_family(db_session, [item])["pendant"]
    assert result["status"] == INSUFFICIENT
    assert result["required_responses_per_family"] == MIN_RESPONSES_FOR_FAMILY_CLAIM


# --- 9. the four claims stay distinct ---------------------------------------

def test_the_four_family_claims_have_different_bases(clean_tables, db_session):
    """Collapsing them would be the misleading claim the brief forbids."""
    items = [_item()]
    aesthetic = best_aesthetic_family_for_product(db_session, items)
    commercial = best_commercial_family_for_product(db_session, items)
    customer = best_customer_family(db_session, items)
    assert SIGNAL_DIMENSIONS["human_aesthetic_score"] != SIGNAL_DIMENSIONS["commercial_appeal_score"]
    assert aesthetic["pendant"]["status"] == NOT_COMPARISON_READY
    assert commercial["pendant"]["status"] == NOT_COMPARISON_READY
    assert customer["pendant"]["status"] == INSUFFICIENT
    signals = derive_aesthetic_signals(db_session, items)
    assert "AI advisory" in signals["excluded_inputs"]


# --- agreement is surfaced, not averaged away -------------------------------

def test_disagreement_on_a_critical_dimension_is_flagged(clean_tables, db_session):
    item = _item()
    _review(db_session, item, reviewer="AD 1", scores=_scores(5, Legibility=5))
    _review(db_session, item, reviewer="AD 2", scores=_scores(5, Legibility=2))
    db_session.flush()
    report = agreement_report(db_session, item["item_id"])
    assert report["flag"] == "REVIEWER_DISAGREEMENT"
    assert report["agreement_ok"] is False
    legibility = report["per_dimension"]["Legibility"]
    assert legibility["spread"] == 3
    # The mean is reported, but never on its own.
    assert legibility["mean"] == 3.5 and legibility["values"] == [5, 2]


def test_agreement_without_disagreement_is_clean(clean_tables, db_session):
    item = _item()
    for reviewer in ("AD 1", "AD 2", "AD 3"):
        _review(db_session, item, reviewer=reviewer, scores=_scores(4))
    db_session.flush()
    report = agreement_report(db_session, item["item_id"])
    assert report["flag"] is None
    assert report["independent_reviews"] == 3
    assert report["confidence"] == ITEM_HIGH_CONFIDENCE


def test_a_revised_opinion_does_not_count_as_a_second_reviewer(clean_tables, db_session):
    """Independence is about people, not rows."""
    item = _item()
    _review(db_session, item, reviewer="AD 1", scores=_scores(2))
    _review(db_session, item, reviewer="AD 1", scores=_scores(5))
    db_session.flush()
    report = agreement_report(db_session, item["item_id"])
    assert report["independent_reviews"] == 1
    assert report["confidence"] == ITEM_LOW_CONFIDENCE
    # The newest opinion is the one that counts for that reviewer.
    assert report["per_dimension"]["Elegance"]["values"] == [5]


def test_three_reviewers_who_disagree_do_not_reach_high_confidence(
    clean_tables, db_session
):
    item = _item()
    _review(db_session, item, reviewer="AD 1", scores=_scores(5, ProductFit=5))
    _review(db_session, item, reviewer="AD 2", scores=_scores(5, ProductFit=2))
    _review(db_session, item, reviewer="AD 3", scores=_scores(5, ProductFit=4))
    db_session.flush()
    report = agreement_report(db_session, item["item_id"])
    assert report["independent_reviews"] == 3
    assert report["flag"] == "REVIEWER_DISAGREEMENT"
    assert report["confidence"] == ITEM_MEDIUM_CONFIDENCE


# --- Wave 1 ------------------------------------------------------------------

def test_wave_1_is_labelled_and_not_called_a_winner():
    from app.services.review_items import WAVE_1, build_wave_1

    wave = build_wave_1()
    assert wave["wave"] == WAVE_1
    assert wave["status"] == "AWAITING_HUMAN_REVIEW"
    assert "Not curated winners" in wave["note"]
    assert wave["size"] <= 15
    assert all(i["wave"] == WAVE_1 for i in wave["items"])


def test_wave_1_only_offers_manufacturable_candidates():
    from app.services.review_items import build_wave_1

    for item in build_wave_1()["items"]:
        assert item["manufacturing_pass"] is True


def test_wave_1_reports_products_that_cannot_reach_comparison():
    """A product with too few rival families is flagged, not padded."""
    from app.services.review_items import build_wave_1

    wave = build_wave_1()
    for product, notes in wave["per_product"].items():
        if notes["can_reach_comparison_ready"]:
            assert len(notes["font_families"]) >= 3
            assert notes["blocker"] is None
        else:
            assert notes["blocker"], f"{product} blocked without a reason"
