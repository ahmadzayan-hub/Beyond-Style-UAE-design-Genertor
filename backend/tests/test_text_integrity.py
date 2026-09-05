"""Text Integrity Engine — CORRECT ARABIC FIRST.

The production acceptance names (owner spec, 2026-09-05). Note ميثه with
haa: it must NEVER become ميثة (taa marbuta); the two are a dot change and
hash differently."""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.engines import text_integrity as ti
from app.main import app
from app.services import design_service as svc

ACCEPTANCE_NAMES = ("حامد", "محمد", "سلطان", "ميثه", "حمد", "خالد", "مهرة")
ACCEPTANCE_TEXT = "\n".join(ACCEPTANCE_NAMES)


def test_acceptance_names_are_exactly_as_specified():
    assert ACCEPTANCE_NAMES[3] == "ميثه" and ACCEPTANCE_NAMES[3] != "ميثة"
    assert [ord(c) for c in "ميثه"] == [0x0645, 0x064A, 0x062B, 0x0647]
    assert ti.sha256("ميثه") != ti.sha256("ميثة")
    for name in ACCEPTANCE_NAMES:
        report = ti.inspect(name)
        assert report.status == "PASS" and report.normalized_text == name and not report.suggested_clean_text


def test_haa_vs_taa_marbuta_is_a_dot_change_and_fails():
    cmp = ti.compare("ميثه", "ميثة")
    assert cmp.status == "FAIL" and not cmp.identical
    assert cmp.entries[0].kind == "DOT_CHANGE" and cmp.entries[0].expected_index == 3
    assert "taa marbuta" in cmp.entries[0].detail
    assert ti.compare("ميثه", "ميثه").status == "PASS"


def test_compare_classifies_missing_reorder_hamza_and_diacritics():
    assert {e.kind for e in ti.compare("محمد", "محد").entries} == {"MISSING"}
    assert "REORDERED" in {e.kind for e in ti.compare("حمد", "دمح").entries}
    assert {e.kind for e in ti.compare("أحمد", "احمد").entries} == {"HAMZA_CHANGE"}
    assert {e.kind for e in ti.compare("مُحمد", "محمد").entries} == {"DIACRITIC_LOST"}
    assert {e.kind for e in ti.compare("علي", "على").entries} == {"DOT_CHANGE"}


def test_inspect_flags_hidden_characters_and_never_strips_them():
    raw = "مي‍ثه"  # a zero width joiner smuggled into the name
    report = ti.inspect(raw)
    assert report.status == "FAIL"
    assert report.issues[0].code == "INVISIBLE_CHARACTER" and report.issues[0].index == 2
    assert report.normalized_text == raw  # nothing removed
    assert report.suggested_clean_text == "ميثه"
    bidi = ti.inspect("‮ميثه")
    assert bidi.status == "FAIL" and "RLO" in bidi.issues[0].detail
    assert ti.inspect("ميـثه").issues[0].code == "TATWEEL_PRESENT"  # warning, still PASS
    assert ti.inspect("ميـثه").status == "PASS"


def test_certify_fails_when_carried_text_drifts():
    class Proof:
        verified = True
        uncovered_codepoint_indices = []
        notdef_glyph_count = 0

    ok = ti.certify("ميثه", ti.sha256("ميثه"), Proof(), [], carried_text="ميثه")
    assert ok["status"] == "PASS" and ok["label"] == "TEXT INTEGRITY: PASS"
    bad = ti.certify("ميثه", ti.sha256("ميثه"), Proof(), [], carried_text="ميثة")
    assert bad["status"] == "FAIL" and bad["checks"][0]["entries"][0]["kind"] == "DOT_CHANGE"
    wrong_hash = ti.certify("ميثه", ti.sha256("ميثة"), Proof(), [])
    assert wrong_hash["status"] == "FAIL"


def test_api_blocks_hidden_characters_with_plain_language(clean_tables):
    with TestClient(app) as c:
        r = c.post("/api/designs", json={"text": "مي​ثه", "product_type": "pendant"})
        assert r.status_code == 422
        body = r.json()["detail"]
        assert body["code"] == "TEXT_INTEGRITY_FAILED"
        assert body["integrity"]["suggested_clean_text"] == "ميثه"
        assert "Hidden character" in body["integrity"]["issues"][0]["detail"]
        r = c.post("/api/designs/integrity/inspect", json={"text": "ميثه"})
        assert r.status_code == 200 and r.json()["label"] == "TEXT INTEGRITY: PASS"
        assert [ch["char"] for ch in r.json()["characters"]] == list("ميثه")


def test_acceptance_names_survive_the_whole_pipeline(clean_tables, db_session):
    """Create → confirm → generate → select → version → SVG/DXF: the seven
    names are byte-identical everywhere and the version certifies PASS."""
    req = svc.create_request(db_session, ACCEPTANCE_TEXT, "pendant")
    assert req.source_text_normalized == ACCEPTANCE_TEXT
    svc.confirm_request_text(db_session, req.id, ACCEPTANCE_TEXT)
    with pytest.raises(svc.ApprovalRejected):
        svc.confirm_request_text(db_session, svc.create_request(db_session, ACCEPTANCE_TEXT, "pendant").id,
                                 ACCEPTANCE_TEXT.replace("ميثه", "ميثة"))
    # Single-name pipeline (the seven-name composition is the Vector
    # Composition Engine's acceptance case, tested there).
    one = svc.create_request(db_session, "ميثه", "pendant")
    svc.confirm_request_text(db_session, one.id, "ميثه")
    result = svc.generate_and_persist_candidates(db_session, one.id)
    assert result["top"]
    for c in result["top"]:
        assert c.source_text_sha256 == hashlib.sha256("ميثه".encode()).hexdigest()
    _, v = svc.select_candidate(db_session, one.id, result["top"][0].candidate_id)
    db_session.flush()
    assert v.immutable_source_text == "ميثه"
    candidate, source = svc._version_to_candidate(v)
    verdict = ti.certify(source.normalized_text, source.sha256, candidate.identity_proof, [],
                         carried_text=v.immutable_source_text)
    assert verdict["status"] == "PASS"
    from app.exporters.dxf_exporter import export_dxf
    from app.exporters.svg_exporter import export_svg

    svg = export_svg(candidate, source)
    assert "ميثه" in svg and "ميثة" not in svg
    assert source.sha256 in svg and source.sha256 in export_dxf(candidate, source)
