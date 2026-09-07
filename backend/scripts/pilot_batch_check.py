"""
Step 8 pilot run: batch-runs real label photos through the exact same
OCR -> field classification -> compliance engine -> report pipeline the
live API uses (see routers/scans.py's upload_scan_image and
routers/reports.py's get_scan_report) — but standalone, against a folder
of images and a metadata CSV, with no database or running server
involved. This is deliberately the lowest-friction way to run the "10-20
real products" pilot described in docs/DEPLOYMENT.md and the Step 8
brief: point it at a folder of photos, get a summary CSV plus one PDF
report per product, and have an inspector compare the engine's verdicts
against their own manual read.

Usage:
    cd backend
    python -m scripts.pilot_batch_check \
        --images-dir /path/to/photos \
        --metadata /path/to/metadata.csv \
        --out-dir ./pilot_reports

metadata.csv columns (see metadata_template.csv alongside this script):
    filename, product_name, brand, category, is_imported, surface_treatment, calibration_px_per_mm

- filename: must match a file in --images-dir
- is_imported: "true"/"false" (blank = false)
- surface_treatment: one of blown/formed/molded/embossed/perforated, or
  blank for an ordinary printed label
- calibration_px_per_mm: the inspector-measured pixels-per-mm for that
  photo (see docs/RULES_CONFIG.md / the ScanDetail page for how this is
  normally captured). Leave blank to skip font-size checks for that row
  — the summary will flag it as needing calibration rather than
  silently passing it, matching the live engine's behavior.
"""
import argparse
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.compliance.engine import ComplianceContext, evaluate_scan  # noqa: E402
from app.ocr.pipeline import process_label_image  # noqa: E402
from app.reports.data import build_report_data  # noqa: E402
from app.reports.pdf_report import generate_pdf_report  # noqa: E402
from app.rules_loader import load_rules  # noqa: E402


class _Row:
    """Duck-typed stand-in for the ORM objects build_report_data expects —
    same pattern backend/tests/test_report_generation.py uses, so this
    script exercises the identical report-assembly code path the live
    API does, without needing a DB."""

    pass


def _make_product(row: dict) -> _Row:
    p = _Row()
    p.name = row["product_name"]
    p.brand = row.get("brand") or None
    p.category = row.get("category") or None
    p.manufacturer_name = None
    p.is_imported = (row.get("is_imported") or "").strip().lower() in ("true", "1", "yes")
    p.surface_treatment = row.get("surface_treatment") or None
    return p


def _make_user() -> _Row:
    u = _Row()
    u.full_name = "Pilot Run"
    return u


def _make_rule_version() -> _Row:
    rv = _Row()
    rv.version_label = load_rules().get("version_label", "unknown")
    return rv


def run(images_dir: str, metadata_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    rules = load_rules()

    summary_path = os.path.join(out_dir, "pilot_summary.csv")
    with open(metadata_path, newline="") as meta_f, open(summary_path, "w", newline="") as summary_f:
        reader = csv.DictReader(meta_f)
        writer = csv.writer(summary_f)
        writer.writerow(
            [
                "filename",
                "product_name",
                "status",
                "open_violations",
                "critical",
                "major",
                "minor",
                "review_items",
                "exempt",
                "report_path",
            ]
        )

        for row in reader:
            filename = row["filename"]
            image_path = os.path.join(images_dir, filename)
            if not os.path.exists(image_path):
                writer.writerow([filename, row.get("product_name", ""), "IMAGE NOT FOUND", "", "", "", "", "", "", ""])
                print(f"  ! {filename}: not found in {images_dir}, skipping")
                continue

            print(f"  processing {filename} ...")
            try:
                extracted = process_label_image(image_path)
            except Exception as exc:  # OCR/preprocessing failure shouldn't kill the whole batch
                writer.writerow([filename, row.get("product_name", ""), f"OCR ERROR: {exc}", "", "", "", "", "", "", ""])
                print(f"  ! {filename}: OCR failed — {exc}")
                continue

            product = _make_product(row)
            calibration_raw = (row.get("calibration_px_per_mm") or "").strip()
            calibration = float(calibration_raw) if calibration_raw else None

            ctx = ComplianceContext(
                is_imported=product.is_imported,
                surface_treatment=product.surface_treatment,
                category=product.category,
            )
            outcome = evaluate_scan(extracted, rules, calibration, ctx)

            scan = _Row()
            scan.id = os.path.splitext(filename)[0]
            scan.status = "review"
            scan.created_at = datetime.now()
            scan.extracted_fields = extracted
            scan.calibration_px_per_mm = calibration
            scan.compliance_review = {
                "exempt": outcome.exempt,
                "exemption_reason": outcome.exemption_reason,
                "review_items": [
                    {"rule_id": ri.rule_id, "category": ri.category, "note": ri.note} for ri in outcome.review_items
                ],
            }
            scan.violations = [
                _violation_row(v) for v in outcome.violations
            ]

            report_filename = f"{scan.id}-report.pdf"
            report_path = os.path.join(out_dir, report_filename)
            data = build_report_data(scan, product, _make_user(), _make_rule_version(), image_path)
            generate_pdf_report(data, report_path)

            severities = [v.severity for v in outcome.violations]
            writer.writerow(
                [
                    filename,
                    product.name,
                    "EXEMPT" if outcome.exempt else ("VIOLATIONS FOUND" if outcome.violations else "PASS"),
                    len(outcome.violations),
                    severities.count("critical"),
                    severities.count("major"),
                    severities.count("minor"),
                    len(outcome.review_items),
                    outcome.exempt,
                    report_path,
                ]
            )

    print(f"\nDone. Summary: {summary_path}")
    print(f"Per-product PDF reports in: {out_dir}/")
    print(
        "\nNext step: have an inspector open each PDF and compare the engine's\n"
        "verdict against their own manual read of the same label. Log any\n"
        "disagreement (false positive/negative) against the specific rule_id\n"
        "involved — see docs/RULES_CONFIG.md for how to correct the rule config\n"
        "or docs/DEPLOYMENT.md's pilot section for the overall process."
    )


def _violation_row(v) -> _Row:
    row = _Row()
    row.rule_id = v.rule_id
    row.citation = v.citation
    row.description = v.description
    row.severity = v.severity
    row.needs_review = v.needs_review
    row.is_resolved = False
    row.resolution_note = None
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", required=True, help="Folder containing the label photos")
    parser.add_argument("--metadata", required=True, help="CSV describing each photo (see metadata_template.csv)")
    parser.add_argument("--out-dir", default="./pilot_reports", help="Where to write the summary CSV and PDFs")
    args = parser.parse_args()
    run(args.images_dir, args.metadata, args.out_dir)
