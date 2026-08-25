"""IMMUTABLE Golden Path acceptance fixture — the exact 7-name family
scenario, oldest to youngest:

    حامد محمد سلطان ميثة حمد خالد مهرة

This is the canonical production acceptance case (also used by
scripts/production-smoke.py's GOLDEN_SEVEN_NAMES). DO NOT edit the
names, their order, or the codepoint fingerprint below without an
explicit, reviewed decision — that is the entire point of this file:
any accidental substitution, omission, duplication, invention, or
reordering of a name must fail loudly, in CI, before it ever reaches a
customer.
"""
from __future__ import annotations

import unicodedata

import pytest

from app.engines.arabic_engine import paragraph_direction, shape_text, verify_identity
from app.services import design_service as svc

# ---------------------------------------------------------------- fixture

GOLDEN_SEVEN_NAMES = ("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة")
GOLDEN_TEXT = " ".join(GOLDEN_SEVEN_NAMES)

#: Exact codepoint fingerprint per name — catches a visually-similar but
#: wrong character (e.g. a look-alike letter) that a string diff might miss.
GOLDEN_CODEPOINTS = (
    (0x062D, 0x0627, 0x0645, 0x062F),          # حامد
    (0x0645, 0x062D, 0x0645, 0x062F),          # محمد
    (0x0633, 0x0644, 0x0637, 0x0627, 0x0646),  # سلطان
    (0x0645, 0x064A, 0x062B, 0x0629),          # ميثة
    (0x062D, 0x0645, 0x062F),                  # حمد
    (0x062E, 0x0627, 0x0644, 0x062F),          # خالد
    (0x0645, 0x0647, 0x0631, 0x0629),          # مهرة
)

FORBIDDEN_NAME = "فاطمة"  # explicitly NOT part of this fixture — a prior
# slice's smoke-test text wrongly included this name; this test exists
# specifically to prevent that regression from recurring silently.


# ------------------------------------------------------------ fixture proof


def test_exactly_seven_names_in_exact_unicode_and_order():
    assert len(GOLDEN_SEVEN_NAMES) == 7
    for name, codepoints in zip(GOLDEN_SEVEN_NAMES, GOLDEN_CODEPOINTS):
        assert tuple(ord(c) for c in name) == codepoints, name
    # Order is part of the contract — not just membership.
    assert GOLDEN_SEVEN_NAMES == ("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة")
    assert GOLDEN_TEXT == "حامد محمد سلطان ميثة حمد خالد مهرة"


def test_no_omitted_substituted_duplicated_or_invented_name():
    words = GOLDEN_TEXT.split(" ")
    assert len(words) == 7  # not omitted, not merged
    assert len(set(words)) == 7  # not duplicated (each name distinct)
    assert FORBIDDEN_NAME not in words  # not substituted with a different name
    for w in words:
        assert w in GOLDEN_SEVEN_NAMES  # not invented — every word is one of the 7


def test_nfc_normalization_is_a_no_op_on_this_fixture():
    """The fixture is already NFC-normalized — confirms confirm_request_text's
    byte-exact NFC comparison will match it without silent transformation."""
    assert unicodedata.normalize("NFC", GOLDEN_TEXT) == GOLDEN_TEXT


def test_rtl_preserved():
    assert paragraph_direction(GOLDEN_TEXT) == "rtl"
    for name in GOLDEN_SEVEN_NAMES:
        assert paragraph_direction(name) == "rtl"


def test_arabic_identity_verifies_and_covers_every_name():
    runs = shape_text(GOLDEN_TEXT, "amiri-regular")
    proof = verify_identity(GOLDEN_TEXT, runs)
    assert proof.verified is True
    assert proof.notdef_glyph_count == 0
    assert proof.uncovered_codepoint_indices == []
    assert len(proof.covered_codepoint_indices) == len(GOLDEN_TEXT)


# --------------------------------------------------------- end-to-end request


def test_generated_design_request_contains_all_seven_names_in_order(clean_tables, db_session):
    req = svc.create_request(db_session, GOLDEN_TEXT, "pendant")
    db_session.commit()
    db_session.refresh(req)
    assert req.source_text_normalized == GOLDEN_TEXT
    assert req.source_text_normalized.split(" ") == list(GOLDEN_SEVEN_NAMES)

    svc.confirm_request_text(db_session, req.id, GOLDEN_TEXT)
    result = svc.generate_and_persist_candidates(db_session, req.id)
    db_session.commit()

    assert len(result["top"]) == 10
    for candidate in result["top"]:
        assert candidate.identity_proof.verified is True
        assert candidate.source_text_sha256 == req.source_text_sha256


# ---------------------------------------------------- fail-closed on mutation


@pytest.mark.parametrize(
    "mutated_text,reason",
    [
        (" ".join(("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد")), "omitted last name (مهرة)"),
        (" ".join(("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة", "مهرة")), "duplicated last name"),
        (" ".join(("حامد", "محمد", "سلطان", FORBIDDEN_NAME, "حمد", "خالد", "مهرة")), "substituted ميثة with فاطمة"),
        (" ".join(("محمد", "حامد", "سلطان", "ميثة", "حمد", "خالد", "مهرة")), "reordered first two names"),
        (" ".join(("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة", "سالم")), "invented an 8th name"),
    ],
)
def test_arabic_validation_fails_closed_on_any_mutation(clean_tables, db_session, mutated_text, reason):
    """Confirming a mutated text against the ORIGINAL golden request must
    be rejected — proves the system fails closed, never silently accepts
    a changed name set."""
    req = svc.create_request(db_session, GOLDEN_TEXT, "pendant")
    db_session.commit()
    with pytest.raises(svc.ApprovalRejected):
        svc.confirm_request_text(db_session, req.id, mutated_text)
    db_session.rollback()
    db_session.refresh(req)
    assert req.status == "DRAFT"  # never silently advances past confirmation
    assert req.source_text_normalized == GOLDEN_TEXT  # original never mutated
