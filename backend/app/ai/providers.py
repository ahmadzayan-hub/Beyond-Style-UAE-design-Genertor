"""Provider abstraction for visual AI.

Interfaces: VisualAnalyzer / ImageGenerator / ImageEditor / EmbeddingProvider.
Local implementations lazy-import torch/transformers/diffusers and load
weights only inside a worker process — NEVER in the API process. When
AI_MODE=disabled, dependencies are missing, or no accelerator/weights
exist, calls raise ModelUnavailable — results are never faked.

The models are creative/reference tools only: nothing here may write
source text, glyph geometry, dimensions, validation results or exports.
"""
from __future__ import annotations

import importlib.util
from typing import Protocol

from . import config
from .registry import ModelRecord, get_model


class ModelUnavailable(Exception):
    """Raised when no real model can serve the request. API maps this to a
    graceful MODEL_UNAVAILABLE response; deterministic flow continues."""

    def __init__(self, model_id: str, reason: str):
        self.model_id = model_id
        self.reason = reason
        super().__init__(f"MODEL_UNAVAILABLE[{model_id}]: {reason}")


class VisualAnalyzer(Protocol):
    def analyze(self, image_bytes: bytes, instruction: str) -> dict: ...
    def health(self) -> dict: ...


class ImageGenerator(Protocol):
    def generate(self, prompt: str, width: int, height: int) -> bytes: ...
    def health(self) -> dict: ...


class ImageEditor(Protocol):
    def edit(self, image_bytes: bytes, prompt: str, mask_bytes: bytes | None = None) -> bytes: ...
    def health(self) -> dict: ...


class EmbeddingProvider(Protocol):
    def embed_image(self, image_bytes: bytes) -> list[float]: ...
    def health(self) -> dict: ...


def _deps_available() -> bool:
    return all(
        importlib.util.find_spec(m) is not None for m in ("torch", "transformers")
    )


def _diffusers_available() -> bool:
    return _deps_available() and importlib.util.find_spec("diffusers") is not None


def _accelerator_status() -> str:
    if not _deps_available():
        return "dependencies-missing (pip install -r requirements-ai.txt)"
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu-only (usable but slow; verify latency before enabling)"


class _LocalBase:
    """Shared unavailability logic. Subclasses implement `_run` with real
    model code; loading happens lazily on first call (worker process)."""

    def __init__(self, model_id: str):
        self.record: ModelRecord = get_model(model_id)
        self._pipeline = None

    def _guard(self) -> None:
        if config.AI_MODE == "disabled":
            raise ModelUnavailable(self.record.model_id, "AI_MODE=disabled")
        if config.AI_MODE == "remote":
            raise ModelUnavailable(self.record.model_id, "remote worker endpoint not configured")
        if not _deps_available():
            raise ModelUnavailable(self.record.model_id, "torch/transformers not installed")

    def health(self) -> dict:
        try:
            self._guard()
            status = "ready" if self._pipeline is not None else "loadable"
        except ModelUnavailable as exc:
            status = f"unavailable: {exc.reason}"
        return {
            "model_id": self.record.model_id,
            "hf_repo": self.record.hf_repo,
            "license": self.record.license,
            "status": status,
            "accelerator": _accelerator_status() if config.AI_MODE == "local" else "n/a",
        }


class QwenVLAnalyzer(_LocalBase):
    """Qwen3-VL-8B-Instruct visual analysis (Apache-2.0)."""

    def __init__(self):
        super().__init__(config.VISUAL_MODEL)

    def analyze(self, image_bytes: bytes, instruction: str) -> dict:
        self._guard()
        import io
        import json

        from PIL import Image

        if self._pipeline is None:
            from transformers import AutoModelForImageTextToText, AutoProcessor

            processor = AutoProcessor.from_pretrained(self.record.hf_repo)
            model = AutoModelForImageTextToText.from_pretrained(
                self.record.hf_repo, device_map="auto"
            )
            self._pipeline = (processor, model)
        processor, model = self._pipeline
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": instruction},
                ],
            }
        ]
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
        output = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
        text = processor.batch_decode(
            output[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )[0]
        # Strict JSON contract: the caller validates against the DesignDNA
        # schema; a non-JSON answer is a hard failure, never silently used.
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("VLM did not return JSON")
        return json.loads(text[start:end + 1])


class QwenImageEditor(_LocalBase):
    """Qwen-Image-Edit (Apache-2.0) — visualization only, never geometry."""

    def __init__(self):
        super().__init__(config.IMAGE_MODEL)

    def edit(self, image_bytes: bytes, prompt: str, mask_bytes: bytes | None = None) -> bytes:
        self._guard()
        if not _diffusers_available():
            raise ModelUnavailable(self.record.model_id, "diffusers not installed")
        import io

        from PIL import Image

        if self._pipeline is None:
            from diffusers import QwenImageEditPipeline

            self._pipeline = QwenImageEditPipeline.from_pretrained(self.record.hf_repo)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        result = self._pipeline(image=image, prompt=prompt).images[0]
        out = io.BytesIO()
        result.save(out, format="PNG")
        return out.getvalue()

    generate = None  # not a text-to-image provider


class _DiffusersT2I(_LocalBase):
    def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> bytes:
        self._guard()
        if not _diffusers_available():
            raise ModelUnavailable(self.record.model_id, "diffusers not installed")
        import io

        if self._pipeline is None:
            from diffusers import DiffusionPipeline

            self._pipeline = DiffusionPipeline.from_pretrained(self.record.hf_repo)
        image = self._pipeline(prompt=prompt, width=width, height=height).images[0]
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()


class QwenImageGenerator(_DiffusersT2I):
    def __init__(self):
        super().__init__(config.T2I_MODEL)


class FluxSchnellGenerator(_DiffusersT2I):
    """Fallback for generic concepts/backgrounds/lifestyle ONLY — never an
    authoritative Arabic renderer."""

    def __init__(self):
        super().__init__(config.FALLBACK_IMAGE_MODEL)


def get_visual_analyzer() -> VisualAnalyzer:
    return QwenVLAnalyzer()


def get_image_editor() -> ImageEditor:
    return QwenImageEditor()


def get_image_generator(prefer_fallback: bool = False) -> ImageGenerator:
    return FluxSchnellGenerator() if prefer_fallback else QwenImageGenerator()


def ai_status() -> dict:
    """Honest status of every registered model in this deployment."""
    providers = {
        "visual_analyzer": QwenVLAnalyzer().health(),
        "image_editor": QwenImageEditor().health(),
        "text_to_image": QwenImageGenerator().health(),
        "fallback_image": FluxSchnellGenerator().health(),
    }
    return {
        "ai_mode": config.AI_MODE,
        "allow_paid_providers": config.ALLOW_PAID_PROVIDERS,
        "providers": providers,
        "deterministic_golden_path": "always available (independent of AI)",
    }
