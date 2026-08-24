"""SVG and DXF export validity: structure, mm units, metadata, blocking."""
import io
import json
import xml.etree.ElementTree as ET

import ezdxf
import pytest

from app.engines.generator import generate_candidates
from app.exporters.dxf_exporter import ProductionExportBlocked, export_dxf
from app.exporters.svg_exporter import export_svg


@pytest.fixture(scope="module")
def candidate_and_source(rules_module=None):
    from app.config import DEFAULT_RULES
    from app.schemas.jewellery_design import ImmutableSourceText

    src = ImmutableSourceText.create("ميثة", confirmed=True)
    _, top = generate_candidates("d-exp", src, DEFAULT_RULES)
    assert top
    return top[0], src


def test_svg_structure_and_mm_units(candidate_and_source):
    cand, src = candidate_and_source
    svg = export_svg(cand, src)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.attrib["width"].endswith("mm")
    assert root.attrib["height"].endswith("mm")
    # viewBox matches mm numbers in width/height.
    w = float(root.attrib["width"][:-2])
    vb = [float(x) for x in root.attrib["viewBox"].split()]
    assert vb[2] == w
    ns = "{http://www.w3.org/2000/svg}"
    path = root.find(f"{ns}path")
    assert path is not None and path.attrib["d"].startswith("M")
    assert path.attrib["fill-rule"] == "evenodd"
    # No raster elements.
    assert root.find(f"{ns}image") is None


def test_svg_metadata_traceability(candidate_and_source):
    cand, src = candidate_and_source
    svg = export_svg(cand, src)
    root = ET.fromstring(svg)
    meta = json.loads(root.find("{http://www.w3.org/2000/svg}metadata").text)
    assert meta["source_text"] == src.normalized_text
    assert meta["source_text_sha256"] == src.sha256
    assert meta["candidate_id"] == cand.candidate_id
    assert meta["units"] == "mm"
    assert meta["production_export_allowed"] is True


def test_svg_dimensions_match_features(candidate_and_source):
    cand, src = candidate_and_source
    root = ET.fromstring(export_svg(cand, src))
    w = float(root.attrib["width"][:-2])
    # margin of 1mm each side
    assert w == pytest.approx(cand.features.width_mm + 2.0, abs=0.01)


def test_dxf_machine_validity_mm_units(candidate_and_source):
    cand, src = candidate_and_source
    dxf_text = export_dxf(cand, src)
    doc = ezdxf.read(io.StringIO(dxf_text))
    assert doc.header["$INSUNITS"] == 4  # millimetres
    assert doc.header["$MEASUREMENT"] == 1
    msp = doc.modelspace()
    polylines = list(msp.query("LWPOLYLINE"))
    assert polylines, "no polylines in DXF"
    for pl in polylines:
        assert pl.closed, "open polyline in cut file"
        assert pl.dxf.layer in ("CUT", "HOLES")
    # Extents match candidate mm dimensions.
    xs, ys = [], []
    for pl in polylines:
        for x, y, *_ in pl.get_points():
            xs.append(x)
            ys.append(y)
    assert max(xs) - min(xs) == pytest.approx(cand.features.width_mm, abs=0.05)
    assert max(ys) - min(ys) == pytest.approx(cand.features.height_mm, abs=0.05)


def test_dxf_metadata_traceability(candidate_and_source):
    cand, src = candidate_and_source
    doc = ezdxf.read(io.StringIO(export_dxf(cand, src)))
    cv = dict(doc.header.custom_vars)
    assert cv["SOURCE_TEXT_SHA256"] == src.sha256
    assert cv["CANDIDATE_ID"] == cand.candidate_id
    assert cv["UNITS"] == "mm"


def test_dxf_blocked_for_failed_validation(candidate_and_source):
    from app.config import DEFAULT_RULES
    from app.schemas.jewellery_design import ImmutableSourceText

    src = ImmutableSourceText.create("ميثة", confirmed=True)
    all_c, _ = generate_candidates("d-blk", src, DEFAULT_RULES)
    failed = [c for c in all_c if c.validation and not c.validation.passed]
    assert failed, "expected at least one blocked candidate in pool"
    with pytest.raises(ProductionExportBlocked):
        export_dxf(failed[0], src)


def test_dxf_blocked_for_unconfirmed_text(candidate_and_source):
    cand, _ = candidate_and_source
    from app.schemas.jewellery_design import ImmutableSourceText

    unconfirmed = ImmutableSourceText.create("ميثة", confirmed=False)
    with pytest.raises(ProductionExportBlocked):
        export_dxf(cand, unconfirmed)
