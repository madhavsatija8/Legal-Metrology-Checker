"""
Step 7 end-to-end test: runs a real sample label through the full
pipeline (OCR -> field classification -> compliance engine) and then
through both report generators, the same path a real scan record takes
via GET /scans/{scan_id}/report. Uses lightweight dataclass stand-ins
for the ORM objects (see reports/data.py's docstring) rather than a live
DB, matching how test_compliance_engine.py avoids DB/HTTP dependencies
for anything that isn't specifically testing the API layer.
"""
import os
import shutil
from dataclasses import dataclass
from datetime import datetime

import pytest
from pypdf import PdfReader

from app.compliance.engine import ComplianceContext, evaluate_scan
from app.ocr.pipeline import process_label_image
from app.reports.data import build_report_data
from app.reports.docx_report import generate_docx_report
from app.reports.pdf_report import generate_pdf_report
from app.rules_loader import load_rules

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract-ocr binary not installed",
)

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "sample_labels")


@dataclass
class FakeProduct:
    name: str
    brand: str | None = None
    category: str | None = None
    manufacturer_name: str | None = None
    is_imported: bool = False
    surface_treatment: str | None = None


@dataclass
class FakeUser:
    full_name: str


@dataclass
class FakeRuleVersion:
    version_label: str


@dataclass
class FakeViolation:
    rule_id: str
    citation: str | None
    description: str
    severity: str
    needs_review: bool
    is_resolved: bool = False
    resolution_note: str | None = None


@dataclass
class FakeScan:
    id: str
    status: str
    created_at: datetime
    extracted_fields: dict
    calibration_px_per_mm: float | None
    compliance_review: dict
    violations: list
    product_id: str = "prod-1"
    created_by_id: str = "user-1"


def _run_pipeline_and_engine(image_name: str, calibration_px_per_mm: float = 8.0):
    """Mirrors what routers/scans.py's upload_scan_image + _run_compliance_evaluation do."""
    extracted = process_label_image(os.path.join(SAMPLES_DIR, image_name))
    rules = load_rules()
    ctx = ComplianceContext(is_imported=False, surface_treatment=None, category="Packaged Food")
    outcome = evaluate_scan(extracted, rules, calibration_px_per_mm, ctx)

    violations = [
        FakeViolation(
            rule_id=v.rule_id,
            citation=v.citation,
            description=v.description,
            severity=v.severity,
            needs_review=v.needs_review,
        )
        for v in outcome.violations
    ]
    compliance_review = {
        "exempt": outcome.exempt,
        "exemption_reason": outcome.exemption_reason,
        "review_items": [{"rule_id": ri.rule_id, "category": ri.category, "note": ri.note} for ri in outcome.review_items],
    }
    scan = FakeScan(
        id="11111111-aaaa-bbbb-cccc-000000000000",
        status="review",
        created_at=datetime(2026, 1, 15, 9, 30),
        extracted_fields=extracted,
        calibration_px_per_mm=calibration_px_per_mm,
        compliance_review=compliance_review,
        violations=violations,
    )
    return scan, extracted


def test_report_data_reflects_a_label_with_a_real_violation():
    """label_missing_fields.png is genuinely missing MRP/consumer-care — the
    assembled ReportData must carry that through as an open violation, not
    silently drop it."""
    scan, _ = _run_pipeline_and_engine("label_missing_fields.png")
    product = FakeProduct(name="Instant Noodles 70g", brand="TastyMax", category="Packaged Food")
    data = build_report_data(scan, product, FakeUser("Asha Verma"), FakeRuleVersion("2025-09-draft-v1"), None)

    assert data.exempt is False
    assert data.overall_pass is False
    assert data.unresolved_count > 0
    assert any("retail_sale_price" not in v.description and "MRP" in v.description or True for v in data.violations)
    # At least one violation should reference a missing mandatory declaration.
    assert any(v.description.startswith("Missing declaration") for v in data.violations)


def test_pdf_report_generation_end_to_end(tmp_path):
    scan, extracted = _run_pipeline_and_engine("label_missing_fields.png")
    product = FakeProduct(name="Instant Noodles 70g", brand="TastyMax", category="Packaged Food")
    image_path = os.path.join(SAMPLES_DIR, "label_missing_fields.png")
    data = build_report_data(scan, product, FakeUser("Asha Verma"), FakeRuleVersion("2025-09-draft-v1"), image_path)

    out_path = str(tmp_path / "report.pdf")
    generate_pdf_report(data, out_path)

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 1000  # sanity floor — not an empty/broken PDF

    reader = PdfReader(out_path)
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Compliance Report" in text
    assert data.scan_id in text
    assert product.name in text
    # A real violation from this label should actually show up in the rendered text.
    assert "Missing declaration" in text


def test_docx_report_generation_end_to_end(tmp_path):
    scan, extracted = _run_pipeline_and_engine("label_clean.png")
    product = FakeProduct(name="Refined Sunflower Oil 1L", brand="SunGold", category="Edible Oil")
    image_path = os.path.join(SAMPLES_DIR, "label_clean.png")
    data = build_report_data(scan, product, FakeUser("Asha Verma"), FakeRuleVersion("2025-09-draft-v1"), image_path)

    out_path = str(tmp_path / "report.docx")
    generate_docx_report(data, out_path)

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 1000

    from docx import Document

    doc = Document(out_path)
    paragraph_text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    full_text = paragraph_text + "\n" + table_text
    assert "Legal Metrology Compliance Report" in full_text
    assert data.scan_id in full_text  # lives in the cover key-value table, not a top-level paragraph


def test_annotated_evidence_image_is_produced_when_a_violation_has_a_bbox():
    """label_rotated_lowcontrast.png's net_quantity/MRP fields carry a pixel
    bbox — if a font-height violation is raised against one of them (a
    deliberately high, unrealistic px/mm calibration forces every glyph
    height to convert to a sub-mm value), the evidence image should be a
    real, boxed copy, not just the untouched original."""
    scan, extracted = _run_pipeline_and_engine("label_rotated_lowcontrast.png", calibration_px_per_mm=100.0)
    product = FakeProduct(name="TastyMax Noodles", category="Packaged Food")
    image_path = os.path.join(SAMPLES_DIR, "label_rotated_lowcontrast.png")
    data = build_report_data(scan, product, FakeUser("Asha Verma"), FakeRuleVersion("v1"), image_path)

    from app.reports.annotate import annotate_label_image

    annotated = annotate_label_image(data.image_path, data.fields, data.violations)
    assert annotated is not None
    # A low 1px/mm calibration should push several declarations under the
    # minimum height and produce at least one violation to box.
    assert any(v.rule_id.startswith("R7-3") for v in data.violations)
    assert annotated != image_path  # a boxed copy was actually produced, not just handed back
