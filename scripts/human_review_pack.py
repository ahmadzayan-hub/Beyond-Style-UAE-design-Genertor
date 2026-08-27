#!/usr/bin/env python3
"""Generate the Human Aesthetic Review pack and its evidence.

This script prepares work for a person. It records no decisions: if nobody
has reviewed anything, every file says HUMAN_REVIEW_PENDING and the summary
says zero human decisions. Fabricating a verdict here would defeat the whole
point of the slice.

Usage: python3 scripts/human_review_pack.py [--write]
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.base import session_factory  # noqa: E402
from app.services.review_items import (  # noqa: E402
    PHRASE, REVIEW_CORPUS, REVIEW_PRODUCTS, SEVEN_NAMES, generate_review_pack,
)
from app.services.review_workflow import (  # noqa: E402
    CRITICAL_DIMENSIONS, CRITICAL_SCORE_THRESHOLD, HUMAN_DIMENSIONS,
    ai_advisory_status, curation_decisions, summarize,
)

OUT = ROOT / "docs" / "evidence" / "human-aesthetic-review"
SHEETS = OUT / "review-pack"

CARD_W, CARD_H, PROOF_H = 460, 400, 250


def _sheet(title: str, items: list[dict]) -> str:
    cols = 2
    rows = (len(items) + cols - 1) // cols or 1
    w, h = cols * CARD_W, rows * CARD_H + 64
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="18" y="30" font-family="sans-serif" font-size="20" fill="#111">{title}</text>',
        '<text x="18" y="50" font-family="sans-serif" font-size="12" fill="#666">'
        'HUMAN_REVIEW_PENDING — no aesthetic decision has been made by anyone yet.</text>',
    ]
    for i, item in enumerate(items):
        x, y = (i % cols) * CARD_W, 64 + (i // cols) * CARD_H
        pw, ph = item["proof_view"]
        pad = max(pw, ph) * 0.06
        scale = min((CARD_W - 40) / (pw + 2 * pad), PROOF_H / (ph + 2 * pad))
        parts.append(f'<g transform="translate({x},{y})">')
        parts.append(f'<rect width="{CARD_W-14}" height="{CARD_H-14}" fill="none" stroke="#ddd"/>')
        # Primary visual area: large enough for real artistic judgement.
        parts.append(
            f'<g transform="translate(20,16) scale({scale:.4f}) translate({pad},{pad})">'
            f'<path d="{item["proof_path_d"]}" fill="#111" fill-rule="evenodd"/></g>'
        )
        style = item["customer_style"] or "—"
        lines = [
            (f'{item["product"]} · {style}', 14, "#111"),
            (f'{item["font_family"]} · {item["source_text"]} · '
             f'{item["width_mm"]}×{item["height_mm"]}mm', 11, "#444"),
            ("MANUFACTURING PASS" if item["manufacturing_pass"] else "MANUFACTURING FAIL",
             11, "#0a0" if item["manufacturing_pass"] else "#b00"),
            ("proven production pattern" if item["golden_production_pattern"] else "", 11, "#a60"),
            ("APPROVE   ALLOW   EXPERIMENTAL   HIDE", 11, "#333"),
        ]
        for j, (text, size, colour) in enumerate(lines):
            if not text:
                continue
            safe = text.replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<text x="20" y="{PROOF_H + 40 + j * 18}" font-family="sans-serif" '
                f'font-size="{size}" fill="{colour}">{safe}</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def main(write: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SHEETS.mkdir(parents=True, exist_ok=True)

    print("· generating review items …")
    items = generate_review_pack(max_per_product=4)

    session = session_factory()()
    try:
        decisions = curation_decisions(session, items)
        from sqlalchemy import select

        from app.db import models as m
        recorded = session.execute(select(m.DesignReview)).scalars().all()
        human = [{
            "item_id": r.item_id, "reviewer": r.reviewer, "decision": r.decision,
            "mode": r.review_mode, "scores": r.scores, "note": r.note,
            "recipe_hash": r.recipe_hash, "created_at": r.created_at.isoformat(),
        } for r in recorded]
    finally:
        session.close()

    summary = summarize(decisions, len(human))
    advisory = ai_advisory_status()

    by_product: dict[str, list[dict]] = {}
    for item in items:
        by_product.setdefault(item["product"], []).append(item)

    product_style_map = {
        product: sorted({i["customer_style"] for i in group if i["customer_style"]})
        for product, group in by_product.items()
    }

    if write:
        for product, group in by_product.items():
            (SHEETS / f"{product}.svg").write_text(
                _sheet(f"Review pack — {product}", group), encoding="utf-8")
        (OUT / "review-items.json").write_text(json.dumps({
            "corpus": REVIEW_CORPUS, "phrase": PHRASE, "seven_names": SEVEN_NAMES,
            "products": REVIEW_PRODUCTS,
            "dimensions": HUMAN_DIMENSIONS,
            "critical_dimensions": CRITICAL_DIMENSIONS,
            "critical_score_threshold": CRITICAL_SCORE_THRESHOLD,
            "items": items,
        }, indent=1, ensure_ascii=False) + "\n")
        (OUT / "human-scores.json").write_text(json.dumps({
            "status": summary["human_review_status"],
            "note": "Human scores only. Never merged with engineering or AI advisory scores.",
            "reviews": human,
        }, indent=1, ensure_ascii=False) + "\n")
        (OUT / "curation-decisions.json").write_text(json.dumps({
            "note": "Derived from hard gates first, then the newest human review. "
                    "An item with no review stays EXPERIMENTAL / HUMAN_REVIEW_PENDING.",
            "summary": summary, "decisions": decisions,
        }, indent=1, ensure_ascii=False) + "\n")
        (OUT / "product-style-map.json").write_text(
            json.dumps(product_style_map, indent=1, ensure_ascii=False) + "\n")
        (OUT / "AI-advisory.json").write_text(
            json.dumps(advisory, indent=1, ensure_ascii=False) + "\n")
        (OUT / "summary.md").write_text(_summary_md(summary, advisory, by_product), encoding="utf-8")

    print(f"\nitems: {summary['review_items']} across {len(by_product)} products")
    print(f"human reviews recorded: {summary['human_reviews_recorded']}")
    print(f"status: {summary['human_review_status']}")
    print(f"states: {summary['states']}")
    print(f"blocked by hard gate: {summary['blocked_by_hard_gate']}")
    print(f"AI advisory: {advisory['status']}")
    if not write:
        print("\n(dry run — pass --write)")
    return 0


def _summary_md(summary: dict, advisory: dict, by_product: dict) -> str:
    rows = "\n".join(
        f"| {product} | {len(group)} | "
        f"{sum(1 for i in group if i['manufacturing_pass'])} | "
        f"{sum(1 for i in group if i['golden_production_pattern'])} |"
        for product, group in sorted(by_product.items())
    )
    return f"""# Human Aesthetic Review — pack summary

