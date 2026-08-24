"""Candidate generation: count, determinism, diversity, traceability."""
import pytest

from app.engines.generator import (
    diversity_score,
    expand_recipes,
    generate_candidates,
)
from tests.conftest import GOLDEN_NAMES


def test_expansion_reaches_minimum():
    assert len(expand_recipes(30)) >= 30


def test_generation_counts_and_top10(rules, source_factory):
    src = source_factory("ميثة")
    all_c, top = generate_candidates("d-test", src, rules)
    assert len(all_c) >= 30
    valid = [c for c in all_c if c.validation and c.validation.passed]
    assert len(valid) >= 10, "not enough valid candidates to fill top 10"
    assert len(top) == 10


def test_generation_is_deterministic(rules, source_factory):
    src = source_factory("مريم")
    _, top1 = generate_candidates("d-det", src, rules)
    _, top2 = generate_candidates("d-det", src, rules)
    assert [c.candidate_id for c in top1] == [c.candidate_id for c in top2]
    assert [c.geometry_wkt for c in top1] == [c.geometry_wkt for c in top2]


def test_top10_geometric_diversity(rules, source_factory):
    src = source_factory("محمد")
    _, top = generate_candidates("d-div", src, rules)
    # No near-duplicates: minimum pairwise normalized feature distance.
    assert diversity_score(top) > 0.05
    # Structural spread: at least 2 fonts and 3 composition types in top 10.
    assert len({c.recipe.font_id for c in top}) >= 2
    assert len({c.recipe.composition for c in top}) >= 3


def test_all_candidates_trace_to_source_hash(rules, source_factory):
    src = source_factory("لؤي")
    all_c, _ = generate_candidates("d-trace", src, rules)
    for c in all_c:
        assert c.source_text_sha256 == src.sha256
        assert c.identity_proof.verified


def test_invalid_candidates_carry_block_evidence(rules, source_factory):
    src = source_factory("ميثة")
    all_c, _ = generate_candidates("d-block", src, rules)
    invalid = [c for c in all_c if c.validation and not c.validation.passed]
    for c in invalid:
        assert not c.validation.production_export_allowed
        assert c.validation.violations, "blocked candidate must state why"


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_every_golden_name_yields_valid_top10(rules, source_factory, name):
    src = source_factory(name)
    _, top = generate_candidates("d-gold", src, rules)
    assert len(top) == 10, f"{name}: only {len(top)} diverse valid candidates"
    for c in top:
        assert c.validation.passed
