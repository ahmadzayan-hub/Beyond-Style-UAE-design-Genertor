"""Variable-font instances — one source of truth for shaping AND outlines.

The failure this module exists to prevent: shaping a run at one set of
variation coordinates while extracting outlines at another. That produces
glyph positions from one weight and glyph shapes from a different one, and
the result looks plausible while being geometrically wrong.

So both consumers ask THIS module for their handle, keyed by the same
`(font_id, axes)` pair. `FontInstance.key` is what goes into the design
identity hash, so a coordinate change is a different design, never a silent
in-place mutation of an approved one.

Axis values are validated against the font's real fvar table and, where a
product is named, against the geometry-verified safe range. Invalid values
raise `AxisValueOutOfRange` — they are never silently clamped.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from .registry import get_registry


class AxisValueOutOfRange(ValueError):
    """Structured refusal — carries the machine-readable error code."""

    code = "AXIS_VALUE_OUT_OF_RANGE"

    def __init__(self, message: str, detail: dict):
        super().__init__(message)
        self.detail = {"code": self.code, **detail}


class UnsupportedAxis(ValueError):
    code = "UNSUPPORTED_AXIS"

    def __init__(self, message: str, detail: dict):
        super().__init__(message)
        self.detail = {"code": self.code, **detail}


def normalize_axes(axes: dict | None) -> tuple[tuple[str, float], ...]:
    """Canonical, hashable, order-independent axis form."""
    if not axes:
        return ()
    return tuple(sorted((str(k), float(v)) for k, v in axes.items()))


@lru_cache(maxsize=32)
def font_axis_specs(font_id: str) -> dict[str, dict]:
    """The font's real fvar axes. Empty for a static font."""
    record = get_registry().get(font_id)
    tt = TTFont(record.path, lazy=True)
    if "fvar" not in tt:
        return {}
    return {
        a.axisTag: {"tag": a.axisTag, "min": float(a.minValue),
                    "default": float(a.defaultValue), "max": float(a.maxValue)}
        for a in tt["fvar"].axes
    }


def validate_axes(font_id: str, axes: dict | None, product: str | None = None) -> dict:
    """Validate requested coordinates. Raises rather than clamping.

    Three gates in order: the axis must exist in this font, the value must
    sit inside the font's own min/max, and — when a product is named and a
    geometry-verified range exists — inside that product's safe range."""
    if not axes:
        return {}
    specs = font_axis_specs(font_id)
    checked: dict[str, float] = {}
    for tag, raw in axes.items():
        if tag not in specs:
            raise UnsupportedAxis(
                f"Font '{font_id}' has no '{tag}' axis.",
                {"font_id": font_id, "axis": tag, "available_axes": sorted(specs)},
            )
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise AxisValueOutOfRange(
                f"Axis '{tag}' value must be numeric.",
                {"font_id": font_id, "axis": tag, "value": raw},
            )
        spec = specs[tag]
        if not (spec["min"] <= value <= spec["max"]):
            raise AxisValueOutOfRange(
                f"Axis '{tag}'={value} is outside the font range "
                f"{spec['min']}–{spec['max']}.",
                {"font_id": font_id, "axis": tag, "value": value,
                 "font_min": spec["min"], "font_max": spec["max"]},
            )
        if product:
            safe = product_safe_range(font_id, tag, product)
            if safe and safe.get("min") is not None and not (safe["min"] <= value <= safe["max"]):
                raise AxisValueOutOfRange(
                    f"Axis '{tag}'={value} is outside the geometry-verified safe range "
                    f"{safe['min']}–{safe['max']} for {product}.",
                    {"font_id": font_id, "axis": tag, "value": value, "product": product,
                     "safe_min": safe["min"], "safe_max": safe["max"],
                     "evidence_level": safe.get("evidence_level")},
                )
        checked[tag] = value
    return checked


def product_safe_range(font_id: str, axis: str, product: str) -> dict | None:
    """Geometry-verified safe range for one (font, axis, product), or None
    when it has not been tested. An untested combination is never treated
    as safe — callers decide, but they are told it is NOT_TESTED."""
    from .curation import load_curation

    ranges = load_curation().get("product_axis_ranges", {})
    return ranges.get(font_id, {}).get(axis, {}).get(product)


@dataclass(frozen=True)
class FontInstance:
    """A font at specific variation coordinates. `key` is identity."""

    font_id: str
    path: str
    axes: tuple[tuple[str, float], ...]

    @property
    def key(self) -> str:
        if not self.axes:
            return self.font_id
        coords = ",".join(f"{t}={v:g}" for t, v in self.axes)
        return f"{self.font_id}[{coords}]"

    @property
    def axes_dict(self) -> dict[str, float]:
        return {t: v for t, v in self.axes}


def get_instance(font_id: str, axes: dict | None = None, product: str | None = None) -> FontInstance:
    record = get_registry().get(font_id)
    validated = validate_axes(font_id, axes, product)
    return FontInstance(font_id=font_id, path=str(record.path),
                        axes=normalize_axes(validated))


@lru_cache(maxsize=16)
def _instanced_bytes(font_path: str, axes: tuple[tuple[str, float], ...]) -> bytes:
    """The variable font frozen at these coordinates, as real font bytes.

    Both HarfBuzz and fontTools are built from THESE bytes, so shaping and
    outline extraction cannot drift apart."""
    tt = TTFont(font_path)
    static = instancer.instantiateVariableFont(tt, dict(axes), inplace=False)
    buf = io.BytesIO()
    static.save(buf)
    return buf.getvalue()


@lru_cache(maxsize=16)
def hb_font_for(instance: FontInstance) -> hb.Font:
    """HarfBuzz font at the instance's coordinates."""
    if not instance.axes:
        blob = hb.Blob.from_file_path(instance.path)
        return hb.Font(hb.Face(blob))
    blob = hb.Blob(_instanced_bytes(instance.path, instance.axes))
    font = hb.Font(hb.Face(blob))
    # Belt and braces: the bytes are already instanced, but setting the
    # coordinates too means a partially-instanced font still shapes right.
    font.set_variations(instance.axes_dict)
    return font


@lru_cache(maxsize=16)
def glyphset_for(instance: FontInstance):
    """fontTools glyph set + order at the SAME coordinates."""
    if not instance.axes:
        tt = TTFont(instance.path, lazy=True)
    else:
        tt = TTFont(io.BytesIO(_instanced_bytes(instance.path, instance.axes)), lazy=True)
    return tt.getGlyphSet(), tt.getGlyphOrder()
