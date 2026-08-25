"""Production readiness checks — GET /ready.

/health only proves the process is alive; /ready proves the Golden
Path can actually run: DB reachable, migrations at head, font
registry loaded, Arabic shaping engine functional, geometry/validator
importable and callable, private storage writable, generator wired.
Every check reports a component status without leaking secrets or
internal paths beyond what's already public (e.g. font ids).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_database(session: Session) -> dict:
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_migrations() -> dict:
    try:
        import os

        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        from .config import DATABASE_URL
        from .db.base import get_engine

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        with get_engine().connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        if current == head:
            return {"status": "ok", "revision": current}
        return {"status": "error", "current": current, "head": head}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_font_registry() -> dict:
    try:
        from .fonts.registry import get_registry

        fonts = get_registry().list()
        return {"status": "ok" if fonts else "error", "font_count": len(fonts)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_arabic_engine() -> dict:
    try:
        from .engines.arabic_engine import shape_text, verify_identity

        runs = shape_text("ميثة", "amiri-regular")
        proof = verify_identity("ميثة", runs)
        return {"status": "ok" if proof.verified else "error"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_geometry_and_manufacturing() -> dict:
    try:
        from .config import DEFAULT_RULES
        from .engines.generator import build_geometry_for_recipe
        from .schemas.jewellery_design import RecipeParams

        recipe = RecipeParams(recipe_id="readiness-probe", name="probe", font_id="amiri-regular",
                              composition="bare")
        _runs, proof, built = build_geometry_for_recipe("م", recipe, DEFAULT_RULES)
        return {"status": "ok" if not built.geometry.is_empty else "error"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_storage() -> dict:
    try:
        from .security.uploads import get_storage

        storage = get_storage()
        key = storage.put(b"readiness-probe", ".txt")
        ok = storage.get(key) == b"readiness-probe"
        return {"status": "ok" if ok else "error"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def check_generator() -> dict:
    try:
        from .engines.generator import load_recipe_library

        library = load_recipe_library()
        return {"status": "ok" if library else "error", "recipe_count": len(library)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": type(exc).__name__}


def readiness_report(session: Session) -> dict:
    components = {
        "database": check_database(session),
        "migrations": check_migrations(),
        "font_registry": check_font_registry(),
        "arabic_shaping_engine": check_arabic_engine(),
        "geometry_and_manufacturing_engine": check_geometry_and_manufacturing(),
        "storage": check_storage(),
        "design_generator": check_generator(),
    }
    overall_ok = all(c["status"] == "ok" for c in components.values())
    return {"status": "ready" if overall_ok else "not_ready", "components": components}