**Status: {summary['human_review_status']}.**
{summary['human_reviews_recorded']} human decisions have been recorded.
{summary['awaiting_human_review']} items await review.

Nothing in this pack has been aesthetically approved. The software prepared
the work; the judgement is Beyond Style's to make.

| product | items | manufacturing pass | proven production pattern |
|---|---|---|---|
{rows}

## What a reviewer decides

Quick curation: APPROVE · ALLOW · EXPERIMENTAL · HIDE.
Deep review additionally records all twelve dimensions 1–5 plus a note.

## What a reviewer cannot do

Approval is permission to SHOW, never permission to ship something unsafe.
An APPROVE on an item failing Arabic identity, manufacturing or rights
resolves to HIDDEN with the blocking gate recorded — {summary['blocked_by_hard_gate']}
items in this pack are in that position on engineering grounds alone.

A design reaches PRODUCTION_RECOMMENDED only with Arabic identity PASS,
rights PASS, manufacturing PASS, a human APPROVE, and no critical dimension
(Readability, JewellerySuitability, ProductFit) below {CRITICAL_SCORE_THRESHOLD}.

## AI advisory

{advisory['status']} — {advisory['note']}
An advisory score is stored as AI_ADVISORY_SCORE and can never promote a
variant; only a human decision is read when curation is derived.

## Sheets

`review-pack/<product>.svg` — one card per item, proof first, customer style
word as the label, OpenType/axis detail in secondary metadata.
"""


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
