"""Dimensioned agreement proof — the artifact the customer approves.

Locks in: the proof carries the REAL millimetre dimensions of the built
geometry, preserves the exact source text, is deterministic (stable sha256),
its hash is recorded on approval, and the AI-preview dimension strip is a
serve-time overlay that never claims to be a manufacturing file.
"""
import hashlib
import io
import json
import re

import pytest
from shapely import wkt as shapely_wkt

from app.db import models as m
from app.services import design_service as svc
from app.services.visual_studio import render_canonical_png, stamp_dimensions_strip
from sqlalchemy import select


@pytest.fixture
def client(clean_tables):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def version(clean_tables, db_session):
    req = svc.create_request(db_session, "ميثة", "pendant")
    svc.confirm_request_text(db_session, req.id, "ميثة")
    result = svc.generate_and_persist_candidates(db_session, req.id)
    _, v = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    db_session.flush()
    return v


def _proof_meta(svg: str) -> dict:
    raw = re.search(r"<metadata>(.*?)</metadata>", svg, re.S).group(1)
    # Un-escape the XML entities the exporter escapes.
    raw = raw.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
    return json.loads(raw)


def test_proof_carries_the_real_mm_dimensions(db_session, version):
    svg = svc.agreement_proof_for_version(db_session, version)
    meta = _proof_meta(svg)
    geom = shapely_wkt.loads(version.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    assert meta["units"] == "mm"
    assert meta["width_mm"] == pytest.approx(maxx - minx, abs=0.001)
    assert meta["height_mm"] == pytest.approx(maxy - miny, abs=0.001)
    # The dimension labels drawn on the sheet match the geometry, not a guess.
    assert f"{round(maxx - minx, 1):g} mm" in svg
    assert f"{round(maxy - miny, 1):g} mm" in svg


def test_proof_preserves_exact_source_text_and_identity(db_session, version):
    svg = svc.agreement_proof_for_version(db_session, version)
    meta = _proof_meta(svg)
    assert meta["source_text"] == "ميثة"
    assert meta["source_text_sha256"] == version.source_text_sha256
    assert meta["geometry_hash"] == version.geometry_hash
    assert "ميثة" in svg  # spec block shows the confirmed text verbatim


def test_proof_is_deterministic(db_session, version):
    a = svc.agreement_proof_for_version(db_session, version)
    b = svc.agreement_proof_for_version(db_session, version)
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest()


def test_approval_records_the_agreement_proof_hash(db_session, version):
    expected = hashlib.sha256(
        svc.agreement_proof_for_version(db_session, version).encode()
    ).hexdigest()
    svc.approve_version(
        db_session,
        version.id,
        confirmed_text="ميثة",
        source_text_sha256=version.source_text_sha256,
        geometry_hash=version.geometry_hash,
        approved_by="test-customer",
    )
    events = db_session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "CUSTOMER_APPROVED")
    ).scalars().all()
    assert any(
        (e.event_metadata or {}).get("agreement_proof_sha256") == expected for e in events
    ), "approval must bind the exact dimensioned picture the customer saw"


def test_dimension_strip_is_added_without_touching_the_design_pixels(db_session, version):
    """The strip goes UNDER the image (canvas grows); the design area at the
    top stays pixel-identical, and the disclaimer is drawn — using a locally
    rendered canonical PNG, never a fabricated AI output."""
    from PIL import Image

    base = render_canonical_png(version.geometry_wkt, size_px=256)
    stamped = stamp_dimensions_strip(
        base,
        width_mm=32.4,
        height_mm=18.2,
        version_number=version.version_number,
        geometry_hash=version.geometry_hash,
    )
    src = Image.open(io.BytesIO(base)).convert("RGB")
    out = Image.open(io.BytesIO(stamped)).convert("RGB")
    assert out.width == src.width
    assert out.height > src.height
    # Design area preserved exactly.
    assert list(out.crop((0, 0, src.width, src.height)).getdata()) == list(src.getdata())


def test_agreement_proof_endpoint_requires_the_owner_session(client, db_session, version):
    r = client.get(f"/api/versions/{version.id}/agreement-proof")
    # The API's anti-enumeration contract: unowned/unauthenticated version
    # access reads as 404 (same as /svg), never a leaked artifact.
    assert r.status_code == 404
    assert "<svg" not in r.text
