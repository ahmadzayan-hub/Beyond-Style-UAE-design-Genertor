"""Beyond Style UAE — backend API (P0 Golden Path slice)."""
from __future__ import annotations

from fastapi import FastAPI

from .api.designs import fonts_router, router as designs_router, versions_router
from .api.intake import router as intake_router
from .config import SCHEMA_VERSION

app = FastAPI(
    title="Beyond Style UAE — AI Jewellery Designer API",
    version=SCHEMA_VERSION,
)
app.include_router(designs_router)
app.include_router(intake_router)
app.include_router(versions_router)
app.include_router(fonts_router)


@app.get("/health")
def health():
    return {"status": "ok", "schema_version": SCHEMA_VERSION}
