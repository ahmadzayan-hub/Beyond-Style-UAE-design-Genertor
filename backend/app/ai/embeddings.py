"""Embeddings for DesignDNA retrieval.

Deterministic DNA encoder (FALLBACK, always available): one-hot/scalar
encoding of the structured DesignDNA — honest, reproducible, no model.
A visual EmbeddingProvider slot exists for a real image encoder when a
model is deployed. Retrieval interface is pgvector-shaped: cosine
similarity over stored vectors; a Python implementation backs it until
the pgvector extension is installed on the database host.
"""
from __future__ import annotations

from .design_dna import COMPOSITIONS, DesignDNA, PRODUCT_TYPES, SCRIPT_FAMILIES

ENCODER_VERSION = "dna-onehot-1"


def _onehot(value: str, vocab: list[str]) -> list[float]:
    return [1.0 if value == v else 0.0 for v in vocab]


def encode_dna(dna: DesignDNA) -> list[float]:
    """Deterministic DNA embedding (labelled FALLBACK encoder)."""
    vec: list[float] = []
    vec += _onehot(dna.product_type, PRODUCT_TYPES)
    vec += _onehot(dna.script_family, SCRIPT_FAMILIES)
    vec += _onehot(dna.composition, COMPOSITIONS)
    vec += [
        {"openwork": 0.0, "plate": 0.5, "relief": 0.75, "engraving": 1.0}.get(dna.construction, 0.25),
        dna.luxury_score,
        dna.minimal_score,
        dna.heritage_score,
        dna.modern_score,
        dna.reference_confidence,
        (dna.aspect_ratio or 1.5) / 5.0,
        {"low": 0.2, "medium": 0.5, "high": 0.9}.get(dna.manufacturing_complexity, 0.5),
    ]
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def rank_by_similarity(query: list[float], rows: list[tuple[str, list[float]]], top_k: int = 5):
    """rows: (id, embedding). Returns [(id, similarity)] best-first.
    Same contract as a pgvector `ORDER BY embedding <=> query` — swap the
    backend when the extension is available."""
    scored = [(rid, cosine(query, emb)) for rid, emb in rows]
    return sorted(scored, key=lambda t: (-t[1], t[0]))[:top_k]
