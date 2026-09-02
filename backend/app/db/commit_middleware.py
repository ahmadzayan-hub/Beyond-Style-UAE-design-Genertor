"""Commit-before-respond — pure ASGI middleware.

FastAPI 0.118+ runs yield-dependency teardown (where the request session
used to commit) AFTER the response has been sent. Under real HTTP that is
a data race: a client that reads "10 candidates" and immediately fetches
one could beat the commit and get 404 — reproduced with uvicorn while
TestClient stayed green. This middleware commits the request session on
`http.response.start` for success responses (2xx/3xx), so no response
leaves the server before its data is durable, and rolls back on error
responses. A commit failure turns the response into a 500 instead of a
silently lost write.
"""
from __future__ import annotations

import json

import anyio


class SessionCommitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        failed = {"value": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                session = state.get("db_session")
                if session is not None and not state.get("db_committed"):
                    status = message.get("status", 500)
                    try:
                        if 200 <= status < 400:
                            await anyio.to_thread.run_sync(session.commit)
                        else:
                            await anyio.to_thread.run_sync(session.rollback)
                        state["db_committed"] = True
                    except Exception as exc:  # noqa: BLE001 — surfaced as 500
                        await anyio.to_thread.run_sync(session.rollback)
                        state["db_committed"] = True
                        failed["value"] = True
                        body = json.dumps({
                            "detail": "The change could not be saved.",
                            "error_code": "BACKEND_UNAVAILABLE",
                            "commit_error": type(exc).__name__,
                        }).encode()
                        await send({
                            "type": "http.response.start",
                            "status": 500,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())],
                        })
                        await send({"type": "http.response.body", "body": body, "more_body": False})
                        return
            elif message["type"] == "http.response.body" and failed["value"]:
                return  # original body dropped; the 500 already went out
            await send(message)

        await self.app(scope, receive, send_wrapper)
