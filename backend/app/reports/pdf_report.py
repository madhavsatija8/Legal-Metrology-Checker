"""
Step 7: PDF compliance report, built entirely from a `ReportData`
snapshot (data.py) — no re-deriving fields or violations at render time,
so this file only ever has to know how to lay a page out, not how the
compliance engine works.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .annotate import annotate_label_image
from .data import ReportData

_SEVERITY_COLOR = {
    "critical": colors.HexColor("#8B1A1A"),
    "major": colors.HexColor("#B4530A"),
    "minor": colors.HexColor("#8A7A00"),
}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontSize=18, spaceAfter=4))
    styles.add(ParagraphStyle(name="SubTitle", parent=styles["Normal"], textColor=colors.grey, spaceAfter=14))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=6))
    styles.add(
        ParagraphStyle(
            name="PassBanner",
            parent=styles["Normal"],
            fontSize=13,
            textColor=colors.white,
            alignment=1,
        )
    )
    return styles


def _cell(text, style):
    """Wrap plain strings in a Paragraph so long text wraps inside a table cell instead of overflowing it."""
    return Paragraph(str(text) if text not in (None, "") else "\u2014", style)


def _cover_table(data: ReportData, styles) -> Table:
    p = data.product
    rows = [
        ["Scan ID", data.scan_id],
        ["Product", p.name],
        ["Brand", p.brand or "\u2014"],
        ["Category", p.category or "\u2014"],
        ["Manufacturer", p.manufacturer_name or "\u2014"],
        ["Imported", "Yes" if p.is_imported else "No"],
        ["Surface treatment", p.surface_treatment or "Ordinary printed label"],
        ["Scan status", data.status],
        ["Scanned on", data.scan_created_at.strftime("%d %b %Y, %H:%M UTC")],
        ["Inspector", data.inspector_name or "\u2014"],
        ["Rule version evaluated", data.rule_version_label or "\u2014"],
        [
            "Font calibration",
            f"{data.calibration_px_per_mm:g} px/mm" if data.calibration_px_per_mm else "Not set — font-size checks skipped",
        ],
    ]
    table_data = [[_cell(k, styles["Normal"]), _cell(v, styles["Normal"])] for k, v in rows]
    t = Table(table_data, colWidths=[45 * mm, 110 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F0EA")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D3C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _result_banner(data: ReportData, styles):
    if data.exempt:
        text, bg = f"EXEMPT \u2014 {data.exemption_reason}", colors.HexColor("#5A6B3D")
    elif data.overall_pass:
        text, bg = "NO OPEN VIOLATIONS", colors.HexColor("#2F6B4F")
    else:
        counts = data.severity_counts
        summary = ", ".join(f"{n} {sev}" for sev, n in counts.items() if n)
        text, bg = f"OPEN VIOLATIONS \u2014 {summary}", colors.HexColor("#8B1A1A")

    t = Table([[Paragraph(text, styles["PassBanner"])]], colWidths=[155 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _declarations_table(data: ReportData, styles) -> Table:
    header = ["Declaration", "Detected", "Detail"]
    rows = [[_cell(h, styles["Normal"]) for h in header]]
    for name, entry in sorted(data.fields.items()):
        if not isinstance(entry, dict):
            continue
        matched = entry.get("matched")
        detail = entry.get("value") or entry.get("amount") or entry.get("raw_text") or entry.get("source_line") or entry.get("note") or ""
        rows.append(
            [
                _cell(name.replace("_", " "), styles["Normal"]),
                _cell("Yes" if matched else "No", styles["Normal"]),
                _cell(detail, styles["Normal"]),
            ]
        )
    t = Table(rows, colWidths=[50 * mm, 25 * mm, 80 * mm], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F2A22")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D3C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF8F2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _violations_table(data: ReportData, styles) -> Table | None:
    if not data.violations:
        return None
    header = ["Severity", "Citation", "Description", "Status"]
    rows = [[_cell(h, styles["Normal"]) for h in header]]
    for v in data.violations:
        status = f"Resolved \u2014 {v.resolution_note}" if v.is_resolved else "Open"
        sev_style = ParagraphStyle(
            name=f"sev_{v.severity}",
            parent=styles["Normal"],
            textColor=_SEVERITY_COLOR.get(v.severity, colors.black),
            fontName="Helvetica-Bold",
        )
        rows.append(
            [
                Paragraph(v.severity.upper(), sev_style),
                _cell(v.citation, styles["Normal"]),
                _cell(v.description, styles["Normal"]),
                _cell(status, styles["Normal"]),
            ]
        )
    t = Table(rows, colWidths=[26 * mm, 20 * mm, 76 * mm, 33 * mm], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F2A22")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D3C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF8F2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def generate_pdf_report(data: ReportData, out_path: str) -> str:
    styles = _styles()
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Compliance Report - {data.scan_id}",
    )

    story = [
        Paragraph("Legal Metrology Compliance Report", styles["ReportTitle"]),
        Paragraph(
            "Legal Metrology (Packaged Commodities) Rules, 2011 &mdash; automated scan assessment, "
            f"generated {data.generated_at.strftime('%d %b %Y, %H:%M UTC')}",
            styles["SubTitle"],
        ),
        _result_banner(data, styles),
        Spacer(1, 10),
        _cover_table(data, styles),
        Spacer(1, 4),
    ]

    story.append(Paragraph("Mandatory Declarations", styles["SectionHeading"]))
    story.append(_declarations_table(data, styles))

    violations_table = _violations_table(data, styles)
    if violations_table:
        story.append(Paragraph("Violations", styles["SectionHeading"]))
        story.append(violations_table)

    if data.review_items:
        story.append(Paragraph("Flagged for Manual Review", styles["SectionHeading"]))
        for ri in data.review_items:
            label = ri.get("rule_id") or ri.get("category", "").replace("_", " ")
            story.append(Paragraph(f"\u2022 <b>{label}</b>: {ri.get('note', '')}", styles["Normal"]))
            story.append(Spacer(1, 2))

    annotated_path = annotate_label_image(data.image_path, data.fields, data.violations)
    if annotated_path:
        story.append(Paragraph("Evidence", styles["SectionHeading"]))
        try:
            img = Image(annotated_path, width=140 * mm, height=105 * mm, kind="proportional")
            story.append(img)
            story.append(
                Paragraph(
                    "Boxes mark declarations tied to an open violation on this scan.",
                    ParagraphStyle(name="caption", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
                )
            )
        except Exception:
            # A corrupt/unreadable image shouldn't block the rest of the report from being generated.
            story.append(Paragraph("Evidence image could not be rendered.", styles["Normal"]))

    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            "This report is generated by an automated compliance-checking system. Findings marked "
            "'needs review' or drawn from low-confidence extraction should be verified by an inspector "
            "before being relied on for enforcement action.",
            ParagraphStyle(name="disclaimer", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(story)
    return out_path
