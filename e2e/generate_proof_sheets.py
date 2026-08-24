"""Generate Top-10 proof-sheet evidence for the quality-gate names.

Renders the real engine output (high-fidelity proof SVGs) into an HTML
sheet per name and screenshots it → docs/evidence/proof-sheet-<name>.png
plus a machine-readable diversity report.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import diversity_score, generate_candidates  # noqa: E402
from app.engines.similarity import hex_to_grid, iou  # noqa: E402
from app.exporters.svg_exporter import export_proof_svg  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText  # noqa: E402

NAMES = {"ميثة": "maitha", "نورة": "noura", "محمد": "mohammed", "Amal": "amal", "Basma": "basma"}
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

report = {}
sheets = []
for name, slug in NAMES.items():
    src = ImmutableSourceText.create(name, confirmed=True)
    _, top = generate_candidates("d-quality", src, DEFAULT_RULES)
    grids = [hex_to_grid(c.features.occupancy_hex) for c in top]
    max_iou = max(
        iou(grids[i], grids[j]) for i in range(len(grids)) for j in range(i + 1, len(grids))
    )
    report[name] = {
        "top_count": len(top),
        "max_pairwise_perceptual_iou": round(max_iou, 3),
        "feature_diversity_min_pairwise": diversity_score(top),
        "families": sorted({c.recipe.dna["family"] for c in top if c.recipe.dna}),
        "compositions": sorted({c.recipe.composition for c in top}),
        "fonts": sorted({c.recipe.font_id for c in top}),
        "all_manufacturing_pass": all(c.validation.passed for c in top),
    }
    cards = []
    for c in top:
        svg = export_proof_svg(c, src)
        q = c.quality_report
        cards.append(
            f'<div class="card"><div class="svgbox">{svg}</div>'
            f'<p class="t">{c.diversity_rank}. {c.recipe.name}</p>'
            f'<p class="s">{c.recipe.font_id} · {c.recipe.composition} · '
            f'{c.features.width_mm:.0f}×{c.features.height_mm:.0f}mm · '
            f'balance {q["visual_balance"]["value"]:.2f}</p></div>'
        )
    html = (
        '<html dir="rtl"><head><meta charset="utf-8"><style>'
        "body{font-family:sans-serif;background:#faf7f1;padding:16px}"
        ".grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}"
        ".card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px}"
        ".svgbox{display:flex;align-items:center;justify-content:center;min-height:120px}"
        ".svgbox svg{max-width:100%;height:auto;max-height:120px}"
        ".t{font-size:12px;font-weight:700;margin:6px 0 0}.s{font-size:10px;color:#666;margin:2px 0 0}"
        f"</style></head><body><h2>{name} — Top 10 (quality gate)</h2>"
        f'<div class="grid">{"".join(cards)}</div></body></html>'
    )
    path = EVIDENCE / f"proof-sheet-{slug}.html"
    path.write_text(html)
    sheets.append((slug, path))
    print(name, report[name]["max_pairwise_perceptual_iou"], report[name]["compositions"])

(EVIDENCE / "diversity-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

from playwright.sync_api import sync_playwright  # noqa: E402

exe = None
for cand in (
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
):
    if pathlib.Path(cand).is_file():
        exe = cand
        break
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=exe)
    page = browser.new_page(viewport={"width": 1400, "height": 800})
    for slug, path in sheets:
        page.goto(f"file://{path}")
        page.wait_for_timeout(300)
        page.screenshot(path=str(EVIDENCE / f"proof-sheet-{slug}.png"), full_page=True)
        path.unlink()  # keep PNG evidence only
    browser.close()
print("proof sheets written to", EVIDENCE)
