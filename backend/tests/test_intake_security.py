"""Reference intake, upload security, session isolation, rate limits."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.db import models as m
from app.main import app
from app.security.sessions import GENERATE_LIMITER, UPLOAD_LIMITER
from app.security.uploads import get_storage
from app.services.intake_service import classify_request


@pytest.fixture
def client(clean_tables):
    UPLOAD_LIMITER.reset()
    GENERATE_LIMITER.reset()
    with TestClient(app) as c:
        yield c
    UPLOAD_LIMITER.reset()
    GENERATE_LIMITER.reset()


def _new_session(client, text="ميثة"):
    r = client.post("/api/designs", json={"text": text})
    body = r.json()
    return body["design_id"], {"X-Session-Token": body["session_token"]}


def _jpeg_bytes(w=800, h=400, with_exif=False) -> bytes:
    img = Image.new("RGB", (w, h), (200, 180, 120))
    out = io.BytesIO()
    if with_exif:
        exif = Image.Exif()
        exif[0x010F] = "SecretCameraMake"  # Make tag
        img.save(out, format="JPEG", exif=exif)
    else:
        img.save(out, format="JPEG")
    return out.getvalue()


# ------------------------------------------------------------- reference


def test_valid_image_intake_persists_privately(client, db_session):
    design_id, h = _new_session(client)
    r = client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("ref.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"provenance": "CUSTOMER_OWNED"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["privacy_status"] == "PRIVATE"
    assert body["provenance"] == "CUSTOMER_OWNED"
    assert body["ip_risk"] == "CLEARED"
    assert body["scan_status"] == "PENDING_SCAN"  # honest: no scanner faked
    assert body["analysis"]["orientation"] == "horizontal"
    assert body["analysis"]["detected_text"] is None
    # Content only readable with the owning session token.
    rid = body["reference_id"]
    ok = client.get(f"/api/designs/{design_id}/references/{rid}/content", headers=h)
    assert ok.status_code == 200
    assert ok.headers["cache-control"] == "private, no-store"
    anon = client.get(f"/api/designs/{design_id}/references/{rid}/content")
    assert anon.status_code == 404


def test_exif_metadata_stripped(client, db_session):
    design_id, h = _new_session(client)
    r = client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("exif.jpg", _jpeg_bytes(with_exif=True), "image/jpeg")},
    )
    rid = r.json()["reference_id"]
    stored = client.get(f"/api/designs/{design_id}/references/{rid}/content", headers=h).content
    exif = Image.open(io.BytesIO(stored)).getexif()
    assert 0x010F not in exif, "EXIF metadata leaked into stored file"


def test_invalid_mime_rejected(client):
    design_id, h = _new_session(client)
    for payload, name, ctype in [
        (b"MZ\x90\x00fakeexe", "x.jpg", "image/jpeg"),  # wrong magic bytes
        (b"<svg onload=alert(1)></svg>", "x.svg", "image/svg+xml"),
        (b"%PDF-1.4 fake", "x.pdf", "application/pdf"),
    ]:
        r = client.post(
            f"/api/designs/{design_id}/references",
            headers=h,
            files={"file": (name, payload, ctype)},
        )
        assert r.status_code == 422, f"{name} accepted!"


def test_oversized_upload_rejected(client, monkeypatch):
    import app.security.uploads as up
    import app.api.intake as intake_api

    monkeypatch.setattr(up, "MAX_UPLOAD_BYTES", 10_000)
    monkeypatch.setattr(intake_api, "MAX_UPLOAD_BYTES", 10_000)
    design_id, h = _new_session(client)
    r = client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("big.jpg", _jpeg_bytes(3000, 3000), "image/jpeg")},
    )
    assert r.status_code in (413, 422)


def test_ocr_text_never_becomes_source_text(client, db_session):
    """Reference upload + brief must not change request source text; only
    explicit confirmation sets it."""
    design_id, h = _new_session(client, text="نورة")
    client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("ref.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    client.put(
        f"/api/designs/{design_id}/brief",
        headers=h,
        json={"customer_message": "نفس الشكل بس غير الكتابة إلى نورة"},
    )
    brief = client.get(f"/api/designs/{design_id}/brief", headers=h).json()
    assert brief["confirmed_text"] is None  # not confirmed yet — never auto-set
    assert "confirmed_text" in brief["missing_fields"]
    # generation refused pre-confirmation
    assert client.post(f"/api/designs/{design_id}/candidates", headers=h).status_code == 409
    # explicit confirmation is the only path to text truth
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "نورة"})
    brief = client.get(f"/api/designs/{design_id}/brief", headers=h).json()
    assert brief["confirmed_text"] == "نورة"


def test_reference_classification():
    assert classify_request("نفس الشكل بس غير الكتابة إلى نورة", True, True)[0] == "SAME_STRUCTURE_NEW_TEXT"
    assert classify_request("same style please change the name", True, True)[0] == "SAME_STRUCTURE_NEW_TEXT"
    assert classify_request("حوليها خاتم", True, True)[0] == "PRODUCT_CONVERSION"
    assert classify_request("تصميم مستوحى", True, True)[0] == "STYLE_INSPIRED_REDESIGN"
    assert classify_request(None, False, True)[0] == "TEXT_ONLY_DESIGN"
    assert classify_request(None, False, False)[0] == "NEEDS_CLARIFICATION"


def test_branded_reference_flagged_copy_risk(client):
    design_id, h = _new_session(client)
    r = client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("brand.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"customer_message": "نفس تصميم كارتير بالضبط", "provenance": "UNKNOWN"},
    )
    body = r.json()
    assert body["ip_risk"] == "POTENTIAL_COPY_RISK"
    assert body["copy_notice"] is not None  # inspired alternative, no exact copy


def test_reference_influences_generation_hints(client):
    design_id, h = _new_session(client, text="نورة")
    client.post(
        f"/api/designs/{design_id}/references",
        headers=h,
        files={"file": ("ref.jpg", _jpeg_bytes(400, 900), "image/jpeg")},  # vertical
    )
    brief = client.put(
        f"/api/designs/{design_id}/brief", headers=h,
        json={"customer_message": "نفس الشكل بس غير الكتابة", "product_type": "pendant"},
    ).json()
    assert brief["request_type"] == "SAME_STRUCTURE_NEW_TEXT"
    assert "plate_oval" in brief["generation_hints"]["preferred_compositions"]


def test_privacy_delete_purges_files(client, db_session):
    design_id, h = _new_session(client)
    r = client.post(
        f"/api/designs/{design_id}/references", headers=h,
        files={"file": ("ref.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    rid = r.json()["reference_id"]
    assert client.delete(f"/api/designs/{design_id}/references", headers=h).json()["deleted"] == 1
    assert client.get(
        f"/api/designs/{design_id}/references/{rid}/content", headers=h
    ).status_code == 404
    asset = db_session.execute(select(m.ReferenceAsset)).scalars().one()
    assert asset.deleted and asset.privacy_status == "DELETED"
    with pytest.raises(FileNotFoundError):
        get_storage().get(asset.storage_key)


# ------------------------------------------------------- session security


def test_session_isolation(client):
    a_id, a_h = _new_session(client, "ميثة")
    b_id, b_h = _new_session(client, "مريم")
    # B cannot read A's design, brief, candidates or events.
    assert client.get(f"/api/designs/{a_id}", headers=b_h).status_code == 404
    assert client.get(f"/api/designs/{a_id}").status_code == 404  # no token
    assert client.post(
        f"/api/designs/{a_id}/confirm", headers=b_h, json={"confirmed_text": "ميثة"}
    ).status_code == 404
    # A works with its own token.
    assert client.get(f"/api/designs/{a_id}", headers=a_h).status_code == 200


def test_version_endpoints_are_session_scoped(client):
    design_id, h = _new_session(client)
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "ميثة"})
    top = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()["top"]
    sel = client.post(
        f"/api/designs/{design_id}/select", headers=h,
        json={"candidate_id": top[0]["candidate_id"]},
    ).json()
    vid = sel["version_id"]
    _, other_h = _new_session(client, "غريب")
    assert client.get(f"/api/versions/{vid}", headers=other_h).status_code == 404
    assert client.get(f"/api/versions/{vid}/svg", headers=other_h).status_code == 404
    assert client.get(f"/api/versions/{vid}", headers=h).status_code == 200


def test_upload_rate_limit(client, monkeypatch):
    from app.security.sessions import RateLimiter
    import app.api.intake as intake_api

    monkeypatch.setattr(intake_api, "UPLOAD_LIMITER", RateLimiter(2, 60))
    design_id, h = _new_session(client)
    img = _jpeg_bytes(200, 200)
    codes = [
        client.post(
            f"/api/designs/{design_id}/references", headers=h,
            files={"file": ("r.jpg", img, "image/jpeg")},
        ).status_code
        for _ in range(3)
    ]
    assert codes == [201, 201, 429]


def test_generation_rate_limit(client, monkeypatch):
    from app.security.sessions import RateLimiter
    import app.api.designs as designs_api

    monkeypatch.setattr(designs_api, "GENERATE_LIMITER", RateLimiter(1, 60))
    design_id, h = _new_session(client)
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "ميثة"})
    assert client.post(f"/api/designs/{design_id}/candidates", headers=h).status_code == 200
    assert client.post(f"/api/designs/{design_id}/candidates", headers=h).status_code == 429


# ------------------------------------------------------------ repair UX


def test_repair_creates_new_version_never_mutates(client):
    design_id, h = _new_session(client)
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "ميثة"})
    top = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()["top"]
    sel = client.post(
        f"/api/designs/{design_id}/select", headers=h,
        json={"candidate_id": top[0]["candidate_id"]},
    ).json()
    vid = sel["version_id"]
    opts = client.get(f"/api/versions/{vid}/repair-options", headers=h).json()["options"]
    assert opts and opts[0]["repair_id"] == "thicken_strokes"
    rep = client.post(f"/api/versions/{vid}/repair", headers=h, json={}).json()
    assert rep["version_number"] == 2 and rep["status"] == "UNAPPROVED"
    assert rep["parent_version_id"] == vid
    # Before/after previews render for both versions.
    assert client.get(rep["before_svg_url"], headers=h).status_code == 200
    assert client.get(rep["after_svg_url"], headers=h).status_code == 200
    # Parent unchanged.
    v1 = client.get(f"/api/versions/{vid}", headers=h).json()
    assert v1["version_number"] == 1 and v1["status"] == "UNAPPROVED"
