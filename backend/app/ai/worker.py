"""AI worker process — runs models OUTSIDE the API process.

Usage:  python -m app.ai.worker
Polls the ai_jobs table, executes with per-job timeout + bounded retries,
records honest terminal states (DONE / FAILED / MODEL_UNAVAILABLE).
Cancellation: set status=CANCELLED; the worker skips it.
"""
from __future__ import annotations

import concurrent.futures
import time
import uuid

from sqlalchemy import select

from ..db import models as m
from ..db.base import session_factory
from . import config
from .providers import ModelUnavailable, get_image_editor, get_visual_analyzer

POLL_INTERVAL_S = 2.0


def _execute(job: m.AIJob) -> dict:
    payload = job.payload
    if job.kind == "analyze":
        from ..services.reference_intelligence import analyze_reference

        session = session_factory()()
        try:
            row = analyze_reference(session, uuid.UUID(payload["reference_id"]))
            session.commit()
            return {"reference_dna_id": str(row.id), "source": row.source}
        finally:
            session.close()
    if job.kind == "preview":
        from ..security.uploads import get_storage

        editor = get_image_editor()
        base_image = bytes.fromhex(payload["image_hex"]) if "image_hex" in payload else get_storage().get(payload["storage_key"])
        result = editor.edit(base_image, payload["prompt"])
        key = get_storage().put(result, ".png")
        return {"storage_key": key}
    raise ValueError(f"Unknown job kind: {job.kind}")


def run_once() -> bool:
    """Process at most one queued job. Returns True if one was handled."""
    session = session_factory()()
    try:
        job = session.execute(
            select(m.AIJob).where(m.AIJob.status == "QUEUED").order_by(m.AIJob.created_at).with_for_update(skip_locked=True)
        ).scalars().first()
        if job is None:
            return False
        job.status = "RUNNING"
        job.attempts += 1
        session.commit()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(_execute, job).result(timeout=job.timeout_s)
            job.status = "DONE"
            job.result = result
        except ModelUnavailable as exc:
            job.status = "MODEL_UNAVAILABLE"
            job.error = str(exc)
        except concurrent.futures.TimeoutError:
            job.status = "QUEUED" if job.attempts <= config.AI_MAX_RETRIES else "FAILED"
            job.error = f"timeout after {job.timeout_s}s (attempt {job.attempts})"
        except Exception as exc:  # honest failure, bounded retries
            job.status = "QUEUED" if job.attempts <= config.AI_MAX_RETRIES else "FAILED"
            job.error = str(exc)[:2000]
        session.commit()
        return True
    finally:
        session.close()


def main() -> None:  # pragma: no cover — long-running entrypoint
    print(f"AI worker started (AI_MODE={config.AI_MODE})")
    while True:
        if not run_once():
            time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":  # pragma: no cover
    main()
