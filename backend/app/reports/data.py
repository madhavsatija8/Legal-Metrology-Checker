"""
Step 7 reporting module: data assembly.

Both the PDF and DOCX generators read from the same `ReportData` snapshot
built here, rather than each pulling its own subset of fields off the ORM
objects — the same "single source of truth" pattern the rules config
(Step 2) and the compliance engine (Step 5) already follow, so the two
output formats can never drift out of sync with each other.

`build_report_data` is duck-typed against attribute access rather than
importing `..models` types directly, so unit tests can pass lightweight
stand-ins (see tests/test_report_generation.py) without touching the DB —
the router (routers/reports.py) passes real ORM instances in production.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReportProduct:
    name: str
    brand: str | None = None
    category: str | None = None
    manufacturer_name: str | None = None
    is_imported: bool = False
    surface_treatment: str | None = None


@dataclass
class ReportViolation:
    rule_id: str
    citation: str | None
    description: str
    severity: str  # "minor" | "major" | "critical"
    needs_review: bool
    is_resolved: bool
    resolution_note: str | None = None


@dataclass
class ReportData:
    scan_id: str
    generated_at: datetime
    scan_created_at: datetime
    status: str
    product: ReportProduct
    inspector_name: str | None
    rule_version_label: str | None
    calibration_px_per_mm: float | None
    fields: dict  # the classified-declaration dict from the OCR pipeline (Step 4)
    violations: list[ReportViolation] = field(default_factory=list)
    exempt: bool = False
    exemption_reason: str | None = None
    review_items: list[dict] = field(default_factory=list)
    image_path: str | None = None  # absolute path on disk to the original label photo, if any

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = {"critical": 0, "major": 0, "minor": 0}
        for v in self.violations:
            if v.severity in counts:
                counts[v.severity] += 1
        return counts

    @property
    def unresolved_count(self) -> int:
        return sum(1 for v in self.violations if not v.is_resolved)

    @property
    def overall_pass(self) -> bool:
        """A simple pass/fail headline for the report cover: exempt products
        pass trivially, otherwise a scan only passes if nothing unresolved
        remains open — matches how routers/violations.py drives the dashboard."""
        return self.exempt or self.unresolved_count == 0


def build_report_data(scan, product, created_by, rule_version, image_abs_path: str | None) -> ReportData:
    extracted = scan.extracted_fields or {}
    fields = extracted.get("fields", extracted) if isinstance(extracted, dict) else {}

    review = scan.compliance_review or {}

    violations = [
        ReportViolation(
            rule_id=v.rule_id,
            citation=v.citation,
            description=v.description,
            severity=v.severity.value if hasattr(v.severity, "value") else str(v.severity),
            needs_review=v.needs_review,
            is_resolved=v.is_resolved,
            resolution_note=v.resolution_note,
        )
        for v in (scan.violations or [])
    ]

    return ReportData(
        scan_id=scan.id,
        generated_at=datetime.utcnow(),
        scan_created_at=scan.created_at,
        status=scan.status.value if hasattr(scan.status, "value") else str(scan.status),
        product=ReportProduct(
            name=product.name if product else "Unknown product",
            brand=getattr(product, "brand", None),
            category=getattr(product, "category", None),
            manufacturer_name=getattr(product, "manufacturer_name", None),
            is_imported=bool(getattr(product, "is_imported", False)),
            surface_treatment=getattr(product, "surface_treatment", None),
        ),
        inspector_name=getattr(created_by, "full_name", None),
        rule_version_label=getattr(rule_version, "version_label", None),
        calibration_px_per_mm=scan.calibration_px_per_mm,
        fields=fields,
        violations=violations,
        exempt=bool(review.get("exempt")),
        exemption_reason=review.get("exemption_reason"),
        review_items=review.get("review_items", []),
        image_path=image_abs_path,
    )
