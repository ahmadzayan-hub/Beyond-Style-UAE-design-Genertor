"""Customer identity primitives: contact normalisation + hashing, one-time
login codes, and the code delivery adapter.

Delivery is an adapter: with no provider configured the code is NOT sent
and the API says so (`SKIPPED_EXTERNAL_PROVIDER`) — never a fake "sent".
For local development, CI and browser E2E, `AUTH_DEV_ECHO_CODE=1` returns
the code in the API response. With `APP_ENV=production` that flag is
ignored (fail closed) and a missing or default contact pepper refuses
login rather than hashing contacts with a public value.

Providers (`AUTH_CODE_PROVIDER`):
- `whatsapp_cloud`: Meta WhatsApp Cloud API, an approved *authentication*
  template with a copy-code button. Phone contacts only.
- `smtp`: e-mail through an SMTP relay with STARTTLS. E-mail contacts only.
The code is never logged and never placed in an error detail.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import ssl

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


DEV_PEPPER = "beyondstyle-dev-pepper"


class IdentityNotConfigured(RuntimeError):
    """Production is missing a setting customer identity cannot run safely without."""


def is_production() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() == "production"


def contact_pepper() -> str:
    pepper = os.environ.get("CONTACT_HASH_PEPPER", "").strip()
    if pepper and pepper != DEV_PEPPER:
        return pepper
    if is_production():
        # The default is in this public source, so a hash made with it can be reversed by
        # enumerating phone numbers. Refuse instead of storing such hashes.
        raise IdentityNotConfigured("CONTACT_HASH_PEPPER must be set to a private value in production.")
    return DEV_PEPPER


def contact_hash(normalized: str) -> str:
    pepper = contact_pepper()
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


def _whatsapp_cloud(kind: str, normalized: str, code: str, transport) -> dict:
    if kind != "phone":
        return {"status": "FAILED", "provider": "whatsapp_cloud", "detail": "WhatsApp delivers to phone numbers only."}
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    template = os.environ.get("WHATSAPP_AUTH_TEMPLATE", "").strip()
    if not (token and phone_id and template):
        return {"status": "FAILED", "provider": "whatsapp_cloud",
                "detail": "WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_AUTH_TEMPLATE are required."}
    version = os.environ.get("WHATSAPP_API_VERSION", "v21.0").strip()
    language = os.environ.get("WHATSAPP_AUTH_TEMPLATE_LANG", "en").strip()
    body = {
        "messaging_product": "whatsapp",
        "to": normalized.lstrip("+"),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": code}]},
                {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
            ],
        },
    }
    try:
        response = transport.post(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
    except Exception as exc:  # noqa: BLE001 - any transport failure is an honest FAILED
        return {"status": "FAILED", "provider": "whatsapp_cloud", "detail": f"Transport error: {type(exc).__name__}"}
    if response.status_code >= 300:
        return {"status": "FAILED", "provider": "whatsapp_cloud", "detail": f"Provider answered HTTP {response.status_code}."}
    try:
        message_id = (response.json().get("messages") or [{}])[0].get("id")
    except Exception:  # noqa: BLE001
        message_id = None
    if not message_id:
        return {"status": "FAILED", "provider": "whatsapp_cloud", "detail": "Provider did not return a message id."}
    return {"status": "SENT", "provider": "whatsapp_cloud", "provider_message_id": message_id}


def _smtp(kind: str, normalized: str, code: str, smtp_factory) -> dict:
    from email.message import EmailMessage

    if kind != "email":
        return {"status": "FAILED", "provider": "smtp", "detail": "SMTP delivers to e-mail addresses only."}
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    if not (host and sender):
        return {"status": "FAILED", "provider": "smtp", "detail": "SMTP_HOST and SMTP_FROM are required."}
    message = EmailMessage()
    message["From"] = sender
    message["To"] = normalized
    message["Subject"] = "Beyond Style login code | رمز الدخول"
    message.set_content(
        f"Your Beyond Style login code is {code}. It expires in {CODE_TTL_MINUTES} minutes.\n"
        f"رمز الدخول إلى Beyond Style هو {code}. ينتهي خلال {CODE_TTL_MINUTES} دقائق.\n"
    )
    try:
        with smtp_factory(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as client:
            # Authenticate the relay before sending credentials or the one-time code.
            client.starttls(context=ssl.create_default_context())
            user = os.environ.get("SMTP_USER", "").strip()
            if user:
                client.login(user, os.environ.get("SMTP_PASSWORD", ""))
            refused = client.send_message(message)
            if refused:
                return {"status": "FAILED", "provider": "smtp", "detail": "SMTP relay refused the recipient."}
    except Exception as exc:  # noqa: BLE001
        return {"status": "FAILED", "provider": "smtp", "detail": f"Transport error: {type(exc).__name__}"}
    return {"status": "SENT", "provider": "smtp"}


def deliver_code(kind: str, normalized: str, code: str, *, transport=None, smtp_factory=None) -> dict:
    """Send the code through the configured provider. Honest statuses:
    SENT | SKIPPED_EXTERNAL_PROVIDER | FAILED. SENT means the provider
    accepted the message, not that the customer read it."""
    provider = os.environ.get("AUTH_CODE_PROVIDER", "").strip().lower()
    if not provider:
        return {"status": "SKIPPED_EXTERNAL_PROVIDER", "provider": None,
                "detail": "No SMS/e-mail provider configured (AUTH_CODE_PROVIDER)."}
    if provider == "whatsapp_cloud":
        if transport is None:
            import httpx as transport
        return _whatsapp_cloud(kind, normalized, code, transport)
    if provider == "smtp":
        if smtp_factory is None:
            from smtplib import SMTP as smtp_factory
        return _smtp(kind, normalized, code, smtp_factory)
    return {"status": "FAILED", "provider": provider, "detail": f"Provider '{provider}' is not implemented."}


def dev_echo_requested() -> bool:
    return os.environ.get("AUTH_DEV_ECHO_CODE", "").strip() in ("1", "true", "yes")


def dev_echo_enabled() -> bool:
    """Never in production, whatever the flag says."""
    return dev_echo_requested() and not is_production()

