"""VisualBrief + centralized VisualPromptBuilder.

Every image generation is described by a machine-readable VisualBrief
that is stored with the generation. Prompts are built in ONE place —
never ad hoc across the app — and always carry the preservation rule
that the supplied canonical geometry is authoritative.
"""
from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, Field

MATERIALS = {
    "silver-925": "polished 925 sterling silver",
    "gold-18k-yellow": "18K yellow gold",
    "gold-18k-rose": "18K rose gold",
    "gold-18k-white": "18K white gold",
    "platinum": "platinum",
    "two-tone": "two-tone yellow gold and white gold",
    "enamel": "gold with coloured enamel inlay",
}
FINISHES = {"polished": "high-polish mirror finish", "matte": "soft matte finish",
            "brushed": "brushed satin finish", "hammered": "lightly hammered texture"}
SCENES = {
    "clean_design": ("neutral light-grey studio background, flat-lay, no props",
                     "soft even diffused light", "straight-on macro, centred"),
    "studio_white": ("pure white seamless e-commerce background",
                     "bright soft box lighting, subtle contact shadow", "3/4 product angle"),
    "luxury_black": ("black velvet surface, dark luxury mood",
                     "dramatic single-source key light with warm rim", "low 3/4 angle"),
    "beyond_style_gold": ("warm cream backdrop with subtle gold gradient (Beyond Style UAE look)",
                          "warm directional light, gentle gold reflections", "elegant 3/4 angle"),
    "on_body_neck": ("worn on a neck, elegant neckline, plain clothing",
                     "soft natural window light", "portrait crop from collarbone up"),
    "on_body_ear": ("worn on an ear, hair tucked back", "soft natural light", "profile crop"),
    "on_body_hand": ("worn on a hand, relaxed pose", "soft natural light", "close hand crop"),
    "on_body_wrist": ("worn on a wrist", "soft natural light", "close wrist crop"),
    "packaging": ("inside a premium jewellery box on a neutral surface",
                  "soft boutique lighting", "3/4 angle"),
    "macro_detail": ("neutral background, extreme close detail of the surface and edges",
                     "raking light revealing texture", "macro"),
}
STONES = {"none", "diamond", "zircon", "emerald", "ruby", "sapphire", "birthstone", "pearl",
          "turquoise", "enamel"}
QUALITY_MODES = {"DRAFT", "STANDARD", "FINAL"}


class VisualBrief(BaseModel):
    """Stored with every generation; also the cache key input."""

    product_type: str = "pendant"
    source_text_hash: str
    design_version_id: str
    geometry_hash: str
    material: str = "silver-925"
    finish: str = "polished"
    stones: list[str] = Field(default_factory=list)
    orientation: str = "front"
    dimensions_mm: dict = Field(default_factory=dict)
    scene: str = "clean_design"
    camera: str = ""
    lighting: str = ""
    style: str = "premium jewellery product photography"
    quality: str = "DRAFT"
    preserve_geometry: bool = True

    def cache_key(self) -> str:
        """Identical brief + geometry ⇒ identical key ⇒ no repeat paid call."""
        payload = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


PRESERVATION_RULE = (
    "The supplied jewellery geometry is authoritative. Preserve the exact shape, "
    "proportions and arrangement of the supplied design, including every letter "
    "form, dot, gap, opening, bridge and attachment loop. Do not rewrite, "
    "reinterpret, translate, add, remove, straighten or alter any Arabic or Latin "
    "characters. Do not add text of any kind."
)
NEGATIVE_CONSTRAINTS = (
    "No added or altered lettering, no extra names, no watermark, no logo, no brand "
    "marks, no text overlays, no duplicated pendant, no distorted or mirrored script, "
    "no invented ornaments that change the silhouette."
)


class VisualPromptBuilder:
    """The single place where image prompts are constructed."""

    @staticmethod
    def build(brief: VisualBrief, reference_style_dna: dict | None = None) -> str:
        material = MATERIALS.get(brief.material, brief.material)
        finish = FINISHES.get(brief.finish, brief.finish)
        scene, lighting, camera = SCENES.get(brief.scene, SCENES["clean_design"])
        lighting = brief.lighting or lighting
        camera = brief.camera or camera
        stones = [s for s in brief.stones if s and s != "none"]
        stone_line = (
            f"Set stones exactly where the supplied design already provides seats: {', '.join(stones)}."
            if stones else "No stones; keep all surfaces plain metal."
        )
        dims = brief.dimensions_mm or {}
        dim_line = (
            f"Real size approximately {dims.get('width_mm', '?')}mm × {dims.get('height_mm', '?')}mm."
            if dims else ""
        )
        style_line = ""
        if reference_style_dna:
            keep = {k: v for k, v in reference_style_dna.items()
                    if k in ("composition", "construction", "ornament", "metal_color") and v not in (None, "unknown")}
            if keep:
                style_line = (
                    "Reference style cues (mood only, never copy any referenced artwork): "
                    + ", ".join(f"{k}={v}" for k, v in keep.items())
                    + "."
                )
        return "\n".join(
            [
                "CANONICAL DESIGN: Render the supplied jewellery design image as a real physical piece.",
                f"PRODUCT: {brief.product_type}. {dim_line}".strip(),
                f"MATERIAL: {material}, {finish}. {stone_line}",
                "CONSTRUCTION: real jewellery with believable thickness, edges and attachment hardware.",
                f"SCENE: {scene}.",
                f"LIGHTING: {lighting}.",
                f"CAMERA: {camera}. Orientation: {brief.orientation}.",
                f"STYLE: {brief.style}.",
                style_line,
                f"PRESERVATION RULES: {PRESERVATION_RULE}",
                f"NEGATIVE CONSTRAINTS: {NEGATIVE_CONSTRAINTS}",
            ]
        ).replace("\n\n", "\n").strip()
