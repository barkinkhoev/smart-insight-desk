"""add delivery failed to insights

Revision ID: 0004_add_delivery_failed_to_insights
Revises: 0003_create_status_logs_table
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_delivery_failed_to_insights"
down_revision = "0003_create_status_logs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("insights")}
    if "delivery_failed" not in columns:
        op.add_column(
            "insights",
            sa.Column("delivery_failed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("insights", "delivery_failed")
