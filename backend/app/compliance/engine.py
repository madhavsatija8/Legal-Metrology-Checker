"""
Rule-evaluation engine (Step 5). Reads rules/legal_metrology_rules.json
(via rules_loader.load_rules()) plus a scan's extracted_fields (Step 4
output) and produces:

  - `violations`: concrete rule breaches, meant to become Violation rows.
  - `review_items`: things the engine could NOT confidently decide either
    way — missing calibration, rules still marked NEEDS_VERIFICATION in
    the config, checks that need data this pipeline doesn't extract yet,
    low-confidence OCR matches. These are surfaced to an inspector instead
    of being silently treated as a pass (or a false violation).
  - `exempt` / `exemption_reason`: set when the product/net-quantity
    combination exempts it from the standard declaration requirements
    entirely (Chapter II exemptions).

This module never hardcodes a legal threshold — every number it compares
against comes from the rules JSON, so amending the config (and re-running
POST /rule-versions/sync-from-file) is enough to change behaviour without
a code change here.
"""
import re
from dataclasses import dataclass, field


@dataclass
class ComplianceContext:
    """Facts about the product that the rule config's conditional checks
    need but that OCR cannot reliably infer from the label text alone."""

    is_imported: bool = False
    surface_treatment: str | None = None  # e.g. "molded", "embossed", "blown" — None means an ordinary printed label
    category: str | None = None  # used for the tobacco / cement / fertilizer exemption carve-outs


@dataclass
class ViolationDraft:
    rule_id: str
    citation: str | None
    description: str
    severity: str  # "minor" | "major" | "critical" — must match models.ViolationSeverity
    needs_review: bool = False


@dataclass
class ReviewItem:
    rule_id: str | None
    category: str  # "missing_calibration" | "rule_pending_verification" | "not_automated" | "low_confidence_extraction" | "pending_manual_entry"
    note: str


@dataclass
class ComplianceResult:
    violations: list[ViolationDraft] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    exempt: bool = False
    exemption_reason: str | None = None


# --- unit normalization for the exemption check ---

_MASS_TO_GRAMS = {"g": 1, "gm": 1, "gram": 1, "grams": 1, "mg": 0.001, "kg": 1000}
_VOLUME_TO_ML = {"ml": 1, "l": 1000, "lt": 1000, "litre": 1000, "liter": 1000, "ltr": 1000, "ltrs": 1000}

_QUANTITY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)")


def _normalize_quantity(value: str | None) -> tuple[float, str] | None:
    """`value` looks like '70 g' or '1 L' (as produced by
    field_classifier._QUANTITY_UNIT_RE). Returns (amount, dimension) where
    dimension is 'mass_g' or 'volume_ml', or None if it can't be parsed."""
    if not value:
        return None
    m = _QUANTITY_RE.match(value.strip())
    if not m:
        return None
    amount, unit = float(m.group(1)), m.group(2).lower()
    if unit in _MASS_TO_GRAMS:
        return amount * _MASS_TO_GRAMS[unit], "mass_g"
    if unit in _VOLUME_TO_ML:
        return amount * _VOLUME_TO_ML[unit], "volume_ml"
    return None


def _check_exemption(net_quantity_value: str | None, ctx: ComplianceContext) -> tuple[bool, str | None]:
    normalized = _normalize_quantity(net_quantity_value)
    if not normalized:
        # Can't determine the declared quantity (missing or unparseable) —
        # that's itself a finding the mandatory-declaration check below
        # will raise; don't guess at exemption from nothing.
        return False, None
    amount, _dimension = normalized

    is_tobacco = bool(ctx.category and "tobacco" in ctx.category.lower())
    if not is_tobacco and amount < 10:
        return True, "EXEMPT-small-pack: declared net quantity is under 10g/10ml"

    is_cement_or_fertilizer = bool(ctx.category and any(k in ctx.category.lower() for k in ("cement", "fertilizer")))
    bulk_threshold_g = 50000 if is_cement_or_fertilizer else 25000
    if amount > bulk_threshold_g:
        return True, f"EXEMPT-bulk-pack: declared net quantity exceeds {bulk_threshold_g / 1000:g}kg/l"

    return False, None


