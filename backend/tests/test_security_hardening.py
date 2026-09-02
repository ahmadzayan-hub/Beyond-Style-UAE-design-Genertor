"""Security hardening slice: headers, malware scan gating, S3 adapter, roles."""
import socket
import struct
import threading

import pytest
from fastapi.testclient import TestClient

from app.security import uploads as up


@pytest.fixture
def client(clean_tables):
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_every_response_carries_security_headers(client):
    r = client.get("/health")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert "strict-transport-security" not in h  # SECURE_HSTS unset in tests


def _fake_clamd(reply: bytes):
    """Minimal clamd double speaking INSTREAM with a buffered reader (so a
    command and the first chunk header arriving together are parsed
    correctly)."""
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
        conn, _ = srv.accept()
        conn.settimeout(10)
        f = conn.makefile("rb")
        cmd = b""
        while not cmd.endswith(b"\0"):
            b = f.read(1)
            if not b:
                break
            cmd += b
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                break
            (n,) = struct.unpack("!I", hdr)
            if n == 0:
                break
            f.read(n)
        conn.sendall(reply); conn.close(); srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return port


def test_clamd_adapter_speaks_the_real_instream_protocol():
    port = _fake_clamd(b"stream: OK\0")
    assert up.ClamdScanner("127.0.0.1", port).scan(b"x" * 200_000) == "CLEAN"
    port = _fake_clamd(b"stream: Eicar-Test-Signature FOUND\0")
    assert up.ClamdScanner("127.0.0.1", port).scan(b"eicar").startswith("INFECTED:Eicar")


def test_unreachable_scanner_is_never_reported_clean():
    assert up.ClamdScanner("127.0.0.1", 1, timeout=0.5).scan(b"x") == "SCAN_ERROR"


def test_infected_upload_is_rejected_and_never_stored(clean_tables, db_session, monkeypatch):
    import io

    from PIL import Image

    from app.services import design_service as svc, intake_service as intake

    class Infected:
        def scan(self, data):
            return "INFECTED:Test"

    monkeypatch.setattr(intake, "get_scanner", lambda: Infected())
    buf = io.BytesIO(); Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="JPEG")
    req = svc.create_request(db_session, "ميثة", "pendant")
    with pytest.raises(up.UploadRejected):
        intake.add_reference(db_session, req.id, buf.getvalue(), "x.jpg", "image/jpeg")


def test_require_scan_policy_refuses_unscanned_uploads(clean_tables, db_session, monkeypatch):
    import io

    from PIL import Image

    from app.services import design_service as svc, intake_service as intake

    monkeypatch.setattr(intake, "REQUIRE_MALWARE_SCAN", True)  # scanner absent → PENDING_SCAN
    buf = io.BytesIO(); Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="JPEG")
    req = svc.create_request(db_session, "ميثة", "pendant")
    with pytest.raises(up.UploadRejected):
        intake.add_reference(db_session, req.id, buf.getvalue(), "x.jpg", "image/jpeg")


class _FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ACL):
        assert ACL == "private"
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        import io

        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_s3_storage_round_trip_with_private_random_keys():
    store = up.S3PrivateStorage("bucket", client=_FakeS3())
    key = store.put(b"hello", ".png")
    assert key.startswith("private/") and key.endswith(".png") and len(key) > 50
    assert store.get(key) == b"hello"
    with pytest.raises(PermissionError):
        store.get("../etc/passwd")
    store.delete(key)
    assert (("bucket", key) not in store.client.objects)


def test_reviewer_token_is_scoped_to_review_routes(client, monkeypatch):
    from app.api import admin

    monkeypatch.setattr(admin, "ADMIN_API_TOKEN", "admin-secret")
    monkeypatch.setattr(admin, "REVIEWER_API_TOKEN", "reviewer-secret")
    rev = {"X-Admin-Token": "reviewer-secret"}
    assert client.get("/api/admin/review/pack", headers=rev).status_code == 200
    assert client.get("/api/admin/golden-cases", headers=rev).status_code == 403
    assert client.get("/api/admin/golden-cases", headers={"X-Admin-Token": "admin-secret"}).status_code == 200
    assert client.get("/api/admin/review/pack").status_code == 403
