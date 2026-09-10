"""Shared infrastructure: one rate-limiter registry (memory | Redis, never
blocking on Redis) and the S3 object-storage path for customer images."""
from __future__ import annotations

import io

import pytest

from app.security import ratelimit as rl


@pytest.fixture(autouse=True)
def _clean():
    rl.reset_all()
    yield
    rl.reset_all()


class FakeRedis:
    """Minimal sorted-set subset used by RedisWindow (ZADD/ZREMRANGEBYSCORE/ZCARD/EXPIRE/pipeline)."""

    def __init__(self):
        self.z: dict[str, dict[str, float]] = {}
        self.fail = False

    def pipeline(self):
        return _Pipe(self)

    def keys(self, pattern):
        return list(self.z)

    def delete(self, k):
        self.z.pop(k, None)


class _Pipe:
    def __init__(self, r):
        self.r, self.ops = r, []

    def zremrangebyscore(self, k, lo, hi):
        self.ops.append(("zrem", k, lo, hi)); return self

    def zcard(self, k):
        self.ops.append(("zcard", k)); return self

    def zadd(self, k, mapping):
        self.ops.append(("zadd", k, mapping)); return self

    def expire(self, k, s):
        self.ops.append(("expire", k, s)); return self

    def execute(self):
        if self.r.fail:
            raise ConnectionError("redis down")
        out = []
        for op in self.ops:
            z = self.r.z.setdefault(op[1], {})
            if op[0] == "zrem":
                for m in [m for m, sc in z.items() if op[2] <= sc <= op[3]]:
                    del z[m]
                out.append(0)
            elif op[0] == "zcard":
                out.append(len(z))
            elif op[0] == "zadd":
                z.update(op[2]); out.append(1)
            else:
                out.append(True)
        return out


def test_registry_returns_one_limiter_per_name_and_memory_window_limits():
    a = rl.get_limiter("t", 2, 10.0)
    assert rl.get_limiter("t", 99, 1.0) is a          # same object, first config wins
    assert a.allow("k", now=0.0) and a.allow("k", now=1.0) and not a.allow("k", now=2.0)
    assert a.allow("k", now=11.5)                     # window slid
    assert a.allow("other", now=2.0)                  # keys are independent
    assert rl.status()["backend"] == "memory" and rl.status()["limiters"]["t"]["max_calls"] == 2


def test_redis_window_is_shared_and_degrades_to_memory_on_failure():
    fake = FakeRedis()
    rl.use_backend(rl.RedisWindow(fake))
    lim = rl.get_limiter("gen", 2, 60.0)
    other = rl.RateLimiter(2, 60.0, name="gen")       # a second process/worker with the same name
    assert lim.allow("ip1", now=100.0) and other.allow("ip1", now=101.0)
    assert not lim.allow("ip1", now=102.0), "the window is shared through Redis, not per process"
    assert "bs:rl:gen:ip1" in fake.z and rl.status()["shared_across_instances"] is True
    fake.fail = True
    assert lim.allow("ip2", now=103.0)                # Redis down → in-process window, request served
    assert lim.fallbacks == 1 and "redis down" in rl.status()["last_failure"]


def test_all_app_limiters_come_from_the_registry():
    import app.main  # noqa: F401 — wires the routers
    names = set(rl.status()["limiters"])
    assert {"upload", "generate", "approval_link", "vote"} <= names


def test_s3_private_storage_put_get_delete_through_boto_stubber(monkeypatch):
    import boto3
    from botocore.stub import ANY, Stubber

    from app.security.uploads import S3PrivateStorage

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    stub = Stubber(client)
    stub.add_response("put_object", {}, {"Bucket": "bs-private", "Key": ANY, "Body": b"jpegdata", "ACL": "private"})
    stub.add_response("get_object", {"Body": io.BytesIO(b"jpegdata")}, {"Bucket": "bs-private", "Key": ANY})
    stub.add_response("delete_object", {}, {"Bucket": "bs-private", "Key": ANY})
    stub.activate()
    st = S3PrivateStorage("bs-private", client=client)
    key = st.put(b"jpegdata", ".jpg")
    assert key.startswith("private/") and key.endswith(".jpg") and len(key) > 40
    assert st.get(key) == b"jpegdata"
    st.delete(key)
    stub.assert_no_pending_responses()
    with pytest.raises(PermissionError):
        st.get("../etc/passwd")


def test_get_storage_selects_s3_from_env_and_readiness_reports_backend(monkeypatch):
    from app.security import uploads
    from app import readiness

    monkeypatch.setattr(uploads, "_storage", None)
    monkeypatch.setenv("OBJECT_STORAGE", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError):
        uploads.get_storage()
    monkeypatch.setattr(uploads, "_storage", None)
    monkeypatch.setenv("OBJECT_STORAGE", "local")
    st = readiness.check_storage()
    assert st["status"] == "ok" and st["backend"] == "local" and st["durability"] == "PROCESS_LOCAL_DISK"
    lim = readiness.check_rate_limiter()
    assert lim["backend"] == "memory" and lim["shared_across_instances"] is False
    monkeypatch.setattr(uploads, "_storage", None)