# --- conditional-rule evaluation ---


def _condition_met(condition: str | None, ctx: ComplianceContext) -> bool:
    if not condition:
        return True
    if condition == "applies_if.is_imported == true":
        return ctx.is_imported
    # An unrecognized condition string fails safe to "always evaluate"
    # rather than silently skipping a real legal requirement because of a
    # typo or a new condition type added to the config later.
    return True


def _surface_condition_met(applies_if: str | None, ctx: ComplianceContext) -> bool:
    if not applies_if or not ctx.surface_treatment:
        return False
    return ctx.surface_treatment.lower() in applies_if.lower()


# --- main entry point ---


def evaluate_scan(
    extracted_fields: dict,
    rules: dict,
    calibration_px_per_mm: float | None,
    ctx: ComplianceContext,
) -> ComplianceResult:
    result = ComplianceResult()

    # process_label_image's output nests the classified fields under
    # "fields"; accept a bare fields dict too so unit tests can pass one directly.
    fields = extracted_fields.get("fields", extracted_fields)

    net_qty_field = fields.get("net_quantity", {})
    exempt, reason = _check_exemption(net_qty_field.get("value"), ctx)
    if exempt:
        result.exempt = True
        result.exemption_reason = reason
        return result  # exempt products skip the rest of the standard checks entirely

    _evaluate_mandatory_declarations(fields, rules.get("mandatory_declarations", []), ctx, result)
    _evaluate_font_and_readability(fields, rules.get("font_and_readability", []), calibration_px_per_mm, ctx, result)
    _evaluate_structural_rules(rules.get("structural_rules", []), result)

    return result


def _evaluate_mandatory_declarations(
    fields: dict, declarations: list[dict], ctx: ComplianceContext, result: ComplianceResult
) -> None:
    for decl in declarations:
        field_name = decl["field"]
        if not _condition_met(decl.get("condition"), ctx):
            continue

        # generic_name is never auto-detected by the OCR pipeline yet (see
        # field_classifier.py's docstring) — flagging every single scan as
        # "missing" here would just be reporting OCR's own limitation, not
        # a real finding about the label.
        if field_name == "generic_name":
            result.review_items.append(
                ReviewItem(
                    rule_id=decl["rule_id"],
                    category="pending_manual_entry",
                    note="Generic/common name isn't auto-extracted yet — needs inspector entry before this declaration can be checked.",
                )
            )
            continue

        extracted = fields.get(field_name, {})
        matched = extracted.get("matched", False)

        if not matched:
            result.violations.append(
                ViolationDraft(
                    rule_id=decl["rule_id"],
                    citation=decl.get("citation"),
                    description=f"Missing declaration: {decl['description']}",
                    severity=decl.get("severity_if_missing", "major"),
                )
            )
            continue

        # Present, but the extraction step itself flagged low confidence —
        # don't fail the label on this alone, but don't count it as a
        # clean pass either.
        low_confidence = extracted.get("needs_inspector_confirmation") or extracted.get("anchored_by_keyword") is False
        if low_confidence:
            result.review_items.append(
                ReviewItem(
                    rule_id=decl["rule_id"],
                    category="low_confidence_extraction",
                    note=f"'{field_name}' was matched but with low extraction confidence — verify against the image before relying on this.",
                )
            )

        # MRP-specific wording check, raised as its own finding since a
        # format defect is a different problem from MRP being absent.
        if decl.get("format_check") == "must_contain_inclusive_of_taxes_wording":
            if not extracted.get("inclusive_of_taxes_wording_present"):
                result.violations.append(
                    ViolationDraft(
                        rule_id=f"{decl['rule_id']}-format",
                        citation=decl.get("citation"),
                        description="MRP is declared but does not carry the required 'inclusive of all taxes' wording.",
                        # The rules config doesn't currently assign a
                        # severity to format defects specifically (only to
                        # the field being missing outright) — defaulting
                        # to "major" since it's still a consumer-facing
                        # pricing disclosure issue. Revisit if the config
                        # is amended to specify this directly.
                        severity="major",
                    )
                )


