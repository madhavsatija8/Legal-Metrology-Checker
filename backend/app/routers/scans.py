import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..compliance.engine import ComplianceContext, evaluate_scan
from ..database import get_db
from ..ocr.pipeline import process_label_image
from ..rules_loader import load_rules

router = APIRouter(prefix="/scans", tags=["scans"])

# Local-disk stand-in for object storage (S3/MinIO) — swap STORAGE_DIR's
# implementation for a real bucket client when deploying; the rest of
# this router doesn't need to change since it only deals with a path/key.
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)


def _active_rule_version(db: Session) -> models.RuleVersion | None:
    return db.query(models.RuleVersion).filter(models.RuleVersion.is_active.is_(True)).first()


def _run_compliance_evaluation(db: Session, scan: models.Scan) -> None:
    """
    Runs the Step 5 engine against this scan's current extracted_fields and
    calibration, and persists the result. Safe to call repeatedly (e.g.
    after an inspector edits extracted_fields or adds calibration): it
    replaces the *unresolved* engine-generated violations with the fresh
    set, but leaves already-resolved violations alone, so re-evaluating
    doesn't wipe an inspector's resolution history.
    """
    if not scan.extracted_fields or "fields" not in scan.extracted_fields:
        return

    product = db.get(models.Product, scan.product_id)
    ctx = ComplianceContext(
        is_imported=bool(product.is_imported) if product else False,
        surface_treatment=product.surface_treatment if product else None,
        category=product.category if product else None,
    )

    rules = load_rules()
    outcome = evaluate_scan(scan.extracted_fields, rules, scan.calibration_px_per_mm, ctx)

    db.query(models.Violation).filter(
        models.Violation.scan_id == scan.id,
        models.Violation.is_resolved.is_(False),
    ).delete()

    for v in outcome.violations:
        db.add(
            models.Violation(
                scan_id=scan.id,
                rule_id=v.rule_id,
                citation=v.citation,
                description=v.description,
                severity=models.ViolationSeverity(v.severity),
                needs_review=v.needs_review,
            )
        )

    scan.compliance_review = {
        "exempt": outcome.exempt,
        "exemption_reason": outcome.exemption_reason,
        "review_items": [
            {"rule_id": ri.rule_id, "category": ri.category, "note": ri.note} for ri in outcome.review_items
        ],
    }


