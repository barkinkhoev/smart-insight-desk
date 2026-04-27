"""create insight and reply history tables

Revision ID: 0001_create_insight_and_reply_history
Revises: 
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_create_insight_and_reply_history"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    create_replies_table = "replies_history" not in tables

    if "replies_history" in tables:
        existing_columns = {column["name"] for column in inspector.get_columns("replies_history")}
        expected_columns = {"id", "insight_id", "ai_response", "feedback_comment", "is_approved"}
        if not expected_columns.issubset(existing_columns):
            op.rename_table("replies_history", "replies_history_legacy")
            create_replies_table = True

    if "insights" not in tables:
        op.create_table(
            "insights",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "source",
                sa.Enum("WB", "OZON", "VK", "TG", "MANUAL", name="insight_source", native_enum=False),
                nullable=False,
            ),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("normalized_text", sa.Text(), nullable=False),
            sa.Column("sentiment_score", sa.Float(), nullable=False),
            sa.Column("pain_point", sa.String(length=255), nullable=False),
            sa.Column(
                "status",
                sa.Enum("DRAFT", "PENDING", "POSTED", name="insight_status", native_enum=False),
                nullable=False,
            ),
            sa.Column("duplicate_of", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["duplicate_of"], ["insights.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_insights_source", "insights", ["source"])
        op.create_index("ix_insights_status", "insights", ["status"])
        op.create_index("ix_insights_created_at", "insights", ["created_at"])

    if create_replies_table:
        op.create_table(
            "replies_history",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("insight_id", sa.String(length=36), nullable=False),
            sa.Column("ai_response", sa.Text(), nullable=False),
            sa.Column("feedback_comment", sa.Text(), nullable=False),
            sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["insight_id"], ["insights.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_replies_history_insight_id", "replies_history", ["insight_id"])


def downgrade() -> None:
    op.drop_index("ix_replies_history_insight_id", table_name="replies_history")
    op.drop_table("replies_history")
    op.drop_index("ix_insights_created_at", table_name="insights")
    op.drop_index("ix_insights_status", table_name="insights")
    op.drop_index("ix_insights_source", table_name="insights")
    op.drop_table("insights")
