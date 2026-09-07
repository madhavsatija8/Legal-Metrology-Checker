from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..database import get_db

router = APIRouter(prefix="/violations", tags=["violations"])

# Violation rows are created by the Step 5 compliance engine
# (../compliance/engine.py, invoked from routers/scans.py) — it reads
# rules/legal_metrology_rules.json + a scan's extracted_fields and writes
# these automatically on upload/evaluate. This router is the read/triage
# surface: list & filter across all scans for the dashboard (Step 6), and
# let an inspector/supervisor confirm, annotate, or resolve a violation.


@router.get("", response_model=list[schemas.ViolationOut])
def list_violations(
    scan_id: str | None = None,
    rule_id: str | None = None,
    severity: models.ViolationSeverity | None = None,
    is_resolved: bool | None = None,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Violation)
    if scan_id:
        query = query.filter(models.Violation.scan_id == scan_id)
    if rule_id:
        query = query.filter(models.Violation.rule_id == rule_id)
    if severity:
        query = query.filter(models.Violation.severity == severity)
    if is_resolved is not None:
        query = query.filter(models.Violation.is_resolved == is_resolved)
    return query.order_by(models.Violation.created_at.desc()).all()


@router.get("/{violation_id}", response_model=schemas.ViolationOut)
def get_violation(
    violation_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    violation = db.get(models.Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    return violation


@router.patch("/{violation_id}", response_model=schemas.ViolationOut)
def update_violation(
    violation_id: str,
    violation_in: schemas.ViolationUpdate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(
        require_role(models.UserRole.INSPECTOR, models.UserRole.SUPERVISOR, models.UserRole.ADMIN)
    ),
):
    """Confirm, override the severity of, or resolve a violation once the seller corrects the label."""
    violation = db.get(models.Violation, violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    for field, value in violation_in.model_dump(exclude_unset=True).items():
        setattr(violation, field, value)
    db.commit()
    db.refresh(violation)
    return violation