def _applicable_height_rule(font_rules: list[dict], ctx: ComplianceContext) -> dict | None:
    """A molded/embossed/blown declaration gets the 2mm threshold instead
    of the ordinary 1mm one — pick whichever single rule actually governs
    this label rather than evaluating both and double-reporting the same
    field against two different thresholds."""
    molded_rule = next((r for r in font_rules if r["rule_id"] == "R7-3-molded-height"), None)
    base_rule = next((r for r in font_rules if r["rule_id"] == "R7-3-min-height"), None)
    if molded_rule and _surface_condition_met(molded_rule.get("applies_if"), ctx):
        return molded_rule
    return base_rule


def _table1_slab_threshold(slab_rule: dict, amount_g_or_ml: float, ctx: ComplianceContext) -> float | None:
    """Table I (Rule 7(2)(i)): pick the slab whose weight/volume range
    contains `amount_g_or_ml`, then return its normal- or molded-package
    threshold depending on the product's surface treatment."""
    molded = _surface_condition_met(
        "blown formed molded embossed perforated" if ctx.surface_treatment else None, ctx
    )
    for slab in slab_rule.get("slabs", []):
        lower = slab.get("more_than_g_or_ml", 0)
        upper = slab.get("up_to_g_or_ml")
        if amount_g_or_ml <= lower:
            continue
        if upper is not None and amount_g_or_ml > upper:
            continue
        return slab["min_height_mm_molded"] if molded else slab["min_height_mm_normal"]
    return None


def _evaluate_numeral_height_slabs(
    fields: dict,
    slab_rule: dict | None,
    calibration_px_per_mm: float | None,
    ctx: ComplianceContext,
    result: ComplianceResult,
) -> None:
    """Rule 7(2)(i)/Table I: net-quantity and MRP numerals must clear a
    threshold that scales with the declared weight/volume, not the flat
    1mm/2mm of Rule 7(3) (which governs every *other* declaration on the
    label). This only covers weight/volume packages (Table I) — Table II
    (length/area/number, keyed to the package's own principal-display-
    panel area) needs package-dimension input this pipeline doesn't
    collect yet, and is reported as a review item instead."""
    if not slab_rule or not slab_rule.get("slabs"):
        return  # config not populated — nothing to enforce (shouldn't happen post-fill, kept as a safety no-op)

    net_qty_field = fields.get("net_quantity", {})
    normalized = _normalize_quantity(net_qty_field.get("value"))
    if not normalized or normalized[1] != "mass_g" and normalized[1] != "volume_ml":
        result.review_items.append(
            ReviewItem(
                rule_id=slab_rule["rule_id"],
                category="not_automated",
                note="Numeral-height slab (Table I) could not be evaluated — declared net quantity wasn't recognized as a weight or volume (it may be declared by length/area/number, which needs Table II and package-dimension input this pipeline doesn't collect yet).",
            )
        )
        return
    amount_g_or_ml, _dim = normalized
    threshold = _table1_slab_threshold(slab_rule, amount_g_or_ml, ctx)
    if threshold is None:
        return

    if not calibration_px_per_mm or calibration_px_per_mm <= 0:
        return  # already reported once as "missing_calibration" by the caller

    for field_name in ("net_quantity", "retail_sale_price"):
        extracted = fields.get(field_name, {})
        px = extracted.get("pixel_height")
        if not extracted.get("matched") or not px:
            continue
        mm = px / calibration_px_per_mm
        if mm < threshold:
            result.violations.append(
                ViolationDraft(
                    rule_id=slab_rule["rule_id"],
                    citation=slab_rule.get("citation"),
                    description=(
                        f"'{field_name}' numeral height is approximately {mm:.2f}mm, below the "
                        f"{threshold}mm minimum required by Table I for a {amount_g_or_ml:g}g/ml package."
                    ),
                    severity=slab_rule.get("severity_if_violated", "minor"),
                )
            )


