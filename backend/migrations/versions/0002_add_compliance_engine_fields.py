"""step 5: compliance engine fields (product context, scan calibration/review, violation confidence)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("is_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("products", sa.Column("surface_treatment", sa.String(), nullable=True))

    op.add_column("scans", sa.Column("calibration_px_per_mm", sa.Float(), nullable=True))
    op.add_column("scans", sa.Column("compliance_review", sa.JSON(), nullable=True))

    op.add_column(
        "violations",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("violations", "needs_review")
    op.drop_column("scans", "compliance_review")
    op.drop_column("scans", "calibration_px_per_mm")
    op.drop_column("products", "surface_treatment")
    op.drop_column("products", "is_imported")
