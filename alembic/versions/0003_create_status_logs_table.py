"""create status logs table

Revision ID: 0003_create_status_logs_table
Revises: 0002_create_insights_table
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_create_status_logs_table"
down_revision = "0002_create_insights_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "status_logs" not in tables:
        op.create_table(
            "status_logs",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("insight_id", sa.Uuid(), nullable=False),
            sa.Column(
                "old_status",
                sa.Enum("DRAFT", "PENDING", "POSTED", name="status_log_old_status", native_enum=False),
                nullable=False,
            ),
            sa.Column(
                "new_status",
                sa.Enum("DRAFT", "PENDING", "POSTED", name="status_log_new_status", native_enum=False),
                nullable=False,
            ),
            sa.Column("changed_by", sa.String(length=255), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["insight_id"], ["insights.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_status_logs_insight_id", "status_logs", ["insight_id"])
        op.create_index("ix_status_logs_changed_at", "status_logs", ["changed_at"])


def downgrade() -> None:
    op.drop_index("ix_status_logs_changed_at", table_name="status_logs")
    op.drop_index("ix_status_logs_insight_id", table_name="status_logs")
    op.drop_table("status_logs")
