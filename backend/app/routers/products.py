from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..database import get_db

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=schemas.ProductOut, status_code=201)
def create_product(
    product_in: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    product = models.Product(**product_in.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[schemas.ProductOut])
def list_products(
    q: str | None = None,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """List products, optionally filtered by a case-insensitive name/brand search (`?q=`)."""
    query = db.query(models.Product)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Product.name.ilike(like)) | (models.Product.brand.ilike(like))
        )
    return query.order_by(models.Product.created_at.desc()).all()


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: str,
    product_in: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(
        require_role(models.UserRole.SUPERVISOR, models.UserRole.ADMIN)
    ),
):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in product_in.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN)),
):
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.scans:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a product with existing scans; it's part of the compliance history.",
        )
    db.delete(product)
    db.commit()
