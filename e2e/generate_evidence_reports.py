"""CI-friendly evidence: diversity/dedup/manufacturing report + HTML proof
sheets for the acceptance cases (no browser needed; PNG screenshots are
produced separately by generate_proof_sheets.py where chromium exists)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import diversity_score, generate_candidates  # noqa: E402
from app.engines.similarity import NEAR_DUP_IOU, hex_to_grid, iou  # noqa: E402
from app.exporters.svg_exporter import export_proof_svg  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText  # noqa: E402

CASES = {
    "ميثة": "maitha",
    "نورة": "noura",
    "محمد": "mohammed",
    "حامد محمد سلطان ميثة حمد خالد مهرة": "seven-names",
    "سلام هي حتى مطلع الفجر": "phrase-fajr",
}
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

report = {}
failed = False
for text, slug in CASES.items():
    src = ImmutableSourceText.create(text, confirmed=True)
    _, top = generate_candidates("d-evidence", src, DEFAULT_RULES)
    grids = [hex_to_grid(c.features.occupancy_hex) for c in top]
    max_iou = max(
        (iou(grids[i], grids[j]) for i in range(len(grids)) for j in range(i + 1, len(grids))),
        default=0.0,
    )
    stylistic = sorted(
        {f"dot:{c.recipe.dot_style}" for c in top if c.recipe.dot_style != "round"}
        | {f"swash:{c.recipe.swash}" for c in top if c.recipe.swash != "none"}
        | {f"kashida:{c.recipe.kashida_count}" for c in top if c.recipe.kashida_count}
        | {f"lines:{c.recipe.max_lines}" for c in top if c.recipe.max_lines > 1 and " " in text}
    )
    entry = {
        "top_count": len(top),
        # Multi-name pieces (ADR-0006) carry their family in the layout —
        # every composition-engine candidate shares the "multi_name" class.
        "composition_families": sorted({
            (f"multi_name:{c.recipe.multi_name['layout']}" if c.recipe.multi_name else c.recipe.composition)
            for c in top
        }),
        "dna_families": sorted({c.recipe.dna["family"] for c in top if c.recipe.dna}),
        "stylistic_families": stylistic,
        "fonts": sorted({c.recipe.font_id for c in top}),
        "max_pairwise_perceptual_iou": round(max_iou, 3),
        "near_dup_gate": NEAR_DUP_IOU,
        "feature_diversity_min_pairwise": diversity_score(top),
        "all_manufacturing_pass": all(c.validation.passed for c in top),
        "all_identity_verified": all(c.identity_proof.verified for c in top),
    }
    report[text] = entry
    ok = (
        entry["top_count"] == 10
        and len(entry["composition_families"]) >= 4
        and len(entry["stylistic_families"]) >= 2
        and entry["max_pairwise_perceptual_iou"] < NEAR_DUP_IOU
        and entry["all_manufacturing_pass"]
        and entry["all_identity_verified"]
    )
    if slug == "seven-names" and len(entry["composition_families"]) >= 3:
        ok = entry["top_count"] == 10 and entry["all_manufacturing_pass"] and entry["all_identity_verified"]
    entry["acceptance_pass"] = ok
    failed = failed or not ok

    cards = "".join(
        f'<div class="card"><div class="svgbox">{export_proof_svg(c, src)}</div>'
        f'<p class="t">{c.diversity_rank}. {c.recipe.name}</p>'
        f'<p class="s">{c.recipe.composition} · {c.recipe.font_id} · '
        f'{c.features.width_mm:.0f}×{c.features.height_mm:.0f}mm</p></div>'
        for c in top
    )
    (EVIDENCE / f"proof-sheet-{slug}.html").write_text(
        '<html dir="rtl"><head><meta charset="utf-8"><style>'
        "body{font-family:sans-serif;background:#faf7f1;padding:16px}"
        ".grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}"
        ".card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px}"
        ".svgbox{display:flex;align-items:center;justify-content:center;min-height:130px}"
        ".svgbox svg{max-width:100%;height:auto;max-height:130px}"
        ".t{font-size:12px;font-weight:700;margin:6px 0 0}.s{font-size:10px;color:#666}"
        f"</style></head><body><h2>{text}</h2><div class=\"grid\">{cards}</div></body></html>"
    )
    print(slug, "PASS" if ok else "FAIL", entry["composition_families"], entry["stylistic_families"][:4])

(EVIDENCE / "diversity-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
sys.exit(1 if failed else 0)
