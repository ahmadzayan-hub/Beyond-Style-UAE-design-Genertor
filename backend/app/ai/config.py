"""AI layer configuration. Zero hard dependency on external APIs or GPUs.

AI_MODE:
  local    — use local open-weight models (requirements-ai.txt + weights + GPU/CPU)
  remote   — reserved for a future remote worker/ComfyUI endpoint (same interfaces)
  disabled — deterministic Golden Path only (default; always fully functional)
"""
from __future__ import annotations

import os

AI_MODE = os.environ.get("AI_MODE", "disabled")
VISUAL_MODEL = os.environ.get("VISUAL_MODEL", "qwen3-vl")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "qwen-image-edit")
T2I_MODEL = os.environ.get("T2I_MODEL", "qwen-image")
FALLBACK_IMAGE_MODEL = os.environ.get("FALLBACK_IMAGE_MODEL", "flux-schnell")
ALLOW_PAID_PROVIDERS = os.environ.get("ALLOW_PAID_PROVIDERS", "false").lower() == "true"
LORA_TRAINING_ENABLED = os.environ.get("LORA_TRAINING_ENABLED", "false").lower() == "true"
AI_JOB_TIMEOUT_S = float(os.environ.get("AI_JOB_TIMEOUT_S", 120))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", 2))
#: Preview identity guard: max tolerated silhouette divergence (1 - IoU).
PREVIEW_IDENTITY_MAX_DIVERGENCE = float(os.environ.get("PREVIEW_IDENTITY_MAX_DIVERGENCE", 0.18))
