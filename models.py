from datetime import datetime, timezone
import uuid
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, SessionLocal, engine


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


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"
    __table_args__ = (
        Index("ix_analysis_history_source", "source"),
        Index("ix_analysis_history_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    raw_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    pain_point: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("ix_insights_source", "source"),
        Index("ix_insights_status", "status"),
        Index("ix_insights_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[InsightSource] = mapped_column(
        SAEnum(InsightSource, name="insight_source", native_enum=False),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    pain_point: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InsightStatus] = mapped_column(
        SAEnum(InsightStatus, name="insight_status", native_enum=False),
        nullable=False,
        default=InsightStatus.DRAFT,
    )
    duplicate_of: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("insights.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ReplyHistory(Base):
    __tablename__ = "replies_history"
    __table_args__ = (
        Index("ix_replies_history_insight_id", "insight_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    insight_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


class Ticket(Base):
    """Legacy model kept for backward compatibility with the current MVP routes."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    pain_point: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


__all__ = [
    "AnalysisHistory",
    "Base",
    "Insight",
    "InsightSource",
    "InsightStatus",
    "ReplyHistory",
    "SessionLocal",
    "Ticket",
    "engine",
]
