from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..database import get_db
from ..seed_products import get_seed_data
from ..services.product_lookup import lookup_product_by_barcode

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/lookup", response_model=schemas.ProductOut)
def lookup_product(
    barcode: str,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """
    Looks up a product by barcode (GTIN / EAN-13). Checks local database first,
    and falls back to live Open Food Facts India API lookup to auto-register new items.
    """
    clean_barcode = re.sub(r"\D", "", barcode)
    if not clean_barcode:
        raise HTTPException(status_code=400, detail="Please enter a valid numeric barcode.")

    # 1. Check local database
    existing = db.query(models.Product).filter(models.Product.barcode == clean_barcode).first()
    if existing:
        return existing

    # 2. Live lookup from Open Food Facts India API
    external_data = lookup_product_by_barcode(clean_barcode)
    if not external_data:
        raise HTTPException(
            status_code=404,
            detail=f"Barcode {clean_barcode} not found in database or online registries.",
        )

    # 3. Auto-register in database
    product = models.Product(**external_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/seed", status_code=200)
def seed_products(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(require_role(models.UserRole.ADMIN, models.UserRole.SUPERVISOR)),
):
    """
    Bulk-inserts the curated Indian product catalogue (~500 products).
    Skips products that already exist (matched by barcode, or name+brand).
    Returns a count of newly inserted vs already-present products.
    """
    inserted = 0
    skipped = 0
    for entry in get_seed_data():
        # Deduplicate by barcode (if present) or name+brand
        if entry.get("barcode"):
            exists = db.query(models.Product).filter(models.Product.barcode == entry["barcode"]).first()
        else:
            exists = (
                db.query(models.Product)
                .filter(
                    models.Product.name == entry["name"],
                    models.Product.brand == entry.get("brand"),
                )
                .first()
            )
        if exists:
            skipped += 1
            continue
        product = models.Product(
            name=entry["name"],
            brand=entry.get("brand"),
            category=entry.get("category"),
            manufacturer_name=entry.get("manufacturer_name"),
            is_imported=entry.get("is_imported", False),
            barcode=entry.get("barcode"),
        )
        db.add(product)
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "total_seed_entries": inserted + skipped}


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
            (models.Product.name.ilike(like))
            | (models.Product.brand.ilike(like))
            | (models.Product.barcode.ilike(like))
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
