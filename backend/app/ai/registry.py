"""Model/provider registry — every model identified with license + role.

Only commercially usable open-weight models are registered for production.
Non-commercial models (e.g. FLUX.1-dev/Kontext-dev) are intentionally absent
and must never be added without a license review.
"""
from __future__ import annotations

from pydantic import BaseModel


class ModelRecord(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_id: str  # internal id used in config
    hf_repo: str
    role: str  # visual_analysis | image_edit | text_to_image | fallback_image
    license: str
    commercial_use: bool
    version_pin: str  # revision/tag to pin in production
    authoritative_for: list[str]  # ALWAYS empty of Arabic/geometry/production truths


MODEL_REGISTRY: dict[str, ModelRecord] = {
    "qwen3-vl": ModelRecord(
        model_id="qwen3-vl",
        hf_repo="Qwen/Qwen3-VL-8B-Instruct",
        role="visual_analysis",
        license="Apache-2.0",
        commercial_use=True,
        version_pin="main",
        authoritative_for=[],
    ),
    "qwen-image-edit": ModelRecord(
        model_id="qwen-image-edit",
        hf_repo="Qwen/Qwen-Image-Edit",
        role="image_edit",
        license="Apache-2.0",
        commercial_use=True,
        version_pin="main",
        authoritative_for=[],
    ),
    "qwen-image": ModelRecord(
        model_id="qwen-image",
        hf_repo="Qwen/Qwen-Image",
        role="text_to_image",
        license="Apache-2.0",
        commercial_use=True,
        version_pin="main",
        authoritative_for=[],
    ),
    "flux-schnell": ModelRecord(
        model_id="flux-schnell",
        hf_repo="black-forest-labs/FLUX.1-schnell",
        role="fallback_image",
        license="Apache-2.0",
        commercial_use=True,
        version_pin="main",
        authoritative_for=[],
    ),
}


def get_model(model_id: str) -> ModelRecord:
    record = MODEL_REGISTRY[model_id]
    if not record.commercial_use:
        raise PermissionError(f"Model {model_id} is not commercially usable.")
    return record
