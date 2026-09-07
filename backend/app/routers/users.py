from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_role
from ..database import get_db

router = APIRouter(prefix="/users", tags=["users"])

# Account creation stays on POST /auth/register (self-serve signup). This
# router is the admin-only surface for managing who has access and what
# role they hold — required for a real inspector/supervisor/admin rollout.


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: str,
    user_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    """Change a user's role, name, or deactivate their account (e.g. an inspector leaving the department)."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in user_in.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
