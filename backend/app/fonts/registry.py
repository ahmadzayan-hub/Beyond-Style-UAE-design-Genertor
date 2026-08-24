"""Font registry with rights metadata.

Fonts are design *sources* for lettering, not final products. The registry
enforces the licensing gate: UNKNOWN_RIGHTS (and INTERNAL_ONLY for customer
deliverables) never reach commercial production export. Outline conversion
does not lift license obligations.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from ..schemas.jewellery_design import COMMERCIAL_OK, FontRightsStatus

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGISTRY_FILE = Path(__file__).resolve().parent / "fonts.json"


class FontRecord(BaseModel):
    font_id: str
    family: str
    style_family: str
    file: str
    license: str
    license_file: str
    source_url: str
    rights_status: FontRightsStatus
    redistribution_permitted: bool
    scripts: list[str]
    supports_harakat: bool
    notes: str = ""

    @property
    def path(self) -> Path:
        return ASSETS_DIR / self.file

    @property
    def commercial_production_allowed(self) -> bool:
        return self.rights_status in COMMERCIAL_OK

    @property
    def file_sha256(self) -> str:
        """Font binary hash — used as the font version stamp on versions."""
        import hashlib

        if not hasattr(self, "_file_sha256"):
            object.__setattr__(
                self, "_file_sha256", hashlib.sha256(self.path.read_bytes()).hexdigest()
            )
        return self._file_sha256


class FontRegistry:
    def __init__(self, registry_file: Path = REGISTRY_FILE):
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        self._fonts: dict[str, FontRecord] = {}
        for entry in data["fonts"]:
            record = FontRecord(**entry)
            if not record.path.is_file():
                raise FileNotFoundError(
                    f"Registered font binary missing: {record.path}"
                )
            if not (ASSETS_DIR / record.license_file).is_file():
                raise FileNotFoundError(
                    f"License file missing for {record.font_id}: {record.license_file}"
                )
            self._fonts[record.font_id] = record

    def get(self, font_id: str) -> FontRecord:
        if font_id not in self._fonts:
            raise KeyError(f"Unknown font_id: {font_id}")
        return self._fonts[font_id]

    def list(self) -> list[FontRecord]:
        return list(self._fonts.values())

    def assert_production_allowed(self, font_id: str) -> None:
        record = self.get(font_id)
        if not record.commercial_production_allowed:
            raise PermissionError(
                f"Font '{font_id}' has rights status {record.rights_status.value}; "
                "commercial production export is blocked."
            )


@lru_cache(maxsize=1)
def get_registry() -> FontRegistry:
    return FontRegistry()
