"""
Runs the actual OCR & extraction pipeline (Tesseract included, no
mocking) against three concrete sample labels checked into
tests/sample_labels/. Requires the `tesseract-ocr` binary on PATH —
skips automatically if it isn't installed, e.g. in a CI image that
hasn't run `apt-get install tesseract-ocr` yet.

Why these three specifically:
- label_clean.png: a well-formed label, all mandatory fields present.
  Baseline sanity check — if this fails, something is broken in
  preprocessing/OCR/regex, not in a specific edge case.
- label_rotated_lowcontrast.png: a few degrees of rotation plus washed-
  out contrast, simulating a real phone photo. Exercises the deskew and
  CLAHE steps in preprocessing.py.
- label_missing_fields.png: MRP and consumer care details are absent by
  construction. This is what the compliance engine (Step 5) depends on
  being detected correctly — a false "matched: true" here would mean a
  real violation gets silently missed.
"""
import os
import shutil

import pytest

from app.ocr.pipeline import process_label_image

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "sample_labels")

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract-ocr binary not installed",
)


def _sample(name: str) -> str:
    return os.path.join(SAMPLES_DIR, name)


def test_clean_label_extracts_all_mandatory_fields():
    result = process_label_image(_sample("label_clean.png"))
    fields = result["fields"]

    assert fields["net_quantity"]["matched"] is True
    assert fields["net_quantity"]["value"] == "1 L"

    assert fields["retail_sale_price"]["matched"] is True
    assert fields["retail_sale_price"]["amount"] == "185.00"
    assert fields["retail_sale_price"]["inclusive_of_taxes_wording_present"] is True

    assert fields["date_of_manufacture_or_packing_or_import"]["matched"] is True
    assert fields["consumer_care_details"]["matched"] is True
    assert fields["consumer_care_details"]["phone"] == "1800-123-4567"
    assert fields["manufacturer_packer_importer_details"]["matched"] is True

    # Every matched field should carry a pixel height for Step 5's
    # mm-conversion / readability check to consume.
    for field_name in ["net_quantity", "retail_sale_price", "manufacturer_packer_importer_details"]:
        assert fields[field_name]["pixel_height"] is not None
        assert fields[field_name]["pixel_height"] > 0


def test_rotated_low_contrast_label_still_extracts_correctly():
    """A ~4-degree rotation and washed-out contrast shouldn't break extraction."""
    result = process_label_image(_sample("label_rotated_lowcontrast.png"))
    fields = result["fields"]

    assert fields["net_quantity"]["matched"] is True
    assert fields["net_quantity"]["value"] == "70 g"
    assert fields["retail_sale_price"]["matched"] is True
    assert fields["retail_sale_price"]["amount"] == "14"
    assert result["average_ocr_confidence"] > 50  # sanity floor, not a tight bound


def test_label_with_missing_fields_is_reported_as_missing():
    """MRP and consumer care are genuinely absent from this label — must not be hallucinated as present."""
    result = process_label_image(_sample("label_missing_fields.png"))
    fields = result["fields"]

    assert fields["net_quantity"]["matched"] is True  # present on this label
    assert fields["retail_sale_price"]["matched"] is False  # genuinely absent
    assert fields["consumer_care_details"]["matched"] is False  # genuinely absent
