import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.insight import InsightStatus


class StatusLog(Base):
    __tablename__ = "status_logs"
    __table_args__ = (
        Index("ix_status_logs_insight_id", "insight_id"),
        Index("ix_status_logs_changed_at", "changed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    insight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_status: Mapped[InsightStatus] = mapped_column(
        SAEnum(InsightStatus, name="status_log_old_status", native_enum=False),
        nullable=False,
    )
    new_status: Mapped[InsightStatus] = mapped_column(
        SAEnum(InsightStatus, name="status_log_new_status", native_enum=False),
        nullable=False,
    )
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    insight = relationship("Insight", back_populates="status_logs")


__all__ = ["StatusLog"]
