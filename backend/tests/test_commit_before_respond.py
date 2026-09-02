"""Commit-before-respond middleware — the fix for the FastAPI>=0.118 race.

The request session must be committed BEFORE `http.response.start` is
forwarded (so no client can observe a response whose data is not yet
durable), rolled back on error responses, and a commit failure must turn
into a 500 rather than a silently lost write.
"""
import json

import anyio
import pytest

from app.db.commit_middleware import SessionCommitMiddleware


class FakeSession:
    def __init__(self, fail_commit=False):
        self.events = []
        self.fail_commit = fail_commit

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("db down")
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")


def _run(status: int, session: FakeSession):
    sent = []

    async def app(scope, receive, send):
        scope["state"]["db_session"] = session
        scope["state"]["db_committed"] = False
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b'{"ok":true}', "more_body": False})

    async def send(message):
        sent.append((message["type"], message.get("status"), list(session.events)))

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "state": {}}
    anyio.run(SessionCommitMiddleware(app), scope, receive, send)
    return sent, scope


def test_commit_happens_before_response_start_is_forwarded():
    session = FakeSession()
    sent, scope = _run(200, session)
    start = next(s for s in sent if s[0] == "http.response.start")
    assert start[2] == ["commit"], "commit must precede the forwarded response start"
    assert scope["state"]["db_committed"] is True


def test_error_responses_roll_back():
    session = FakeSession()
    sent, _ = _run(422, session)
    start = next(s for s in sent if s[0] == "http.response.start")
    assert start[2] == ["rollback"]


def test_commit_failure_becomes_a_500_not_a_lost_write():
    session = FakeSession(fail_commit=True)
    sent, _ = _run(200, session)
    starts = [s for s in sent if s[0] == "http.response.start"]
    assert len(starts) == 1 and starts[0][1] == 500
    assert session.events == ["rollback"]
    bodies = [s for s in sent if s[0] == "http.response.body"]
    assert len(bodies) == 1  # original body dropped


def test_non_http_scopes_pass_through():
    async def app(scope, receive, send):
        await send({"type": "lifespan.startup.complete"})

    sent = []

    async def send(m):
        sent.append(m["type"])

    async def receive():
        return {}

    anyio.run(SessionCommitMiddleware(app), {"type": "lifespan"}, receive, send)
    assert sent == ["lifespan.startup.complete"]
