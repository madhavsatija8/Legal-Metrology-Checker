"""initial schema: users, products, scans, violations, rule_versions

Revision ID: 0001
Revises:
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = sa.Enum("inspector", "supervisor", "admin", name="userrole")
scan_status = sa.Enum("pending", "processing", "review", "resolved", "escalated", name="scanstatus")
violation_severity = sa.Enum("minor", "major", "critical", name="violationseverity")


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    scan_status.create(bind, checkfirst=True)
    violation_severity.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="inspector"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("manufacturer_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "rule_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version_label", sa.String(), nullable=False),
        sa.Column("source_file_hash", sa.String(), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false()),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_by_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("status", scan_status, nullable=False, server_default="pending"),
        sa.Column("extracted_fields", sa.JSON(), nullable=True),
        sa.Column("rule_version_id", sa.String(), sa.ForeignKey("rule_versions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "violations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scan_id", sa.String(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("citation", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", violation_severity, nullable=False),
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.false()),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("violations")
    op.drop_table("scans")
    op.drop_table("rule_versions")
    op.drop_table("products")
    op.drop_table("users")

    bind = op.get_bind()
    violation_severity.drop(bind, checkfirst=True)
    scan_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
