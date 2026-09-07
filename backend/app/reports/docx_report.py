"""
Step 7: editable DOCX compliance report, generated with python-docx (a
Python library, matching the rest of this FastAPI backend's stack)
rather than a JS tool, since this file is application code that runs
inside the deployed service — not a one-off document Claude hands to a
user directly.

Same ReportData snapshot as pdf_report.py (see data.py) and the same
scope of content, laid out so an inspector can annotate or amend it
before it's finalized (e.g. adding a manual generic-name entry, or a
note on a resolved violation) ahead of producing the locked PDF.
"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from .annotate import annotate_label_image
from .data import ReportData

_SEVERITY_COLOR = {
    "critical": RGBColor(0x8B, 0x1A, 0x1A),
    "major": RGBColor(0xB4, 0x53, 0x0A),
    "minor": RGBColor(0x8A, 0x7A, 0x00),
}


def _add_heading(doc, text, level=1):
    doc.add_heading(text, level=level)


def _add_kv_table(doc, rows: list[tuple[str, str]]):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for key, value in rows:
        row = table.add_row().cells
        row[0].text = key
        row[0].paragraphs[0].runs[0].bold = True
        row[1].text = value or "\u2014"
    return table


def generate_docx_report(data: ReportData, out_path: str) -> str:
    doc = Document()

    title = doc.add_heading("Legal Metrology Compliance Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    sub = doc.add_paragraph(
        "Legal Metrology (Packaged Commodities) Rules, 2011 \u2014 automated scan assessment, "
        f"generated {data.generated_at.strftime('%d %b %Y, %H:%M UTC')}"
    )
    sub.runs[0].italic = True

    # --- result banner ---
    if data.exempt:
        banner_text = f"EXEMPT \u2014 {data.exemption_reason}"
    elif data.overall_pass:
        banner_text = "NO OPEN VIOLATIONS"
    else:
        counts = data.severity_counts
        summary = ", ".join(f"{n} {sev}" for sev, n in counts.items() if n)
        banner_text = f"OPEN VIOLATIONS \u2014 {summary}"
    banner = doc.add_paragraph()
    banner_run = banner.add_run(banner_text)
    banner_run.bold = True
    banner_run.font.size = Pt(13)

    # --- cover details ---
    p = data.product
    _add_kv_table(
        doc,
        [
            ("Scan ID", data.scan_id),
            ("Product", p.name),
            ("Brand", p.brand),
            ("Category", p.category),
            ("Manufacturer", p.manufacturer_name),
            ("Imported", "Yes" if p.is_imported else "No"),
            ("Surface treatment", p.surface_treatment or "Ordinary printed label"),
            ("Scan status", data.status),
            ("Scanned on", data.scan_created_at.strftime("%d %b %Y, %H:%M UTC")),
            ("Inspector", data.inspector_name),
            ("Rule version evaluated", data.rule_version_label),
            (
                "Font calibration",
                f"{data.calibration_px_per_mm:g} px/mm" if data.calibration_px_per_mm else "Not set — font-size checks skipped",
            ),
        ],
    )

    # --- mandatory declarations ---
    _add_heading(doc, "Mandatory Declarations", level=1)
    decl_table = doc.add_table(rows=1, cols=3)
    decl_table.style = "Light List Accent 1"
    hdr = decl_table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "Declaration", "Detected", "Detail"
    for name, entry in sorted(data.fields.items()):
        if not isinstance(entry, dict):
            continue
        matched = entry.get("matched")
        detail = entry.get("value") or entry.get("amount") or entry.get("raw_text") or entry.get("source_line") or entry.get("note") or "\u2014"
        row = decl_table.add_row().cells
        row[0].text = name.replace("_", " ")
        row[1].text = "Yes" if matched else "No"
        row[2].text = str(detail)

    # --- violations ---
    if data.violations:
        _add_heading(doc, "Violations", level=1)
        v_table = doc.add_table(rows=1, cols=4)
        v_table.style = "Light List Accent 1"
        hdr = v_table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Severity", "Citation", "Description", "Status"
        for v in data.violations:
            row = v_table.add_row().cells
            sev_run = row[0].paragraphs[0].add_run(v.severity.upper())
            sev_run.bold = True
            sev_run.font.color.rgb = _SEVERITY_COLOR.get(v.severity, RGBColor(0, 0, 0))
            row[1].text = v.citation or "\u2014"
            row[2].text = v.description
            row[3].text = f"Resolved \u2014 {v.resolution_note}" if v.is_resolved else "Open"

    # --- review items: left as an editable checklist for the inspector ---
    if data.review_items:
        _add_heading(doc, "Flagged for Manual Review", level=1)
        for ri in data.review_items:
            label = ri.get("rule_id") or ri.get("category", "").replace("_", " ")
            para = doc.add_paragraph(style="List Bullet")
            run = para.add_run(f"{label}: ")
            run.bold = True
            para.add_run(ri.get("note", ""))
        doc.add_paragraph(
            "Use this section to record inspector findings for each item above before finalizing the report."
        ).italic = True

    # --- evidence image ---
    annotated_path = annotate_label_image(data.image_path, data.fields, data.violations)
    if annotated_path:
        _add_heading(doc, "Evidence", level=1)
        try:
            doc.add_picture(annotated_path, width=Inches(5.5))
            caption = doc.add_paragraph("Boxes mark declarations tied to an open violation on this scan.")
            caption.runs[0].italic = True
            caption.runs[0].font.size = Pt(8)
        except Exception:
            doc.add_paragraph("Evidence image could not be embedded.")

    doc.add_paragraph()
    disclaimer = doc.add_paragraph(
        "This report is generated by an automated compliance-checking system. Findings marked "
        "'needs review' or drawn from low-confidence extraction should be verified by an inspector "
        "before being relied on for enforcement action."
    )
    disclaimer.runs[0].italic = True
    disclaimer.runs[0].font.size = Pt(8)

    doc.save(out_path)
    return out_path
