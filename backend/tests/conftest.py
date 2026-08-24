import pytest

from app.config import DEFAULT_RULES
from app.schemas.jewellery_design import ImmutableSourceText

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
