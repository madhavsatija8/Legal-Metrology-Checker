"""
Step 7: exposes the reporting module (../reports/) as a download endpoint.
Kept as its own router rather than folded into routers/scans.py since it
has a different concern (rendering a document) from the rest of the scan
lifecycle, even though it's nested under the same /scans/{scan_id} path.
"""
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_db
from ..reports.data import build_report_data
from ..reports.docx_report import generate_docx_report
from ..reports.pdf_report import generate_pdf_report

router = APIRouter(prefix="/scans", tags=["reports"])

# Same local-disk storage location routers/scans.py writes uploaded images
# to — resolved here rather than imported from there to avoid a circular
# import between the two routers.
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "storage")

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{scan_id}/report")
def get_scan_report(
    scan_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """
    Generates a compliance report for this scan on demand from its current
    stored data (extracted fields, violations, review items) — nothing is
    cached, so the report always reflects the latest evaluation/resolution
    state. `format=pdf` (default) for the locked record copy, `format=docx`
    for an editable version an inspector can annotate before finalizing.
    """
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    product = db.get(models.Product, scan.product_id)
    created_by = db.get(models.User, scan.created_by_id)
    rule_version = db.get(models.RuleVersion, scan.rule_version_id) if scan.rule_version_id else None
    image_abs_path = os.path.join(STORAGE_DIR, scan.image_path) if scan.image_path else None

    data = build_report_data(scan, product, created_by, rule_version, image_abs_path)

    out_dir = tempfile.mkdtemp(prefix="lmc_report_")
    filename = f"compliance-report-{scan.id[:8]}.{format}"
    out_path = os.path.join(out_dir, filename)

    if format == "pdf":
        generate_pdf_report(data, out_path)
    else:
        generate_docx_report(data, out_path)

    return FileResponse(out_path, media_type=_MEDIA_TYPES[format], filename=filename)
