import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..database import get_db
from ..rules_loader import read_rules_raw

router = APIRouter(prefix="/rule-versions", tags=["rule-versions"])


def _hash_rules_file() -> tuple[str, str]:
    """Returns (version_label, sha256_hash) read straight from the rules JSON."""
    raw = read_rules_raw()
    data = json.loads(raw)
    version_label = data.get("version_label", "unknown")
    file_hash = hashlib.sha256(raw).hexdigest()
    return version_label, file_hash


@router.get("", response_model=list[schemas.RuleVersionOut])
def list_rule_versions(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    return db.query(models.RuleVersion).order_by(models.RuleVersion.activated_at.desc()).all()


@router.get("/active", response_model=schemas.RuleVersionOut)
def get_active_rule_version(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    active = db.query(models.RuleVersion).filter(models.RuleVersion.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404,
            detail="No active rule version yet — POST /rule-versions/sync-from-file as an admin first.",
        )
    return active


@router.post("/sync-from-file", response_model=schemas.RuleVersionOut, status_code=201)
def sync_rule_version_from_file(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    """
    Reads rules/legal_metrology_rules.json, and if its contents don't match
    any known RuleVersion, registers a new one and makes it active (so new
    scans get stamped with it). This is how a rule amendment gets adopted:
    edit the JSON, then call this endpoint — never hand-edit the DB.
    """
    version_label, file_hash = _hash_rules_file()

    existing = (
        db.query(models.RuleVersion).filter(models.RuleVersion.source_file_hash == file_hash).first()
    )
    if existing:
        if not existing.is_active:
            db.query(models.RuleVersion).update({models.RuleVersion.is_active: False})
            existing.is_active = True
            db.commit()
            db.refresh(existing)
        return existing

    db.query(models.RuleVersion).update({models.RuleVersion.is_active: False})
    new_version = models.RuleVersion(
        version_label=version_label,
        source_file_hash=file_hash,
        is_active=True,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version
