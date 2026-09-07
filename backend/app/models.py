import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    INSPECTOR = "inspector"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"          # uploaded, not yet processed
    PROCESSING = "processing"    # OCR / extraction running
    REVIEW = "review"            # extracted, awaiting inspector confirmation
    RESOLVED = "resolved"        # reviewed and closed
    ESCALATED = "escalated"      # sent up for enforcement action


class ViolationSeverity(str, enum.Enum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.INSPECTOR, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="created_by")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=True)
    manufacturer_name: Mapped[str] = mapped_column(String, nullable=True)

    # Compliance-engine context (Step 5). These drive conditional rules in
    # legal_metrology_rules.json (e.g. country-of-origin only applies if
    # imported; the 2mm-vs-1mm letter height threshold depends on surface
    # treatment) that OCR cannot reliably infer from the label text alone.
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    surface_treatment: Mapped[str] = mapped_column(String, nullable=True)  # e.g. "molded", "embossed", "blown" — None means an ordinary printed label

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="product")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    image_path: Mapped[str] = mapped_column(String, nullable=True)  # object storage key, wired in Step 4
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.PENDING)

    # Raw + structured extraction output from the OCR module (Step 4).
    # Kept as JSON for now since the schema will evolve as extraction improves.
    extracted_fields: Mapped[dict] = mapped_column(JSON, nullable=True)

    rule_version_id: Mapped[str] = mapped_column(ForeignKey("rule_versions.id"), nullable=True)

    # Inspector-supplied pixels-per-mm scale (from a reference object or a
    # manually measured package dimension). Font-size/readability rules
    # (Step 5) can't convert OCR'd pixel heights to mm without this, and
    # are skipped — not silently passed — until it's set.
    calibration_px_per_mm: Mapped[float] = mapped_column(Float, nullable=True)

    # Step 5 engine output that isn't a hard violation: exemption status
    # and "review_items" (missing calibration, rules still pending legal
    # verification, checks the pipeline can't automate yet, low-confidence
    # OCR matches). Kept separate from `violations` so the dashboard can
    # tell "the engine found a breach" apart from "the engine couldn't
    # decide and a human needs to look."
    compliance_review: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="scans")
    created_by: Mapped["User"] = relationship(back_populates="scans")
    rule_version: Mapped["RuleVersion"] = relationship(back_populates="scans")
    violations: Mapped[list["Violation"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), nullable=False)

    rule_id: Mapped[str] = mapped_column(String, nullable=False)  # references an id in legal_metrology_rules.json
    citation: Mapped[str] = mapped_column(String, nullable=True)  # e.g. "Rule 6(1)(a)", copied at write-time
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[ViolationSeverity] = mapped_column(Enum(ViolationSeverity), nullable=False)

    # Set by the Step 5 engine when the underlying OCR match was low-
    # confidence (e.g. unanchored keyword match) — the violation is a real
    # lead, but should read differently in the UI than a confident one.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    # Inspector workflow: a violation raised by the engine (Step 5) can be
    # confirmed as-is, overridden (e.g. false positive on OCR), or resolved
    # once the seller corrects the label. Kept here rather than only on the
    # parent Scan so the dashboard (Step 6) can filter/count at this level.
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_note: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scan: Mapped["Scan"] = relationship(back_populates="violations")


class RuleVersion(Base):
    """
    Tracks which version of rules/legal_metrology_rules.json a given scan
    was evaluated against, so historical compliance reports stay accurate
    even after the rule config is later amended/updated.
    """
    __tablename__ = "rule_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    version_label: Mapped[str] = mapped_column(String, nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # Exactly one row should be active at a time (enforced in the router,
    # not the DB, since SQLite/Postgres partial-unique-index syntax differs).
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="rule_version")
