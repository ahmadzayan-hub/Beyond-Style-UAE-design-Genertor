"""Visual Studio: DESIGN → IMAGE only.

Canonical approved/validated geometry is rendered to a transparent PNG,
sent to the image provider as the authoritative reference, and the
result is checked by the Visual Identity Guard before anyone sees it.

Never the other direction: an AI raster can never become geometry, and
`ai_generations` rows are display artifacts (kind='ai_preview') that the
export path refuses.
"""
from __future__ import annotations

import hashlib
import io
import uuid

from PIL import Image, ImageDraw
from shapely import wkt as shapely_wkt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.image_providers import ImageProviderUnavailable, get_image_provider
from ..ai.preview_guard import identity_divergence
from ..ai.visual_brief import QUALITY_MODES, VisualBrief, VisualPromptBuilder
from ..db import models as m
from .design_service import _emit

MAX_PREVIEW_RETRIES = 2
#: Identity guard thresholds on 1 − IoU vs the canonical silhouette.
PASS_MAX = 0.18
REVIEW_MAX = 0.30
RENDER_PX = 1024


class PreviewRejected(Exception):
    def __init__(self, status: str, guard: dict):
        self.status = status
        self.guard = guard
        super().__init__(f"{status}: divergence {guard['divergence']}")


def render_canonical_png(geometry_wkt: str, size_px: int = RENDER_PX) -> bytes:
    """Deterministic transparent raster of the canonical geometry — the
    conditioning image. Rasterization is for AI conditioning and display
    only; the vector geometry remains the manufacturing truth."""
    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    scale = (size_px * 0.86) / max(w, h)
    off_x = (size_px - w * scale) / 2
    off_y = (size_px - h * scale) / 2
    img = Image.new("RGBA", (size_px, size_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for poly in polys:
        def to_px(coords):
            return [
                (off_x + (x - minx) * scale, size_px - (off_y + (y - miny) * scale))
                for x, y in coords
            ]

        draw.polygon(to_px(poly.exterior.coords), fill=(38, 38, 38, 255))
        for ring in poly.interiors:
            draw.polygon(to_px(ring.coords), fill=(0, 0, 0, 0))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def guard_status(divergence: float) -> str:
    if divergence <= PASS_MAX:
        return "PASS"
    if divergence <= REVIEW_MAX:
        return "REVIEW_REQUIRED"
    return "REJECTED_GEOMETRY_DRIFT"


def build_brief(version: m.DesignVersion, **overrides) -> VisualBrief:
    features = (version.validation or {}).get("features") or {}
    geom = shapely_wkt.loads(version.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    data = {
        "product_type": overrides.pop("product_type", None) or "pendant",
        "source_text_hash": version.source_text_sha256,
        "design_version_id": str(version.id),
        "geometry_hash": version.geometry_hash,
        "dimensions_mm": {
            "width_mm": round(maxx - minx, 2),
            "height_mm": round(maxy - miny, 2),
            "thickness_mm": features.get("thickness_mm"),
        },
    }
    data.update({k: v for k, v in overrides.items() if v is not None})
    if data.get("quality") not in QUALITY_MODES:
        data["quality"] = "DRAFT"
    return VisualBrief(**data)


def session_spend_usd(session: Session, request_id: uuid.UUID) -> float:
    rows = session.execute(
        select(m.AIGeneration).where(m.AIGeneration.design_request_id == request_id)
    ).scalars().all()
    return round(sum(r.cost_usd for r in rows), 6)


def generate_preview(
    session: Session,
    version: m.DesignVersion,
    request_id: uuid.UUID,
    brief: VisualBrief,
    reference_style_dna: dict | None = None,
    max_session_cost_usd: float = 5.0,
    max_images_per_session: int = 20,
) -> m.AIGeneration:
    """Cached, budgeted, identity-guarded preview generation.

    Raises ImageProviderUnavailable when no provider exists — the caller
    falls back to the deterministic SVG preview.
    """
    cache_key = brief.cache_key()
    cached = session.execute(
        select(m.AIGeneration).where(
            m.AIGeneration.cache_key == cache_key,
            m.AIGeneration.guard_status.in_(("PASS", "REVIEW_REQUIRED")),
        )
    ).scalars().first()
    if cached is not None:
        _emit(session, "AI_PREVIEW_CACHE_HIT", request_id=request_id,
              version_id=version.id, metadata={"cache_key": cache_key})
        return cached

    provider = get_image_provider()
    provider._guard()  # raises ImageProviderUnavailable before any spend

    prior = session.execute(
        select(m.AIGeneration).where(m.AIGeneration.design_request_id == request_id)
    ).scalars().all()
    if len(prior) >= max_images_per_session:
        raise PreviewRejected("BUDGET_IMAGE_COUNT_EXCEEDED",
                              {"divergence": 0.0, "images": len(prior)})
    spent = round(sum(p.cost_usd for p in prior), 6)
    estimate = provider.estimate_cost(brief)
    if spent + estimate > max_session_cost_usd:
        raise PreviewRejected("BUDGET_COST_EXCEEDED",
                              {"divergence": 0.0, "spent_usd": spent, "estimate_usd": estimate})

    canonical_png = render_canonical_png(version.geometry_wkt)
    prompt = VisualPromptBuilder.build(brief, reference_style_dna)
    attempts, cost, last_guard = 0, 0.0, {"divergence": 1.0}
    image_bytes = None
    status = "REJECTED_GEOMETRY_DRIFT"

    while attempts <= MAX_PREVIEW_RETRIES:  # bounded — never an infinite loop
        attempts += 1
        strengthened = prompt if attempts == 1 else (
            prompt + "\nRETRY: the previous attempt altered the design. Reproduce the supplied "
                     "silhouette and lettering EXACTLY; change only material, lighting and scene."
        )
        candidate = (
            provider.create_reference_inspired_preview(canonical_png, brief, reference_style_dna)
            if reference_style_dna
            else provider.create_product_preview(canonical_png, brief)
        )
        cost = round(cost + provider.estimate_cost(brief), 6)
        divergence = identity_divergence(version.geometry_wkt, candidate)
        last_guard = {"divergence": round(divergence, 4), "attempt": attempts,
                      "pass_max": PASS_MAX, "review_max": REVIEW_MAX}
        status = guard_status(divergence)
        image_bytes = candidate
        if status == "PASS":
            break

    from ..security.uploads import get_storage

    storage_key = get_storage().put(image_bytes, ".png") if image_bytes else None
    record = m.AIGeneration(
        design_request_id=request_id,
        design_version_id=version.id,
        kind="ai_preview",
        provider=provider.name,
        model=provider.model,
        visual_brief=brief.model_dump(),
        cache_key=cache_key,
        geometry_hash=version.geometry_hash,
        source_text_sha256=version.source_text_sha256,
        prompt=prompt,
        storage_key=storage_key,
        content_sha256=hashlib.sha256(image_bytes).hexdigest() if image_bytes else None,
        guard_status=status,
        guard_report=last_guard,
        attempts=attempts,
        cost_usd=cost,
        quality=brief.quality,
    )
    session.add(record)
    session.flush()
    _emit(session, "AI_PREVIEW_GENERATED", request_id=request_id, version_id=version.id,
          metadata={"guard_status": status, "attempts": attempts, "cost_usd": cost,
                    "provider": provider.name, "model": provider.model,
                    "cache_key": cache_key})
    if status == "REJECTED_GEOMETRY_DRIFT":
        raise PreviewRejected(status, last_guard)
    return record
