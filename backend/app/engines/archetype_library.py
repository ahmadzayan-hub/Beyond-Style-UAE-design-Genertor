"""Structured archetype catalogue + Design-DNA retrieval.

Coverage (assessment risk #6): the curated library holds 40 design recipes
and 6 script recipes, each hand-tuned with a distinct visual purpose. This
module widens the catalogue to ≥150 *structured* archetypes by deriving
constructions from a deterministic matrix over the proven parameter
vocabulary (composition × dot style × swash × kashida) on top of each
font's curated base. Every derived archetype is labelled
``UNCURATED_PARAMETRIC`` — it inherits its manufacturing parameters from a
curated base and still passes through the same Arabic/manufacturing QA as
any candidate, but no designer has reviewed it as a look. Nothing here is
an artwork copy: only Beyond Style parametric constructions.

Retrieval follows the CLAUDE.md rule "retrieve with metadata + pgvector;
never send the whole library": a brief/reference is encoded into the same
DNA vector space as the archetypes, filtered by product and text length,
ranked by cosine similarity, and only the top-k enter the candidate pool.
The encoder is the deterministic DNA encoder (``app.ai.embeddings``) — a
Python cosine backs it until pgvector is installed on the database host,
and the provenance says so.

The default (hint-less) candidate pool is untouched, so the immutable
golden fixtures keep their candidate ids.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..ai.embeddings import cosine
from ..fonts.registry import get_registry
from ..schemas.jewellery_design import RecipeParams

CATALOGUE_VERSION = "archetypes-1.0"
RETRIEVAL_ENCODER = "archetype-dna-onehot-1 (python cosine; pgvector-shaped)"
CURATED = "CURATED"
UNCURATED = "UNCURATED_PARAMETRIC"
RIGHTS = "BEYOND_STYLE_ORIGINAL_PARAMETRIC"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DESIGN_RECIPES = DATA_DIR / "design_recipes.json"
SCRIPT_RECIPES = DATA_DIR / "script_recipes.json"

COMPOSITIONS = [
    "bare", "baseline_bar", "underline_bar", "plate_oval", "plate_rect",
    "frame_circle", "frame_rect", "top_bar",
]
DOT_STYLES = ["round", "diamond", "square", "petal"]
SWASHES = ["none", "underline_flourish", "tail_sweep", "double_flourish"]
LOOPS = ["none", "top", "left_right"]
SCRIPT_FAMILIES = ["naskh", "ruqaa", "kufi", "modern_arabic", "nastaliq"]
INFLUENCES = ["thuluth", "diwani", "kufi"]
#: Connected scripts where baseline elongation (kashida) is idiomatic.
KASHIDA_SCRIPTS = {"naskh", "ruqaa", "nastaliq"}

#: Products an archetype construction is sensible for (metadata filter).
PRODUCTS_BY_COMPOSITION = {
    "bare": ["pendant", "necklace", "bracelet", "earring"],
    "baseline_bar": ["pendant", "necklace", "bracelet"],
    "underline_bar": ["pendant", "necklace", "bracelet"],
    "plate_oval": ["pendant", "necklace", "keychain", "medallion"],
    "plate_rect": ["pendant", "necklace", "keychain", "cufflinks"],
    "frame_circle": ["pendant", "necklace", "medallion", "earring"],
    "frame_rect": ["pendant", "necklace", "keychain"],
    "top_bar": ["pendant", "necklace"],
}
VISUAL_PURPOSE = {
    "bare": "free silhouette",
    "baseline_bar": "connected nameplate on a baseline bar",
    "underline_bar": "nameplate with underline bar",
    "plate_oval": "oval plate relief",
    "plate_rect": "rectangular plate relief",
    "frame_circle": "circular openwork medallion",
    "frame_rect": "rectangular openwork frame",
    "top_bar": "suspended from a top bar",
}
#: DesignDNA script vocabulary → catalogue script family / influence.
DNA_SCRIPT_MAP = {
    "naskh": ("naskh", None), "ruqaa": ("ruqaa", None),
    "kufi": ("kufi", None), "geometric_kufi": ("kufi", None), "square_kufi": ("kufi", None),
    "farsi": ("nastaliq", None), "nastaliq": ("nastaliq", None),
    "modern_arabic": ("modern_arabic", None), "minimal": ("modern_arabic", None),
    "thuluth": ("naskh", "thuluth"), "thuluth_jali": ("naskh", "thuluth"),
    "diwani": ("naskh", "diwani"), "diwani_jali": ("naskh", "diwani"),
}
STYLE_INTENT_FAMILIES = {
    "minimal": {"kufi": 1.0, "modern_arabic": 1.0},
    "modern": {"kufi": 1.0, "modern_arabic": 0.8},
    "luxury": {"naskh": 1.0, "thuluth": 0.7, "diwani": 0.7},
    "traditional": {"naskh": 1.0, "ruqaa": 0.8},
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _curated(raw: dict, source: str) -> list[RecipeParams]:
    out = []
    for r in raw["recipes"]:
        dna = dict(r.get("dna") or {})
        dna.setdefault("rights", RIGHTS)
        dna["curation"] = CURATED
        dna["catalogue_source"] = source
        out.append(RecipeParams(**{**r, "dna": dna}))
    return out


def signature(r: RecipeParams) -> tuple:
    """Parameter identity used for de-duplication: two archetypes with the
    same signature would produce the same construction family."""
    return (
        r.font_id, r.composition, r.dot_style, r.swash, r.loops,
        r.ot_feature_set, r.kashida_count > 0, r.max_lines,
    )


def _derive(base: RecipeParams, *, composition: str, dot_style: str = "round",
            swash: str = "none", kashida: int = 0, script: str) -> RecipeParams:
    tag = ".".join(p for p in (
        composition, None if dot_style == "round" else dot_style,
        None if swash == "none" else swash, "kashida" if kashida else None) if p)
    purpose = VISUAL_PURPOSE[composition]
    if dot_style != "round":
        purpose += f", {dot_style} dots"
    if swash != "none":
        purpose += f", {swash.replace('_', ' ')}"
    if kashida:
        purpose += ", elongated baseline"
    return base.model_copy(update={
        "recipe_id": f"arch.{base.font_id}.{tag}",
        "name": f"{script} {purpose}",
        "composition": composition,
        "dot_style": dot_style,
        "swash": swash,
        "kashida_count": kashida,
        "ot_feature_set": "default",
        "max_lines": 1,
        "dna": {
            "family": f"{script}-{composition}",
            "visual_purpose": purpose,
            "products": PRODUCTS_BY_COMPOSITION[composition],
            "text_length_chars": [1, 14],
            "manufacturing_constraints": (base.dna or {}).get("manufacturing_constraints", {}),
            "rights": RIGHTS,
            "curation": UNCURATED,
            "derived_from": base.recipe_id,
            "catalogue_source": CATALOGUE_VERSION,
        },
    })


@lru_cache(maxsize=1)
def build_catalogue() -> tuple[RecipeParams, ...]:
    """Curated bases first (unchanged), then derived archetypes, de-duplicated
    by parameter signature. Deterministic: same inputs → same order."""
    curated = _curated(_load(DESIGN_RECIPES), "design_recipes.json") + \
        _curated(_load(SCRIPT_RECIPES), "script_recipes.json")
    seen = {signature(r) for r in curated}
    ids = {r.recipe_id for r in curated}
    registry = get_registry()
    out: list[RecipeParams] = list(curated)

    def add(r: RecipeParams) -> None:
        if signature(r) in seen or r.recipe_id in ids:
            return
        seen.add(signature(r))
        ids.add(r.recipe_id)
        out.append(r)

    fonts = sorted({r.font_id for r in curated})
    for font_id in fonts:
        record = registry.get(font_id)
        script = record.script_family
        bases = [r for r in curated if r.font_id == font_id and r.ring is None]
        base = min(bases, key=lambda r: (r.composition != "bare", r.max_lines, r.recipe_id))
        for comp in COMPOSITIONS:
            add(_derive(base, composition=comp, script=script))
        for dot in DOT_STYLES[1:]:
            add(_derive(base, composition="bare", dot_style=dot, script=script))
            add(_derive(base, composition="plate_rect", dot_style=dot, script=script))
        for sw in SWASHES[1:]:
            add(_derive(base, composition="bare", swash=sw, script=script))
            add(_derive(base, composition="underline_bar", swash=sw, script=script))
        if script in KASHIDA_SCRIPTS:
            add(_derive(base, composition="baseline_bar", kashida=2, script=script))
            add(_derive(base, composition="bare", kashida=2, script=script))
    return tuple(out)


def catalogue_summary() -> dict:
    cat = build_catalogue()
    return {
        "catalogue_version": CATALOGUE_VERSION,
        "total": len(cat),
        "curated": sum(1 for r in cat if (r.dna or {}).get("curation") == CURATED),
        "uncurated_parametric": sum(1 for r in cat if (r.dna or {}).get("curation") == UNCURATED),
        "fonts": sorted({r.font_id for r in cat}),
        "families": len({(r.dna or {}).get("family") for r in cat}),
    }


# ---------------------------------------------------------------- vectors

def _onehot(value, vocab: list[str]) -> list[float]:
    return [1.0 if value == v else 0.0 for v in vocab]


def _weights(weights: dict[str, float], vocab: list[str]) -> list[float]:
    return [float(weights.get(v, 0.0)) for v in vocab]


#: Script family is the strongest visual identity of a piece, so it
#: outweighs any single construction axis in the similarity space.
SCRIPT_WEIGHT = 2.0


def archetype_vector(r: RecipeParams) -> list[float]:
    record = get_registry().get(r.font_id)
    influence = getattr(record, "style_influence", None)
    return (
        [SCRIPT_WEIGHT * v for v in _onehot(record.script_family, SCRIPT_FAMILIES)]
        + [SCRIPT_WEIGHT * v for v in _onehot(influence, INFLUENCES)]
        + _onehot(r.composition, COMPOSITIONS)
        + _onehot(r.dot_style, DOT_STYLES)
        + _onehot(r.swash, SWASHES)
        + _onehot(r.loops, LOOPS)
        + [1.0 if r.kashida_count > 0 else 0.0, min(r.target_height_mm, 20.0) / 20.0,
           0.0 if r.ot_feature_set == "default" else 1.0]
    )


def query_vector(hints: dict) -> list[float] | None:
    """Brief/reference hints → DNA query in archetype space. Returns None
    when the hints carry no visual signal (no retrieval, pool unchanged)."""
    fam: dict[str, float] = {}
    infl: dict[str, float] = {}
    comp: dict[str, float] = {}
    dots: dict[str, float] = {}
    sw: dict[str, float] = {}
    kashida = 0.0
    for i, c in enumerate(hints.get("preferred_compositions") or []):
        if c in COMPOSITIONS:
            comp[c] = max(comp.get(c, 0.0), 1.0 / (i + 1))
    for name, w in STYLE_INTENT_FAMILIES.get(hints.get("style_intent") or "", {}).items():
        (infl if name in INFLUENCES else fam)[name] = w
    dna = hints.get("dna_fields") or {}
    mapped = DNA_SCRIPT_MAP.get(dna.get("script_family"))
    if mapped:
        fam[mapped[0]] = 1.0
        if mapped[1]:
            infl[mapped[1]] = 1.0
    if dna.get("dot_style") in DOT_STYLES:
        dots[dna["dot_style"]] = 1.0
    if hints.get("prefer_swash") or dna.get("swashes") in ("present", "expressive"):
        for s in SWASHES[1:]:
            sw[s] = 0.6
    if hints.get("prefer_kashida") or dna.get("kashida") in ("present", "strong"):
        kashida = 1.0
    if dna.get("construction") == "openwork":
        comp["bare"] = max(comp.get("bare", 0.0), 0.5)
        comp["frame_rect"] = max(comp.get("frame_rect", 0.0), 0.5)
    for rid in hints.get("preferred_recipes") or []:
        for r in build_catalogue():
            if r.recipe_id == rid:
                comp[r.composition] = max(comp.get(r.composition, 0.0), 0.5)
                fam[get_registry().get(r.font_id).script_family] = max(
                    fam.get(get_registry().get(r.font_id).script_family, 0.0), 0.5)
    vec = (
        [SCRIPT_WEIGHT * v for v in _weights(fam, SCRIPT_FAMILIES)]
        + [SCRIPT_WEIGHT * v for v in _weights(infl, INFLUENCES)]
        + _weights(comp, COMPOSITIONS)
        + _weights(dots, DOT_STYLES) + _weights(sw, SWASHES) + [0.0] * len(LOOPS)
        + [kashida, 0.0, 0.0]
    )
    return vec if any(vec) else None


def retrieve_archetypes(hints: dict | None, *, product_type: str | None = None,
                        text_length: int | None = None, k: int = 8,
                        exclude_ids: set[str] | frozenset[str] = frozenset()
                        ) -> tuple[list[RecipeParams], dict]:
    """Metadata filter + cosine ranking. Returns (recipes, provenance)."""
    provenance = {
        "catalogue_version": CATALOGUE_VERSION,
        "encoder": RETRIEVAL_ENCODER,
        "catalogue_size": len(build_catalogue()),
        "product_type": product_type,
        "text_length": text_length,
        "returned": [],
    }
    q = query_vector(hints or {})
    if q is None:
        provenance["basis"] = "NO_QUERY_SIGNAL"
        return [], provenance
    pool = []
    for r in build_catalogue():
        if r.recipe_id in exclude_ids or r.ring is not None:
            continue
        dna = r.dna or {}
        if product_type and product_type not in (dna.get("products") or []):
            continue
        lo, hi = (dna.get("text_length_chars") or [1, 14])
        if text_length is not None and not (lo <= text_length <= hi):
            continue
        pool.append(r)
    scored = sorted(
        ((round(cosine(q, archetype_vector(r)), 4), r) for r in pool),
        key=lambda t: (-t[0], t[1].recipe_id),
    )
    chosen = [r for s, r in scored[:k] if s > 0]
    provenance.update({
        "basis": "DNA_COSINE",
        "considered": len(pool),
        "returned": [r.recipe_id for r in chosen],
        "similarities": [s for s, _ in scored[:len(chosen)]],
        "curation": {r.recipe_id: (r.dna or {}).get("curation") for r in chosen},
    })
    return chosen, provenance
