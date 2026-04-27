import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InsightSource(str, Enum):
    WB = "WB"
    OZON = "OZON"
    VK = "VK"
    TG = "TG"
    MANUAL = "MANUAL"


class InsightStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    POSTED = "POSTED"


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("ix_insights_source", "source"),
        Index("ix_insights_status", "status"),
        Index("ix_insights_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source: Mapped[InsightSource] = mapped_column(
        SAEnum(InsightSource, name="insight_source", native_enum=False),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    pain_category: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InsightStatus] = mapped_column(
        SAEnum(InsightStatus, name="insight_status", native_enum=False),
        nullable=False,
        default=InsightStatus.DRAFT,
    )
    delivery_failed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("insights.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    duplicate_parent = relationship(
        "Insight",
        remote_side="Insight.id",
        foreign_keys=[duplicate_of],
        uselist=False,
    )
    status_logs = relationship(
        "StatusLog",
        back_populates="insight",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


__all__ = ["Insight", "InsightSource", "InsightStatus"]
