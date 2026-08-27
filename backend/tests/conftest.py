import os

# Integration tests run against a real PostgreSQL test database (behavioral
# parity with production; SQLite is not used). Set before app imports.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/beyondstyle_test",
)

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text

from app.config import DEFAULT_RULES
from app.db.base import reset_engine, session_factory
from app.schemas.jewellery_design import ImmutableSourceText

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def migrated_db():
    """Fresh schema via real Alembic migrations (up from base) per test session."""
    cfg = AlembicConfig(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    reset_engine()
    yield cfg


@pytest.fixture
def db_session(migrated_db):
    session = session_factory()()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def clean_tables(migrated_db):
    """Truncate mutable state between tests that need isolation
    (session_replication_role bypasses append-only audit triggers —
    superuser-only, test database use)."""
    session = session_factory()()
    session.execute(text("SET session_replication_role = replica"))
    for table in [
        "design_reviews", "customer_validation_responses",
        "exports", "manufacturing_validation_runs", "design_events",
        "customer_approvals", "design_versions", "designs",
        "design_candidates", "font_references", "design_requests",
    ]:
        session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    session.execute(text("SET session_replication_role = DEFAULT"))
    session.commit()
    session.close()

# Golden dataset: difficult Arabic cases + English + mixed forms.
GOLDEN_NAMES = [
    "ميثة",       # Taa Marbuta
    "مريم",
    "محمد",
    "لؤي",        # Hamza on Waw
    "رؤى",        # Hamza on Waw + Alif Maqsura
    "يحيى",       # Alif Maqsura
    "عبد الرحمن",  # multi-word
    "ما شاء الله", # phrase w/ Lam-Alif and Allah ligature contexts
    "Amal",
    "Basma",
]

ARABIC_NAMES = [n for n in GOLDEN_NAMES if any("؀" <= c <= "ۿ" for c in n)]


@pytest.fixture(scope="session")
def rules():
    return DEFAULT_RULES


@pytest.fixture
def source_factory():
    def make(text: str, confirmed: bool = True) -> ImmutableSourceText:
        return ImmutableSourceText.create(text, confirmed=confirmed)

    return make