@router.post("", response_model=schemas.ScanOut, status_code=201)
def create_scan(
    scan_in: schemas.ScanCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    product = db.get(models.Product, scan_in.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    active_rules = _active_rule_version(db)
    scan = models.Scan(
        product_id=scan_in.product_id,
        created_by_id=current_user.id,
        image_path=scan_in.image_path,
        status=models.ScanStatus.PENDING,
        # Stamp every new scan with whichever rule config is active right now,
        # so historical reports stay accurate even if rules are amended later.
        rule_version_id=active_rules.id if active_rules else None,
        calibration_px_per_mm=scan_in.calibration_px_per_mm,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


@router.get("", response_model=list[schemas.ScanOut])
def list_scans(
    status: models.ScanStatus | None = None,
    product_id: str | None = None,
    created_by_id: str | None = None,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """List scans, optionally filtered by status/product/inspector — the dashboard's main feed (Step 6)."""
    query = db.query(models.Scan)
    if status:
        query = query.filter(models.Scan.status == status)
    if product_id:
        query = query.filter(models.Scan.product_id == product_id)
    if created_by_id:
        query = query.filter(models.Scan.created_by_id == created_by_id)
    return query.order_by(models.Scan.created_at.desc()).all()


@router.get("/{scan_id}", response_model=schemas.ScanOut)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.patch("/{scan_id}", response_model=schemas.ScanOut)
def update_scan_status(
    scan_id: str,
    scan_in: schemas.ScanUpdate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(
        require_role(models.UserRole.SUPERVISOR, models.UserRole.ADMIN)
    ),
):
    """Manual status transition (e.g. mark RESOLVED or ESCALATED), or setting the
    calibration Step 5's font-size checks need — supervisor/admin only."""
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan_in.status is not None:
        scan.status = scan_in.status
    if scan_in.calibration_px_per_mm is not None:
        scan.calibration_px_per_mm = scan_in.calibration_px_per_mm
        _run_compliance_evaluation(db, scan)
    db.commit()
    db.refresh(scan)
    return scan


@router.post("/{scan_id}/evaluate", response_model=schemas.ScanOut)
def evaluate_scan_endpoint(
    scan_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """
    Re-runs the Step 5 compliance engine against this scan's current
    extracted_fields and calibration, without re-uploading the image —
    use this after an inspector corrects extracted_fields directly.
    """
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.extracted_fields or "fields" not in scan.extracted_fields:
        raise HTTPException(status_code=400, detail="Scan has no extracted fields yet — upload an image first.")
    _run_compliance_evaluation(db, scan)
    db.commit()
    db.refresh(scan)
    return scan


@router.post("/{scan_id}/image", response_model=schemas.ScanOut)
def upload_scan_image(
    scan_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """
    Accepts a label photo for an existing scan, runs it through the OCR
    & extraction pipeline (preprocess -> OCR -> field classification),
    stores the structured result on the scan record, and then runs the
    Step 5 compliance engine against it (writing Violation rows and the
    scan's compliance_review summary). If no calibration has been set yet,
    font-size checks are skipped and flagged as needing one, rather than
    silently passed.
    """
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    stored_name = f"{uuid.uuid4()}{ext}"
    stored_path = os.path.join(STORAGE_DIR, stored_name)
    with open(stored_path, "wb") as f:
        f.write(file.file.read())

    scan.image_path = stored_name
    scan.status = models.ScanStatus.PROCESSING
    db.commit()

    try:
        result = process_label_image(stored_path)
        scan.extracted_fields = result
        scan.status = models.ScanStatus.REVIEW
        _run_compliance_evaluation(db, scan)
    except Exception as exc:
        # Extraction failures shouldn't crash the request — surface them
        # on the scan record so an inspector can see it needs a re-upload
        # or manual entry, rather than losing the scan silently.
        scan.extracted_fields = {"error": str(exc)}
        scan.status = models.ScanStatus.PENDING

    db.commit()
    db.refresh(scan)
    return scan


@router.post("/{scan_id}/reprocess", response_model=schemas.ScanOut)
def reprocess_scan_image(
    scan_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """
    Re-runs the OCR & extraction pipeline on the scan's existing stored image.
    Useful when upgrading OCR/classifier logic or recovering from an earlier extraction failure.
    """
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.image_path:
        raise HTTPException(status_code=400, detail="Scan has no image to process — upload an image first.")

    stored_path = os.path.join(STORAGE_DIR, scan.image_path)
    if not os.path.exists(stored_path):
        raise HTTPException(status_code=404, detail="Scan image file not found on disk.")

    scan.status = models.ScanStatus.PROCESSING
    db.commit()

    try:
        result = process_label_image(stored_path)
        scan.extracted_fields = result
        scan.status = models.ScanStatus.REVIEW
        _run_compliance_evaluation(db, scan)
    except Exception as exc:
        scan.extracted_fields = {"error": str(exc)}
        scan.status = models.ScanStatus.PENDING

    db.commit()
    db.refresh(scan)
    return scan


@router.delete("/{scan_id}", status_code=204)
def delete_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    """Admin-only, and rare in practice — scans are compliance history, not scratch data."""
    scan = db.get(models.Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    db.delete(scan)
    db.commit()


# Rule evaluation against rules/legal_metrology_rules.json now runs
# automatically after upload (and on demand via POST /{scan_id}/evaluate
# and PATCH calibration updates above) — see ../compliance/engine.py.
# See routers/violations.py for the violations triage surface, and
# routers/rule_versions.py for tracking which rule config a scan was
# evaluated against.
