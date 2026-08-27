"""P2 curation analysis and customer validation regressions.

The contamination this file guards against: taste inferred from geometry,
customer opinion averaged with expert opinion, or a confident family claim
built on two reviews.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services.curation_analysis import (
    INSUFFICIENT, MIN_DEEP_REVIEWS_FOR_CLAIM, MIN_DISTINCT_ITEMS_FOR_CLAIM,
    SIGNAL_DIMENSIONS, best_family, commercial_class, commercial_curation,
    confidence_for, derive_aesthetic_signals, golden_pattern_validation,
    load_review_evidence, review_quality_check,
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


def test_confidence_needs_volume_and_more_than_one_reviewer():
    assert confidence_for(0, 0) == "NONE"
    assert confidence_for(2, 1) == "LOW"
    assert confidence_for(9, 1) == "MEDIUM", "one reviewer alone is never HIGH confidence"
    assert confidence_for(MIN_DEEP_REVIEWS_FOR_CLAIM, 2) == "HIGH"


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
    _review(db_session, item, scores=_scores(5, Readability=2))
    db_session.flush()
    result = commercial_curation(db_session, [item])[0]
    assert result["state"] == "COMMERCIAL_CANDIDATE"
    assert "Readability" in result["weak_critical_dimensions"]


def test_full_approval_reaches_production_recommended(clean_tables, db_session):
    item = _item()
    _review(db_session, item, scores=_scores(5))
    db_session.flush()
    assert commercial_curation(db_session, [item])[0]["state"] == "PRODUCTION_RECOMMENDED"


# --- 5. best family requires real evidence ----------------------------------

def test_best_family_refuses_to_guess_without_evidence(clean_tables, db_session):
    items = [_item(f"i{n}") for n in range(3)]
    result = best_family(db_session, items, "human_aesthetic_score")
    assert result["pendant"]["status"] == INSUFFICIENT
    assert result["pendant"]["required"]["scored_reviews_per_family"] == MIN_DEEP_REVIEWS_FOR_CLAIM


def test_thin_evidence_is_excluded_with_a_reason(clean_tables, db_session):
    items = [_item(f"i{n}") for n in range(2)]
    for item in items:
        _review(db_session, item, scores=_scores(5))
    db_session.flush()
    result = best_family(db_session, items, "human_aesthetic_score")["pendant"]
    assert result["status"] == INSUFFICIENT
    assert result["exclusions"][0]["reason"] == "below evidence threshold"


def test_best_family_derives_once_thresholds_are_met(clean_tables, db_session):
    items = [_item(f"i{n}") for n in range(MIN_DEEP_REVIEWS_FOR_CLAIM)]
    for n, item in enumerate(items):
        _review(db_session, item, reviewer=f"AD {n % 2}", scores=_scores(4))
    db_session.flush()
    result = best_family(db_session, items, "human_aesthetic_score")["pendant"]
    assert result["status"] == "DERIVED"
    assert result["font_family"] == "amiri-regular"
    assert result["review_count"] >= MIN_DEEP_REVIEWS_FOR_CLAIM
    assert result["distinct_items"] >= MIN_DISTINCT_ITEMS_FOR_CLAIM
    assert result["supporting_reviews"]


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
    aesthetic = best_family(db_session, items, "human_aesthetic_score")
    commercial = best_family(db_session, items, "commercial_appeal_score")
    customer = best_customer_family(db_session, items)
    assert SIGNAL_DIMENSIONS["human_aesthetic_score"] != SIGNAL_DIMENSIONS["commercial_appeal_score"]
    for result in (aesthetic["pendant"], commercial["pendant"], customer["pendant"]):
        assert result["status"] == INSUFFICIENT
    signals = derive_aesthetic_signals(db_session, items)
    assert "AI advisory" in signals["excluded_inputs"]
