"""Product catalogue and size guide — owner-stated reference data.

Everything served here is transcribed from Beyond Style's own catalogue and
size-guide creatives (evidence: golden cases BS-GPC-0017/0023 and the
bracelet size guide) or from industry-standard length charts. Prices are the
owner's stated starting prices; nothing is computed or invented, and the
data file names its evidence level on every table.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/products", tags=["products"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOGUE_FILE = DATA_DIR / "product_catalogue.json"
WEARABILITY_FILE = DATA_DIR / "wearability.json"


@lru_cache(maxsize=1)
def load_catalogue() -> dict:
    return json.loads(CATALOGUE_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_wearability() -> dict:
    return json.loads(WEARABILITY_FILE.read_text(encoding="utf-8"))


@router.get("/catalogue")
def product_catalogue(family: str | None = None, text_process: str | None = None):
    """Owner catalogue items with stated starting prices (AED)."""
    data = load_catalogue()
    items = data["items"]
    if family is not None:
        if family not in data["families"]:
            raise HTTPException(status_code=404, detail={"code": "UNKNOWN_PRODUCT_FAMILY", "family": family,
                                                         "known": sorted(data["families"])})
        items = [i for i in items if i["family"] == family]
    if text_process is not None:
        items = [i for i in items if i["text_process"] == text_process]
    return {
        "catalogue_version": data["catalogue_version"],
        "currency": data["currency"],
        "evidence_level": data["evidence_level"],
        "families": data["families"],
        "count": len(items),
        "items": items,
    }


@router.get("/catalogue/{code}")
def product_catalogue_item(code: str):
    data = load_catalogue()
    for item in data["items"]:
        if item["code"].lower() == code.lower():
            return {"currency": data["currency"], "evidence_level": data["evidence_level"], **item}
    raise HTTPException(status_code=404, detail={"code": "UNKNOWN_PRODUCT_CODE", "product_code": code})


@router.get("/size-guide")
def size_guide():
    """Bracelet fit table (owner-published), necklace length chart
    (industry standard) and the men's chain length/weight catalogue
    (owner-stated). Each table carries its own evidence_level."""
    data = load_wearability()
    return {
        "wearability_version": data["wearability_version"],
        "bracelet": data["bracelet_size_guide"],
        "necklace": data["necklace_lengths_cm"],
        "chains": data["chain_catalogue"],
    }


def recommended_bracelet_cm(wrist_cm: float, fit: str = "standard") -> dict:
    """Deterministic lookup used by the wearability heuristic."""
    guide = load_wearability()["bracelet_size_guide"]
    row = next((r for r in guide["fits"] if r["fit"] == fit), None)
    if row is None:
        raise ValueError(f"unknown fit {fit!r}")
    add = {"snug": 1.0, "standard": 1.0, "slightly_loose": 1.5, "loose": 2.0, "very_loose": 2.0, "extra_loose": 2.0}[fit]
    return {"fit": fit, "wrist_cm": wrist_cm, "bracelet_cm": round(wrist_cm + add, 1),
            "evidence_level": guide["evidence_level"]}


@router.get("/size-guide/bracelet")
def bracelet_size(wrist_cm: float, fit: str = "standard"):
    if not 10 <= wrist_cm <= 30:
        raise HTTPException(status_code=422, detail={"code": "WRIST_OUT_OF_RANGE", "wrist_cm": wrist_cm})
    try:
        return recommended_bracelet_cm(wrist_cm, fit)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_FIT", "fit": fit,
                                                     "known": [r["fit"] for r in load_wearability()["bracelet_size_guide"]["fits"]]})


@router.get("/specifications")
def specifications(product: str | None = None, audience: str | None = None, material: str | None = None,
                   text_length: int | None = None):
    """Jewellery specification knowledge with evidence levels. With `product`
    the response is the copilot's expert brief for that product; without it,
    the whole knowledge base plus its (honest) online-research status."""
    from ..services.specifications import expert_brief, load_specifications, research_status

    if product is None:
        data = load_specifications()
        return {"specifications_version": data["specifications_version"], "research_status": research_status(),
                "evidence_levels": data["evidence_levels"], "sections": data["sections"]}
    return expert_brief(product, audience=audience, material=material, text_length=text_length)
