"""
Unit tests for the Step 5 compliance engine (app/compliance/engine.py).
Deliberately uses synthetic extracted_fields dicts rather than running
OCR, so these run fast and everywhere (no tesseract dependency) — the
OCR->extraction contract itself is covered by test_ocr_pipeline.py.

Tests load the *actual* rules/legal_metrology_rules.json (via
rules_loader.load_rules()) rather than a hand-rolled fixture, so a rule
being renamed/removed in the real config would break these tests too --
that's intentional, since it's the same coupling the real engine has.
"""
import pytest

from app.compliance.engine import ComplianceContext, evaluate_scan
from app.rules_loader import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _base_fields(**overrides):
    """A minimal but complete set of matched fields, so each test only
    has to override what it actually cares about."""
    fields = {
        "net_quantity": {"matched": True, "value": "1 kg", "pixel_height": 20, "anchored_by_keyword": True},
        "retail_sale_price": {
            "matched": True,
            "amount": "185.00",
            "inclusive_of_taxes_wording_present": True,
            "pixel_height": 18,
        },
        "date_of_manufacture_or_packing_or_import": {"matched": True, "value": "05/2026", "pixel_height": 15, "anchored_by_keyword": True},
        "consumer_care_details": {"matched": True, "phone": "1800-123-4567", "pixel_height": 14, "anchored_by_keyword": True},
        "manufacturer_packer_importer_details": {
            "matched": True,
            "raw_text": "Mfd by SunGold Agro Pvt Ltd, Pune",
            "pixel_height": 16,
            "needs_inspector_confirmation": True,
        },
        "country_of_origin": {"matched": False, "value": None, "pixel_height": None},
        "generic_name": {"matched": False, "value": None},
    }
    fields.update(overrides)
    return fields


def _ctx(**kwargs) -> ComplianceContext:
    return ComplianceContext(**kwargs)


# --- mandatory declarations ---


def test_missing_mrp_raises_critical_violation(rules):
    fields = _base_fields(retail_sale_price={"matched": False, "amount": None, "pixel_height": None})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    ids = {v.rule_id for v in result.violations}
    assert "R6-1-mrp" in ids
    assert next(v for v in result.violations if v.rule_id == "R6-1-mrp").severity == "critical"


def test_mrp_present_but_missing_inclusive_wording_is_a_separate_violation(rules):
    fields = _base_fields(
        retail_sale_price={"matched": True, "amount": "185.00", "inclusive_of_taxes_wording_present": False, "pixel_height": 18}
    )
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    ids = {v.rule_id for v in result.violations}
    assert "R6-1-mrp" not in ids  # MRP itself is present — not a "missing" violation
    assert "R6-1-mrp-format" in ids


def test_country_of_origin_only_checked_for_imports(rules):
    fields = _base_fields()  # country_of_origin not matched

    domestic = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx(is_imported=False))
    assert "R6-1-a-origin" not in {v.rule_id for v in domestic.violations}

    imported = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx(is_imported=True))
    assert "R6-1-a-origin" in {v.rule_id for v in imported.violations}


def test_generic_name_is_flagged_for_manual_entry_not_as_a_violation(rules):
    fields = _base_fields()
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert "R6-1-b" not in {v.rule_id for v in result.violations}
    assert any(ri.rule_id == "R6-1-b" and ri.category == "pending_manual_entry" for ri in result.review_items)


def test_low_confidence_match_is_flagged_for_review_not_treated_as_a_violation(rules):
    fields = _base_fields()  # manufacturer field has needs_inspector_confirmation=True
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert "R6-1-a" not in {v.rule_id for v in result.violations}
    assert any(ri.rule_id == "R6-1-a" and ri.category == "low_confidence_extraction" for ri in result.review_items)


# --- exemptions ---


def test_small_pack_under_10g_is_fully_exempt(rules):
    fields = _base_fields(net_quantity={"matched": True, "value": "5 g", "pixel_height": 10})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert result.exempt is True
    assert result.violations == []


def test_bulk_pack_over_25kg_is_exempt(rules):
    fields = _base_fields(net_quantity={"matched": True, "value": "30 kg", "pixel_height": 10})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert result.exempt is True


def test_cement_bulk_pack_uses_50kg_threshold(rules):
    fields = _base_fields(net_quantity={"matched": True, "value": "30 kg", "pixel_height": 10})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx(category="Cement"))
    assert result.exempt is False  # 30kg is under the 50kg cement/fertilizer threshold


def test_normal_sized_pack_is_not_exempt(rules):
    fields = _base_fields()  # 1kg, well within normal range
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert result.exempt is False


# --- font size / readability ---


def test_missing_calibration_skips_font_checks_and_flags_it(rules):
    fields = _base_fields()
    result = evaluate_scan(fields, rules, calibration_px_per_mm=None, ctx=_ctx())
    assert not any(v.rule_id.startswith("R7-3") for v in result.violations)
    assert any(ri.category == "missing_calibration" for ri in result.review_items)


def test_letter_height_below_threshold_is_a_violation(rules):
    # 3px at 8px/mm = 0.375mm, under the 1mm minimum.
    fields = _base_fields(net_quantity={"matched": True, "value": "1 kg", "pixel_height": 3})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    height_violations = [v for v in result.violations if v.rule_id == "R7-3-min-height"]
    assert len(height_violations) == 1
    assert "net_quantity" in height_violations[0].description


def test_letter_height_above_threshold_is_not_a_violation(rules):
    # 20px at 8px/mm = 2.5mm, comfortably above the 1mm minimum.
    fields = _base_fields(net_quantity={"matched": True, "value": "1 kg", "pixel_height": 20})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert not any(v.rule_id == "R7-3-min-height" and "net_quantity" in v.description for v in result.violations)


def test_molded_surface_treatment_uses_2mm_threshold_instead_of_1mm(rules):
    # 12px at 8px/mm = 1.5mm: fails the 2mm molded threshold but would pass the 1mm base one.
    fields = _base_fields(net_quantity={"matched": True, "value": "1 kg", "pixel_height": 12})
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx(surface_treatment="molded"))
    ids = [v.rule_id for v in result.violations if "net_quantity" in v.description]
    assert ids == ["R7-3-molded-height"]


def test_width_ratio_rule_is_always_surfaced_as_not_automated(rules):
    fields = _base_fields()
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert any(ri.rule_id == "R7-3-width-ratio" and ri.category == "not_automated" for ri in result.review_items)


def test_numeral_height_slabs_rule_is_surfaced_as_pending_verification(rules):
    fields = _base_fields()
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert any(
        ri.rule_id == "R7-numeral-height-slabs" and ri.category == "rule_pending_verification"
        for ri in result.review_items
    )


def test_structural_rules_are_surfaced_as_not_automated(rules):
    fields = _base_fields()
    result = evaluate_scan(fields, rules, calibration_px_per_mm=8.0, ctx=_ctx())
    assert any(ri.rule_id == "R7-4-panel-area" and ri.category == "not_automated" for ri in result.review_items)
