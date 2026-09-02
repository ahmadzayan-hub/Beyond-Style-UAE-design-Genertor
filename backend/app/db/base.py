"""SQLAlchemy engine/session setup. PostgreSQL is the source of truth."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import DATABASE_URL


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def session_factory() -> sessionmaker:
    get_engine()
    return _SessionLocal


def get_session(request: Request):
    """FastAPI dependency: one session per request.

    The commit happens in SessionCommitMiddleware at `http.response.start`
    (before any byte of the response leaves), because FastAPI 0.118+ runs
    this generator's exit code only AFTER the response is sent. The
    teardown below is the safety net for non-HTTP callers and for anything
    left pending: commit if nothing committed yet, roll back on error,
    always close."""
    session: Session = session_factory()()
    request.state.db_session = session
    request.state.db_committed = False
    try:
        yield session
        if not request.state.db_committed:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine():
    """Test helper: discard cached engine (e.g. after DATABASE_URL change)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