def _evaluate_font_and_readability(
    fields: dict,
    font_rules: list[dict],
    calibration_px_per_mm: float | None,
    ctx: ComplianceContext,
    result: ComplianceResult,
) -> None:
    if not calibration_px_per_mm or calibration_px_per_mm <= 0:
        result.review_items.append(
            ReviewItem(
                rule_id=None,
                category="missing_calibration",
                note="No pixels-per-mm calibration recorded for this scan — font-size/readability rules were not evaluated. Enter a reference dimension and re-run evaluation.",
            )
        )
    else:
        height_rule = _applicable_height_rule(font_rules, ctx)
        if height_rule:
            threshold = height_rule["min_letter_height_mm"]
            # net_quantity/retail_sale_price are excluded here: their
            # numerals are governed by the Table I slab check below
            # instead of this flat threshold (Rule 7(2) vs Rule 7(3)).
            for field_name, extracted in fields.items():
                if field_name in ("net_quantity", "retail_sale_price"):
                    continue
                if not isinstance(extracted, dict):
                    continue
                px = extracted.get("pixel_height")
                if not extracted.get("matched") or not px:
                    continue
                mm = px / calibration_px_per_mm
                if mm < threshold:
                    result.violations.append(
                        ViolationDraft(
                            rule_id=height_rule["rule_id"],
                            citation=height_rule.get("citation"),
                            description=(
                                f"'{field_name}' letter height is approximately {mm:.2f}mm, "
                                f"below the required minimum of {threshold}mm."
                            ),
                            severity=height_rule.get("severity_if_violated", "minor"),
                        )
                    )

    # Width-to-height ratio: the config has a real threshold, but
    # extraction.Line currently only carries line-level height, not
    # per-glyph width — so this can't be checked yet.
    width_rule = next((r for r in font_rules if r["rule_id"] == "R7-3-width-ratio"), None)
    if width_rule:
        result.review_items.append(
            ReviewItem(
                rule_id=width_rule["rule_id"],
                category="not_automated",
                note="Letter width-to-height ratio isn't checked yet — extraction doesn't currently capture per-glyph width.",
            )
        )

    # Numeral height slabs by net-quantity (Table I) — now enforced using
    # the verified slab data in the rules config.
    slab_rule = next((r for r in font_rules if r["rule_id"] == "R7-numeral-height-slabs"), None)
    if slab_rule and not slab_rule.get("slabs"):
        result.review_items.append(
            ReviewItem(
                rule_id=slab_rule["rule_id"],
                category="rule_pending_verification",
                note="Numeral height slab thresholds are not yet populated in the rules config — this rule is not enforced until the legal text is confirmed and the config updated.",
            )
        )
    else:
        _evaluate_numeral_height_slabs(fields, slab_rule, calibration_px_per_mm, ctx, result)

    # Table II (length/area/number) is stored in the config for
    # reference but always surfaced as a review item — it needs package
    # dimension/principal-display-panel-area input this pipeline doesn't
    # collect, unlike Table I which can be driven off the declared
    # weight/volume alone.
    slab_rule_2 = next((r for r in font_rules if r["rule_id"] == "R7-numeral-height-slabs-table2"), None)
    if slab_rule_2:
        result.review_items.append(
            ReviewItem(
                rule_id=slab_rule_2["rule_id"],
                category="not_automated",
                note="Table II (length/area/number numeral-height slabs) requires principal-display-panel area input not yet captured — not automatically evaluated.",
            )
        )


def _evaluate_structural_rules(structural_rules: list[dict], result: ComplianceResult) -> None:
    for rule in structural_rules:
        # Principal-display-panel-area rules need package shape/dimension
        # input this pipeline doesn't collect yet — surfaced for visibility
        # rather than silently omitted from the output.
        result.review_items.append(
            ReviewItem(
                rule_id=rule["rule_id"],
                category="not_automated",
                note=f"{rule['description']} — requires package dimension/shape input not yet captured; not automatically evaluated.",
            )
        )
