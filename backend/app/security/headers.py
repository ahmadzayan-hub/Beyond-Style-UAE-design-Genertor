"""Security response headers — pure ASGI middleware.

The API serves JSON, SVG and PNG. The policy denies every embedding and
script execution context: an SVG proof opened directly cannot run
scripts, nothing may frame the API, MIME types are not sniffed, and
referrers are not leaked. HSTS is emitted only when the deployment
declares itself HTTPS-terminated (SECURE_HSTS=true), so local HTTP dev is
unaffected.
"""
from __future__ import annotations

import os

_BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-resource-policy", b"cross-origin"),  # the Vercel origin fetches us
    (b"content-security-policy",
     b"default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"),
]


def _headers() -> list[tuple[bytes, bytes]]:
    out = list(_BASE_HEADERS)
    if os.environ.get("SECURE_HSTS", "false").lower() == "true":
        out.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    return out


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app
        self.extra = _headers()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                for k, v in self.extra:
                    if k not in present:
                        headers.append((k, v))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
