"""Upload security: MIME whitelist, magic-byte verification, size limits,
metadata stripping, private storage abstraction, malware-scan adapter.

Uploads are PRIVATE by default: stored under non-guessable keys in a
non-public directory (S3-compatible interface for later), served only via
the owner-authenticated API endpoint. Never used for model training.
"""
from __future__ import annotations

import hashlib
import io
import os
import secrets
from pathlib import Path
from typing import Protocol

from PIL import Image

# Configurable limits (development defaults).
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 8 * 1024 * 1024))

#: verified media types we accept for reference images. SVG deliberately
#: excluded from customer uploads in this slice (no sanitizer needed yet).
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

_MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


class UploadRejected(Exception):
    pass


def sniff_media_type(data: bytes) -> str | None:
    """Magic-byte detection — client-declared Content-Type is never trusted."""
    for magic, mtype in _MAGIC:
        if data.startswith(magic):
            return mtype
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_and_strip(data: bytes, declared_type: str | None) -> tuple[bytes, str, dict]:
    """Validate size + magic bytes + decodability; re-encode to strip
    EXIF/metadata. Returns (clean_bytes, verified_media_type, safe_analysis).
    """
    if not data:
        raise UploadRejected("Empty upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024*1024)}MB.")
    sniffed = sniff_media_type(data)
    if sniffed is None or sniffed not in ALLOWED_IMAGE_TYPES:
        raise UploadRejected("Unsupported file type. Allowed: JPEG, PNG, WebP.")
    if declared_type and declared_type.split(";")[0].strip() not in ALLOWED_IMAGE_TYPES:
        raise UploadRejected("Declared content type not allowed.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise UploadRejected("File is not a valid image.") from exc

    # Re-encode without metadata (EXIF/GPS stripped by not copying info).
    out = io.BytesIO()
    fmt = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[sniffed]
    clean = Image.new(img.mode if img.mode in ("RGB", "RGBA", "L") else "RGB", img.size)
    clean.paste(img.convert(clean.mode))
    save_kwargs = {"quality": 90} if fmt in ("JPEG", "WEBP") else {}
    clean.save(out, format=fmt, **save_kwargs)

    # Safe DESIGN metadata only — never OCR text (OCR is not text truth).
    w, h = img.size
    analysis = {
        "width_px": w,
        "height_px": h,
        "aspect_ratio": round(w / h, 3) if h else None,
        "orientation": "horizontal" if w > h * 1.15 else ("vertical" if h > w * 1.15 else "square"),
        "analysis_source": "deterministic_image_metadata",
        "detected_text": None,  # intentionally never populated automatically
    }
    return out.getvalue(), sniffed, analysis


class PrivateStorage(Protocol):
    def put(self, data: bytes, suffix: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalPrivateStorage:
    """Filesystem-backed private store (S3-compatible interface shape).
    Keys are non-guessable; the directory is never served statically."""

    def __init__(self, root: Path | None = None):
        self.root = root or Path(
            os.environ.get("PRIVATE_STORAGE_DIR", Path(__file__).resolve().parents[2] / "var" / "private_uploads")
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str) -> str:
        key = f"{secrets.token_hex(24)}{suffix}"
        (self.root / key).write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise PermissionError("Invalid storage key.")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if str(path).startswith(str(self.root.resolve())) and path.exists():
            path.unlink()


class S3PrivateStorage:
    """S3-compatible private object storage (AWS S3, Cloudflare R2, MinIO,
    any endpoint boto3 speaks). Objects are private; keys are random and
    non-guessable; nothing is ever served by URL — reads go through the
    owner-scoped API. Configure OBJECT_STORAGE=s3, S3_BUCKET, optional
    S3_ENDPOINT_URL / S3_REGION, and standard AWS credential env vars."""

    def __init__(self, bucket: str, client=None, prefix: str = "private/"):
        if client is None:
            import boto3  # pinned in requirements; imported lazily so local dev needs no creds

            client = boto3.client(
                "s3",
                endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
                region_name=os.environ.get("S3_REGION") or None,
            )
        self.bucket, self.client, self.prefix = bucket, client, prefix

    def put(self, data: bytes, suffix: str) -> str:
        key = f"{self.prefix}{secrets.token_hex(24)}{suffix}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ACL="private")
        return key

    def get(self, key: str) -> bytes:
        if not key.startswith(self.prefix) or ".." in key:
            raise PermissionError("Invalid storage key.")
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        if key.startswith(self.prefix):
            self.client.delete_object(Bucket=self.bucket, Key=key)


_storage: PrivateStorage | None = None


def get_storage() -> PrivateStorage:
    """OBJECT_STORAGE=s3 selects S3PrivateStorage (production); the default
    stays the local private directory (dev/CI)."""
    global _storage
    if _storage is None:
        if os.environ.get("OBJECT_STORAGE", "local").lower() == "s3":
            bucket = os.environ.get("S3_BUCKET")
            if not bucket:
                raise RuntimeError("OBJECT_STORAGE=s3 requires S3_BUCKET.")
            _storage = S3PrivateStorage(bucket)
        else:
            _storage = LocalPrivateStorage()
    return _storage


class MalwareScanner(Protocol):
    def scan(self, data: bytes) -> str: ...


class NoScannerAvailable:
    """Honest adapter: no scanning provider configured in this environment.
    Files stay PENDING_SCAN — we never fake a 'scanned clean' status."""

    def scan(self, data: bytes) -> str:  # noqa: ARG002
        return "PENDING_SCAN"


class ClamdScanner:
    """ClamAV daemon over TCP (INSTREAM protocol). Configure CLAMD_HOST /
    CLAMD_PORT. Results: CLEAN, INFECTED:<signature>, SCAN_ERROR — never a
    guessed status: if the daemon cannot be reached the file is NOT
    reported clean."""

    def __init__(self, host: str, port: int, timeout: float = 20.0):
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, data: bytes) -> str:
        import socket
        import struct

        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(b"zINSTREAM\0")
                view = memoryview(data)
                chunk = 64 * 1024
                for i in range(0, len(view), chunk):
                    part = view[i:i + chunk]
                    sock.sendall(struct.pack("!I", len(part)) + part.tobytes())
                sock.sendall(struct.pack("!I", 0))
                reply = b""
                while not reply.endswith(b"\0") and len(reply) < 4096:
                    got = sock.recv(1024)
                    if not got:
                        break
                    reply += got
        except OSError:
            return "SCAN_ERROR"
        text = reply.decode("utf-8", errors="replace").strip("\0\n ")
        if text.endswith("OK"):
            return "CLEAN"
        if "FOUND" in text:
            sig = text.split(":", 1)[-1].replace("FOUND", "").strip()
            return f"INFECTED:{sig or 'unknown'}"
        return "SCAN_ERROR"


#: Production must set this true once a scanner is deployed: an upload
#: that is not positively CLEAN is then refused instead of stored PENDING.
REQUIRE_MALWARE_SCAN = os.environ.get("REQUIRE_MALWARE_SCAN", "false").lower() == "true"


def get_scanner() -> MalwareScanner:
    host = os.environ.get("CLAMD_HOST")
    if host:
        return ClamdScanner(host, int(os.environ.get("CLAMD_PORT", "3310")))
    return NoScannerAvailable()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
