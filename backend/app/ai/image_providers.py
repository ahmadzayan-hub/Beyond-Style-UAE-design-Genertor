"""Image generation providers (visualization only, never truth).

`OpenAIImage2Provider` uses the official OpenAI SDK with GPT-Image-2.
The API key is server-side only: it is read from the environment inside
this module, never returned by any endpoint and never logged.

No key / SDK absent ⇒ ImageProviderUnavailable, so the deterministic
designer keeps working with SVG previews labelled
PHOTOREAL_PREVIEW_UNAVAILABLE.
"""
from __future__ import annotations

import base64
import importlib.util
import os
from typing import Protocol

from .visual_brief import VisualBrief, VisualPromptBuilder

OPENAI_IMAGE_ENABLED = os.environ.get("OPENAI_IMAGE_ENABLED", "false").lower() == "true"
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
OPENAI_IMAGE_PROVIDER = os.environ.get("OPENAI_IMAGE_PROVIDER", "gpt-image-2")

#: Indicative USD per generated image by quality mode (budget estimates
#: only — actual spend is reconciled from API usage where returned).
COST_PER_IMAGE_USD = {"DRAFT": 0.02, "STANDARD": 0.07, "FINAL": 0.19}
QUALITY_TO_API = {"DRAFT": "low", "STANDARD": "medium", "FINAL": "high"}
SIZE_BY_QUALITY = {"DRAFT": "1024x1024", "STANDARD": "1024x1024", "FINAL": "1536x1536"}


class ImageProviderUnavailable(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"IMAGE_PROVIDER_UNAVAILABLE: {reason}")


class ImageGenerationProvider(Protocol):
    def generate(self, brief: VisualBrief, prompt: str) -> bytes: ...
    def edit(self, image_bytes: bytes, brief: VisualBrief, prompt: str) -> bytes: ...
    def health_check(self) -> dict: ...
    def estimate_cost(self, brief: VisualBrief, images: int = 1) -> float: ...


class OpenAIImage2Provider:
    """GPT-Image-2 via the official OpenAI API (server-side key only)."""

    name = "openai-gpt-image-2"

    def __init__(self, model: str | None = None):
        self.model = model or OPENAI_IMAGE_MODEL
        self._client = None

    # ----------------------------------------------------------- health
    @staticmethod
    def _sdk_available() -> bool:
        return importlib.util.find_spec("openai") is not None

    @staticmethod
    def _key_configured() -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def _guard(self) -> None:
        if not OPENAI_IMAGE_ENABLED:
            raise ImageProviderUnavailable("OPENAI_IMAGE_ENABLED=false")
        if not self._sdk_available():
            raise ImageProviderUnavailable("openai SDK not installed")
        if not self._key_configured():
            raise ImageProviderUnavailable("OPENAI_API_KEY not configured (server-side only)")

    def health_check(self) -> dict:
        try:
            self._guard()
            status = "ready"
        except ImageProviderUnavailable as exc:
            status = f"unavailable: {exc.reason}"
        return {
            "provider": self.name,
            "model": self.model,
            "status": status,
            "enabled_flag": OPENAI_IMAGE_ENABLED,
            "sdk_installed": self._sdk_available(),
            "key_configured": self._key_configured(),  # boolean only — never the key
            "role": "visualization only; never manufacturing truth",
        }

    def estimate_cost(self, brief: VisualBrief, images: int = 1) -> float:
        return round(COST_PER_IMAGE_USD.get(brief.quality, 0.07) * max(images, 1), 4)

    def _client_or_raise(self):
        self._guard()
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(timeout=float(os.environ.get("IMAGE_TIMEOUT_S", 180)))
        return self._client

    @staticmethod
    def _decode(result) -> bytes:
        item = result.data[0]
        b64 = getattr(item, "b64_json", None)
        if not b64:
            raise ImageProviderUnavailable("provider returned no image payload")
        return base64.b64decode(b64)

    # ------------------------------------------------------------ calls
    def generate(self, brief: VisualBrief, prompt: str) -> bytes:
        client = self._client_or_raise()
        result = client.images.generate(
            model=self.model,
            prompt=prompt,
            size=SIZE_BY_QUALITY.get(brief.quality, "1024x1024"),
            quality=QUALITY_TO_API.get(brief.quality, "medium"),
            n=1,
        )
        return self._decode(result)

    def edit(self, image_bytes: bytes, brief: VisualBrief, prompt: str) -> bytes:
        """Image-to-image: the canonical design render conditions the output."""
        client = self._client_or_raise()
        import io

        buf = io.BytesIO(image_bytes)
        buf.name = "canonical_design.png"
        result = client.images.edit(
            model=self.model,
            image=buf,
            prompt=prompt,
            size=SIZE_BY_QUALITY.get(brief.quality, "1024x1024"),
            quality=QUALITY_TO_API.get(brief.quality, "medium"),
            n=1,
        )
        return self._decode(result)

    # --------------------------------------------------- semantic modes
    def create_product_preview(self, canonical_png: bytes, brief: VisualBrief) -> bytes:
        return self.edit(canonical_png, brief, VisualPromptBuilder.build(brief))

    def create_lifestyle_preview(self, canonical_png: bytes, brief: VisualBrief) -> bytes:
        return self.edit(canonical_png, brief, VisualPromptBuilder.build(brief))

    def create_material_variant(self, canonical_png: bytes, brief: VisualBrief) -> bytes:
        return self.edit(canonical_png, brief, VisualPromptBuilder.build(brief))

    def create_reference_inspired_preview(
        self, canonical_png: bytes, brief: VisualBrief, reference_style_dna: dict
    ) -> bytes:
        """Reference DNA supplies mood only — the canonical geometry still
        rules, and no referenced artwork is reproduced."""
        return self.edit(canonical_png, brief,
                         VisualPromptBuilder.build(brief, reference_style_dna))


def get_image_provider() -> OpenAIImage2Provider:
    return OpenAIImage2Provider()


def image_provider_status() -> dict:
    return {
        "configured_provider": OPENAI_IMAGE_PROVIDER,
        "health": get_image_provider().health_check(),
        "quality_modes": sorted(COST_PER_IMAGE_USD),
        "estimated_cost_per_image_usd": COST_PER_IMAGE_USD,
    }
