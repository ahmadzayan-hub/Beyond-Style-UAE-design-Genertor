"""Customer identity primitives: contact normalisation + hashing, one-time
login codes, and the code delivery adapter.

Delivery is an adapter: with no provider configured the code is NOT sent
and the API says so (`SKIPPED_EXTERNAL_PROVIDER`) — never a fake "sent".
For local development, CI and browser E2E, `AUTH_DEV_ECHO_CODE=1` returns
the code in the API response; that flag must never be set in production
(readiness reports it).
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_TTL_MINUTES = 10
CODE_MAX_ATTEMPTS = 5
CUSTOMER_SESSION_DAYS = 30


class ContactInvalid(ValueError):
    pass


def normalize_contact(raw: str) -> tuple[str, str]:
    """→ (kind, normalized). Email: lower-cased. Phone: E.164-style digits
    with a leading '+', UAE default (+971) for local 05x numbers."""
    v = (raw or "").strip()
    if not v:
        raise ContactInvalid("Contact is required.")
    if "@" in v:
        if not EMAIL_RE.match(v):
            raise ContactInvalid("Enter a valid email address.")
        return "email", v.lower()
    digits = re.sub(r"[^\d+]", "", v)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("05") and len(digits) == 10:
        digits = "+971" + digits[1:]
    if not digits.startswith("+"):
        digits = "+" + digits
    if not re.fullmatch(r"\+\d{8,15}", digits):
        raise ContactInvalid("Enter a valid phone number with country code (e.g. +9715xxxxxxxx).")
    return "phone", digits


def contact_hash(normalized: str) -> str:
    pepper = os.environ.get("CONTACT_HASH_PEPPER", "beyondstyle-dev-pepper")
    return hashlib.sha256(f"{pepper}|{normalized}".encode("utf-8")).hexdigest()


def mask_contact(kind: str, normalized: str) -> str:
    if kind == "email":
        local, _, domain = normalized.partition("@")
        return f"{local[:2]}***@{domain}"
    return f"{normalized[:4]}***{normalized[-3:]}"


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(customer_id: str, code: str) -> str:
    return hashlib.sha256(f"{customer_id}|{code}".encode("utf-8")).hexdigest()


def deliver_code(kind: str, normalized: str, code: str) -> dict:
    """Send the code through the configured provider. Honest statuses:
    SENT | SKIPPED_EXTERNAL_PROVIDER | FAILED. No provider is wired in this
    repository yet (SMS/e-mail vendor keys are an ops decision); the adapter
    seam is here so wiring one does not touch the login flow."""
    provider = os.environ.get("AUTH_CODE_PROVIDER", "").strip().lower()
    if not provider:
        return {"status": "SKIPPED_EXTERNAL_PROVIDER", "provider": None,
                "detail": "No SMS/e-mail provider configured (AUTH_CODE_PROVIDER)."}
    return {"status": "FAILED", "provider": provider, "detail": f"Provider '{provider}' is not implemented."}


def dev_echo_enabled() -> bool:
    return os.environ.get("AUTH_DEV_ECHO_CODE", "").strip() in ("1", "true", "yes")
