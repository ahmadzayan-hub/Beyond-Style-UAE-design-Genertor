"""Golden Production Memory regression tests.

The two behaviours that must never regress:
  1. A future request in a proven product family RETRIEVES the real case
     as memory, ranked above lower-evidence sources.
  2. Retrieval never hands back the original geometry — a new design is
     generated from the customer's own confirmed text.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as m
from app.services.golden_memory import (
    EVIDENCE_TIER_WEIGHTS,
    GEOMETRY_KEYS,
    GOLDEN_TIER,
    PENDING_TIER,
    compare_case_stages,
    confirm_customer_source_text,
    golden_case_generation_hints,
    golden_training_export,
    retrieve_golden_cases,
    seed_golden_cases,
)

ARABIC_CASE = "BS-GPC-0001-arabic-letter-pearl-earrings"
NECKLACE_CASE = "BS-GPC-0002-layered-name-necklace-adam-omar"


@pytest.fixture
def seeded(db_session):
    session = db_session
    session.execute(m.GoldenProductionCase.__table__.delete())
    seed_golden_cases(session)
    session.flush()
    return session


def _case(session, case_id) -> m.GoldenProductionCase:
    return session.execute(
        select(m.GoldenProductionCase).where(m.GoldenProductionCase.case_id == case_id)
    ).scalar_one()


def test_seed_is_idempotent(seeded):
    assert seed_golden_cases(seeded) == []
    rows = seeded.execute(select(m.GoldenProductionCase)).scalars().all()
    from app.data.golden_production_cases import GOLDEN_PRODUCTION_CASES
    assert len(rows) == len(GOLDEN_PRODUCTION_CASES) == 38


def test_arabic_letter_earring_request_retrieves_the_real_case(seeded):
    results = retrieve_golden_cases(
        seeded,
        {
            "product_type": "drop_earring",
            "script_family": "modern_arabic",
            "composition": "vertical",
            "keywords": ["pearl arabic earrings", "minimal arabic earrings"],
        },
    )
    assert results, "a proven case must be retrievable as memory"
    assert results[0]["case_id"] == ARABIC_CASE
    assert results[0]["keyword_matches"]
    assert results[0]["lessons_learned"]


def test_layered_english_name_necklace_request_retrieves_the_real_case(seeded):
    results = retrieve_golden_cases(
        seeded,
        {
            "product_type": "necklace",
            "script_family": "latin_script",
            "composition": "stacked",
            "keywords": ["layered necklace", "two name necklace", "stacked letters necklace"],
        },
    )
    assert results[0]["case_id"] == NECKLACE_CASE
    assert results[0]["evidence_tier"] == "MANUFACTURED_CUSTOMER_APPROVED"


def test_manufactured_approved_memory_outranks_lower_evidence_tiers(seeded):
    """Learning priority: manufactured + customer-approved > designer-
    approved > unmanufactured AI concept > external inspiration."""
    weights = EVIDENCE_TIER_WEIGHTS
    assert (
        weights["MANUFACTURED_CUSTOMER_APPROVED"]
        > weights["DESIGNER_APPROVED"]
        > weights["AI_GENERATED_UNMANUFACTURED"]
        > weights["EXTERNAL_INSPIRATION"]
    )
    case = _case(seeded, NECKLACE_CASE)
    demoted = m.GoldenProductionCase(
        case_id="TEST-external-inspiration",
        source_text_status="PENDING_CUSTOMER_VERIFICATION",
        source_text_authority="NOT_ESTABLISHED",
        language="EN",
        product_type="LAYERED_NAME_NECKLACE",
        construction=case.construction,
        lineage_status="EXTERNAL",
        manufacturing_result="NOT_MANUFACTURED",
        production_success=False,
        customer_sentiment="UNKNOWN",
        customer_approved=False,
        memory_tier=PENDING_TIER,
        evidence_tier="EXTERNAL_INSPIRATION",
        ranking_weight="LOW",
        design_dna=case.design_dna,
        dna_embedding=list(case.dna_embedding),  # identical DNA → tier decides
        encoder_version=case.encoder_version,
        retrieval_keywords=list(case.retrieval_keywords),
        rights_provenance="UNKNOWN",
        privacy_status="PRIVATE",
        evidence=[],
    )
    seeded.add(demoted)
    seeded.flush()

    results = retrieve_golden_cases(
        seeded,
        {"product_type": "necklace", "script_family": "latin_script", "composition": "stacked",
         "keywords": ["layered necklace"]},
        top_k=50,
    )
    ranked = [r["case_id"] for r in results]
    assert ranked.index(NECKLACE_CASE) < ranked.index("TEST-external-inspiration")


def test_retrieval_never_returns_original_geometry(seeded):
    """The case is memory, not a template: no geometry or lineage key may
    leave retrieval, so the generator must build new original outlines."""
    results = retrieve_golden_cases(
        seeded, {"product_type": "necklace", "composition": "stacked"}
    )
    for result in results:
        assert not (GEOMETRY_KEYS & set(result))

    hints = golden_case_generation_hints(_case(seeded, NECKLACE_CASE))
    assert not (GEOMETRY_KEYS & set(hints))
    assert hints["copies_original_geometry"] is False
    assert hints["requires_customer_confirmed_text"] is True
    # Style grammar and proven engineering DO transfer.
    assert hints["construction_principles"] == [
        "OUTER_CHAIN", "INNER_CENTER_DROP", "VERTICAL_NAME_ELEMENTS"
    ]
    assert hints["proven_lessons"]
    assert "preferred_compositions" in hints


def test_confirmed_names_are_stored_exactly_and_never_inferred(seeded):
    necklace = _case(seeded, NECKLACE_CASE)
    assert necklace.primary_names == ["ADAM", "OMAR"]
    assert necklace.customer_source_text == "ADAM\nOMAR"
    assert necklace.source_text_status == "CONFIRMED"
    assert necklace.memory_tier == GOLDEN_TIER

    # The Arabic case has no authoritative text yet: it is held below the
    # golden tier rather than having letters read off a photograph.
    arabic = _case(seeded, ARABIC_CASE)
    assert arabic.customer_source_text is None
    assert arabic.source_text_status == "PENDING_CUSTOMER_VERIFICATION"
    assert arabic.memory_tier == PENDING_TIER


def test_unverified_text_is_excluded_from_training_export(seeded):
    exported = {c["case_id"] for c in golden_training_export(seeded)}
    assert NECKLACE_CASE in exported
    assert ARABIC_CASE not in exported


def test_personal_conversation_evidence_is_never_stored_or_exported(seeded):
    for case_id in (ARABIC_CASE, NECKLACE_CASE):
        case = _case(seeded, case_id)
        conversations = [e for e in case.evidence if e["role"] == "customer_conversation"]
        assert conversations, "the conversation must still be registered by hash"
        for item in conversations:
            assert item["storage_status"] == "EXCLUDED_PERSONAL_DATA"
            assert item["storage_key"] is None
        # Only a normalized, de-identified sentence survives.
        assert case.customer_sentiment == "HIGHLY_POSITIVE"
        assert "customer" in (case.customer_feedback or "").lower()

    for exported in golden_training_export(seeded):
        assert all(e["storage_status"] != "EXCLUDED_PERSONAL_DATA" for e in exported["evidence"])


def test_confirming_source_text_promotes_the_pending_case(seeded):
    case = confirm_customer_source_text(
        seeded, ARABIC_CASE, "مي", authority="ORDER_RECORD", actor="workshop_admin"
    )
    assert case.source_text_status == "CONFIRMED"
    assert case.memory_tier == GOLDEN_TIER
    assert case.source_text_sha256
    assert ARABIC_CASE in {c["case_id"] for c in golden_training_export(seeded)}

    events = seeded.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "GOLDEN_CASE_TEXT_CONFIRMED")
    ).scalars().all()
    assert any((e.event_metadata or {}).get("case_id") == ARABIC_CASE for e in events)


def test_ocr_can_never_supply_source_text(seeded):
    with pytest.raises(ValueError):
        confirm_customer_source_text(seeded, ARABIC_CASE, "مي", authority="OCR")


def test_stage_comparison_is_labelled_as_visual_not_computed(seeded):
    necklace = _case(seeded, NECKLACE_CASE)
    comparison = necklace.stage_comparison
    assert comparison["computed_from_vector_geometry"] is False
    assert comparison["measurement_method"] == "VISUAL_REVIEW_NO_VECTOR_GEOMETRY"
    assert comparison["dimensions"]["letter_order_accuracy"]["score"] == 1.0
    assert necklace.design_fidelity_score == comparison["aggregate_score"]

    # Unassessable dimensions stay unassessed instead of being invented.
    arabic = _case(seeded, ARABIC_CASE)
    assert "letter_identity" in arabic.stage_comparison["not_assessed"]
    assert arabic.stage_comparison["dimensions"]["letter_identity"]["score"] is None


def test_aggregate_ignores_unassessed_dimensions():
    result = compare_case_stages(
        {
            "stages": ["a", "b"],
            "dimensions": {
                "x": {"score": 1.0},
                "y": {"score": 0.5},
                "z": {"score": None, "status": "NOT_ASSESSED"},
            },
        }
    )
    assert result["aggregate_score"] == 0.75
    assert result["not_assessed"] == ["z"]
    assert result["assessed_count"] == 2


def test_case2_records_the_real_customer_selection_lifecycle(seeded):
    """The customer chose an existing Beyond Style design, we drew on it by
    hand, proposed two writing styles, and she picked one. That sequence is
    the reusable part — it must be stored as it happened."""
    case = _case(seeded, NECKLACE_CASE)
    roles = [e["role"] for e in case.evidence]
    # The starting point was the CUSTOMER's pick from our own catalogue,
    # not an external style reference we sourced.
    assert "customer_selection" in roles
    assert "shop_annotation" in roles
    assert "style_reference" not in roles
    assert roles.count("writing_variant_proposal") == 2

    actors = [step["actor"] for step in case.design_process]
    assert actors[0] == "customer"          # selection starts with the customer
    assert "beyond_style" in actors and "workshop" in actors
    assert [s["step"] for s in case.design_process] == list(range(1, len(case.design_process) + 1))

    selection = case.variant_selection
    assert selection["options_presented"] == 2
    assert selection["selection_method"] == "CUSTOMER_CHOSE_FROM_TWO_PROPOSALS"
    assert {o["variant"] for o in selection["options"]} == {
        "ROTATED_LETTERS", "UPRIGHT_STACKED_LETTERS"
    }
    # Which of the two she picked was never stated, so it is flagged as read
    # off the finished piece rather than asserted as a record.
    assert selection["selection_status"] == "OBSERVED_FROM_FINAL_PRODUCT_NOT_OWNER_CONFIRMED"


def test_case1_records_its_own_selection_lifecycle(seeded):
    case = _case(seeded, ARABIC_CASE)
    assert case.design_process[0]["actor"] == "customer"
    assert case.variant_selection["selection_method"] == "HAND_MARKED_ON_CONCEPT_SHEET"


def test_proven_process_transfers_but_geometry_still_does_not(seeded):
    hints = golden_case_generation_hints(_case(seeded, NECKLACE_CASE))
    assert hints["proven_process"], "a proven process is reusable memory"
    assert hints["proven_process"][0]["actor"] == "customer"
    assert not (GEOMETRY_KEYS & set(hints))


# --- owner sample batches (2026-09-10) ----------------------------------------

def test_owner_samples_never_carry_customer_text_and_stay_pending(seeded):
    """Text read off a photo is never source text: every owner sample seeds
    with no customer_source_text and sits in the PENDING tier until the
    customer confirms the exact text on the platform."""
    rows = seeded.execute(select(m.GoldenProductionCase)).scalars().all()
    owner = [r for r in rows if r.evidence_tier in ("MANUFACTURED_OWNER_SAMPLE", "MARKETING_RENDER_UNMANUFACTURED", "EXTERNAL_INSPIRATION")]
    assert len(owner) == 36
    for r in owner:
        assert r.customer_source_text is None
        assert r.source_text_status == "PENDING_CUSTOMER_VERIFICATION"
        assert r.memory_tier == "GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION"
        assert r.customer_approved is False


def test_owner_sample_tiers_rank_between_customer_approved_and_ai():
    w = EVIDENCE_TIER_WEIGHTS
    assert w["MANUFACTURED_CUSTOMER_APPROVED"] > w["MANUFACTURED_OWNER_SAMPLE"] > w["DESIGNER_APPROVED"]
    assert w["AI_GENERATED_UNMANUFACTURED"] > w["MARKETING_RENDER_UNMANUFACTURED"] > w["EXTERNAL_INSPIRATION"]


def test_third_party_and_personal_evidence_is_hash_only(seeded):
    """Children's photos, on-body photos and third-party brand photos are
    registered by sha256 only — never stored, never exported."""
    from app.data.golden_production_cases import GOLDEN_PRODUCTION_CASES
    excluded = [e for c in GOLDEN_PRODUCTION_CASES for e in c["evidence"] if e["storage_status"].startswith("EXCLUDED_")]
    assert len(excluded) >= 20
    assert all(e["storage_key"] is None and len(e["sha256"]) == 64 for e in excluded)
    exported_shas = {e["sha256"] for c in golden_training_export(seeded) for e in c["evidence"]}
    assert not exported_shas & {e["sha256"] for e in excluded}


def test_third_party_references_never_reach_training_export(seeded):
    from app.data.golden_production_cases import GOLDEN_PRODUCTION_CASES
    third_party = {c["case_id"] for c in GOLDEN_PRODUCTION_CASES if c["rights_provenance"] not in ("BEYOND_STYLE_OWNED", "CUSTOMER_OWNED", "LICENSED")}
    assert third_party, "the kids/cufflink/size-guide market references must be registered as third-party"
    assert not third_party & {c["case_id"] for c in golden_training_export(seeded)}


def test_owner_samples_are_retrievable_for_new_product_families(seeded):
    hits = retrieve_golden_cases(seeded, {"product_type": "keychain", "keywords": ["keychain", "engraved disc"]}, top_k=3)
    assert hits and hits[0]["case_id"].startswith("BS-GPC-0011")
    hits = retrieve_golden_cases(seeded, {"product_type": "brooch", "keywords": ["hijab pin", "name brooch"]}, top_k=3)
    assert any(h["case_id"].startswith("BS-GPC-0015") for h in hits)
