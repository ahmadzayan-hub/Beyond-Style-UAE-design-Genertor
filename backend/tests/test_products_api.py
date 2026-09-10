"""Product catalogue + size guide — owner-stated data served honestly."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.products import recommended_bracelet_cm
from app.main import app

client = TestClient(app)
DATA = Path(__file__).resolve().parents[1] / "app" / "data"


def test_catalogue_lists_owner_stated_prices():
    r = client.get("/api/products/catalogue")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "AED" and body["evidence_level"] == "OWNER_CATALOGUE_STATED"
    assert body["count"] == 75
    codes = [i["code"] for i in body["items"]]
    assert len(codes) == len(set(codes))
    assert all(isinstance(i["price_from"], int) and i["price_from"] > 0 for i in body["items"])
    assert {i["text_process"] for i in body["items"]} == {"engraving", "cut_out", "none"}


def test_catalogue_filters_and_item_lookup():
    rings = client.get("/api/products/catalogue", params={"family": "ring"}).json()
    assert rings["count"] == 24 and all(i["family"] == "ring" for i in rings["items"])
    assert all(i["text_process"] in ("engraving", "cut_out", "none") for i in rings["items"])
    engraved = client.get("/api/products/catalogue", params={"family": "ring", "text_process": "engraving"}).json()
    assert 0 < engraved["count"] < rings["count"]
    item = client.get("/api/products/catalogue/nck-27").json()
    assert item["code"] == "NCK-27" and "prayer_disc" in item["tags"] and "sacred_text" in item["tags"]
    assert client.get("/api/products/catalogue/NCK-999").status_code == 404
    bad = client.get("/api/products/catalogue", params={"family": "tiara"})
    assert bad.status_code == 404 and bad.json()["detail"]["code"] == "UNKNOWN_PRODUCT_FAMILY"


def test_size_guide_names_its_evidence_levels():
    body = client.get("/api/products/size-guide").json()
    assert body["bracelet"]["evidence_level"] == "OWNER_PUBLISHED"
    assert [f["bracelet_cm"] for f in body["bracelet"]["fits"]] == [16, 17, 18, 19, 20, 21]
    assert body["necklace"]["evidence_level"] == "INDUSTRY_STANDARD"
    assert [l["cm"] for l in body["necklace"]["lengths"]] == [35, 40, 45, 50, 55, 60, 70, 80]
    assert body["chains"]["evidence_level"] == "OWNER_CATALOGUE_STATED"
    c160 = next(p for p in body["chains"]["profiles"] if p["code"] == "C160")
    assert c160["necklace"] == [[55, 26.1], [60, 28.4], [65, 31.2]] and c160["bracelet"] == [[21, 9.8]]


def test_bracelet_recommendation_is_deterministic():
    assert recommended_bracelet_cm(16.0)["bracelet_cm"] == 17.0
    assert recommended_bracelet_cm(16.0, "loose")["bracelet_cm"] == 18.0
    r = client.get("/api/products/size-guide/bracelet", params={"wrist_cm": 17.5, "fit": "slightly_loose"})
    assert r.status_code == 200 and r.json()["bracelet_cm"] == 19.0
    assert client.get("/api/products/size-guide/bracelet", params={"wrist_cm": 5}).status_code == 422
    assert client.get("/api/products/size-guide/bracelet", params={"wrist_cm": 16, "fit": "tight"}).status_code == 422


def test_catalogue_file_matches_golden_case_evidence():
    """The catalogue transcription is bound to the golden case that holds
    the page hashes, and the size guide to its owner creative."""
    from app.data.golden_production_cases import GOLDEN_PRODUCTION_CASES
    by_id = {c["case_id"]: c for c in GOLDEN_PRODUCTION_CASES}
    assert len(by_id["BS-GPC-0023-owner-product-catalogue-2026-09"]["evidence"]) == 9
    wear = json.loads((DATA / "wearability.json").read_text())
    assert len(wear["bracelet_size_guide"]["source_sha256"]) == 64
    chain_case = by_id["BS-GPC-0017-mens-925-silver-chain-catalogue"]
    assert len(chain_case["evidence"]) == len(wear["chain_catalogue"]["profiles"]) == 5
