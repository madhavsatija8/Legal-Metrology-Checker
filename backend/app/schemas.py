from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from .models import ScanStatus, UserRole, ViolationSeverity


# ---- Auth / users ----

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.INSPECTOR


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Admin-only: change a user's role or activate/deactivate their account."""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Products ----

class ProductCreate(BaseModel):
    name: str
    barcode: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer_name: Optional[str] = None
    # Compliance-engine context (Step 5) — drives conditional rules like
    # country-of-origin (imports only) and the 2mm-vs-1mm letter height
    # threshold (surface-treated declarations).
    is_imported: bool = False
    surface_treatment: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer_name: Optional[str] = None
    is_imported: Optional[bool] = None
    surface_treatment: Optional[str] = None


class ProductOut(ProductCreate):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Rule versions ----

class RuleVersionOut(BaseModel):
    id: str
    version_label: str
    source_file_hash: str
    is_active: bool
    activated_at: datetime

    class Config:
        from_attributes = True


# ---- Violations ----

class ViolationOut(BaseModel):
    id: str
    scan_id: str
    rule_id: str
    citation: Optional[str] = None
    description: str
    severity: ViolationSeverity
    needs_review: bool
    is_resolved: bool
    resolution_note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ViolationUpdate(BaseModel):
    """Inspector/supervisor workflow: confirm, annotate, or resolve a violation."""
    is_resolved: Optional[bool] = None
    resolution_note: Optional[str] = None
    severity: Optional[ViolationSeverity] = None


# ---- Scans ----

class ScanCreate(BaseModel):
    product_id: str
    image_path: Optional[str] = None  # populated once upload/storage is wired in Step 4
    calibration_px_per_mm: Optional[float] = None  # can also be set/updated later via PATCH, once measured


class ScanUpdate(BaseModel):
    """Manual status transitions an inspector/supervisor can make (e.g. escalate, resolve),
    plus setting the pixels-per-mm calibration Step 5's font-size checks need. Setting
    calibration_px_per_mm re-runs the compliance engine against the scan's existing
    extracted_fields."""
    status: Optional[ScanStatus] = None
    calibration_px_per_mm: Optional[float] = None


class ScanOut(BaseModel):
    id: str
    product_id: str
    created_by_id: str
    status: ScanStatus
    image_path: Optional[str]
    extracted_fields: Optional[dict]
    calibration_px_per_mm: Optional[float] = None
    compliance_review: Optional[dict] = None
    rule_version_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    violations: list[ViolationOut] = []

    class Config:
        from_attributes = True
