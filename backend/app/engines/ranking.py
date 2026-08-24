"""Configurable candidate ranking (spec weights).

Weights follow CLAUDE.md: Arabic 30, Manufacturing 25, Visual 20,
Wearability 10, Originality 10, Customer Fit 5.

Honesty note: only ArabicIntegrity and Manufacturability are derived from
deterministic engine results. VisualQuality, Wearability, Originality and
CustomerFit are geometric HEURISTICS — NOT ML-VALIDATED — and are labelled
as such in every score breakdown. The configuration (weights + version) is
persisted with each ranked candidate set.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..config import RANKING_CONFIG_VERSION


class RankingConfig(BaseModel):
    version: str = RANKING_CONFIG_VERSION
    arabic_integrity: float = 30.0
    manufacturability: float = 25.0
    visual_quality: float = 20.0
    wearability: float = 10.0
    originality: float = 10.0
    customer_fit: float = 5.0

    @property
    def total(self) -> float:
        return (
            self.arabic_integrity
            + self.manufacturability
            + self.visual_quality
            + self.wearability
            + self.originality
            + self.customer_fit
        )


DEFAULT_RANKING = RankingConfig()

HEURISTIC_DIMENSIONS = {
    "visual_quality": "HEURISTIC / NOT ML-VALIDATED (aspect-ratio + fill balance)",
    "wearability": "HEURISTIC / NOT ML-VALIDATED (size envelope + hole snag proxy)",
    "originality": "HEURISTIC / NOT ML-VALIDATED (feature distance from pool mean)",
    "customer_fit": "HEURISTIC / NOT ML-VALIDATED (no preference model yet; constant)",
}


def score_candidate(
    identity_verified: bool,
    validation_passed: bool,
    features,
    stroke_slack_ratio: float,
    pool_mean_vector: list[float] | None,
    feature_vector: list[float] | None,
    config: RankingConfig = DEFAULT_RANKING,
) -> tuple[float, dict]:
    """Returns (total_score_0_100, breakdown). Deterministic."""
    # Arabic integrity: binary from deterministic identity proof.
    arabic = 1.0 if identity_verified else 0.0
    # Manufacturability: validation gate + stroke margin above minimum.
    manufacturing = (0.6 + 0.4 * min(max(stroke_slack_ratio, 0.0), 1.0)) if validation_passed else 0.0

    visual = wear = orig = 0.0
    if features is not None:
        # Visual: pendant-friendly aspect ratio (~1.5-3) and moderate fill.
        aspect_fit = 1.0 / (1.0 + abs(features.aspect_ratio - 2.2) / 2.2)
        fill_fit = 1.0 - abs(features.fill_ratio - 0.45)
        visual = max(0.0, min(1.0, 0.6 * aspect_fit + 0.4 * fill_fit))
        # Wearability: within envelope, moderate size, few snag holes.
        size_fit = 1.0 - min(max((features.width_mm - 45) / 45, 0.0), 1.0)
        snag = 1.0 / (1.0 + 0.05 * features.hole_count)
        wear = max(0.0, min(1.0, 0.7 * size_fit + 0.3 * snag))
    if pool_mean_vector is not None and feature_vector is not None:
        dist = sum((a - b) ** 2 for a, b in zip(feature_vector, pool_mean_vector)) ** 0.5
        orig = min(dist / 2.0, 1.0)
    customer = 0.5  # no preference model in P0

    breakdown = {
        "config_version": config.version,
        "dimensions": {
            "arabic_integrity": {"weight": config.arabic_integrity, "value": round(arabic, 4), "basis": "deterministic identity proof"},
            "manufacturability": {"weight": config.manufacturability, "value": round(manufacturing, 4), "basis": "deterministic validation + stroke slack"},
            "visual_quality": {"weight": config.visual_quality, "value": round(visual, 4), "basis": HEURISTIC_DIMENSIONS["visual_quality"]},
            "wearability": {"weight": config.wearability, "value": round(wear, 4), "basis": HEURISTIC_DIMENSIONS["wearability"]},
            "originality": {"weight": config.originality, "value": round(orig, 4), "basis": HEURISTIC_DIMENSIONS["originality"]},
            "customer_fit": {"weight": config.customer_fit, "value": round(customer, 4), "basis": HEURISTIC_DIMENSIONS["customer_fit"]},
        },
    }
    total = (
        config.arabic_integrity * arabic
        + config.manufacturability * manufacturing
        + config.visual_quality * visual
        + config.wearability * wear
        + config.originality * orig
        + config.customer_fit * customer
    )
    return round(total, 4), breakdown
