import re
import unicodedata
import uuid

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.insight import InsightSource, InsightStatus


def _validate_meaningful_text(value):
    if not isinstance(value, str):
        return value

    cleaned = unicodedata.normalize("NFKC", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("Text cannot be empty.")

    if not re.search(r"[A-Za-zА-Яа-я0-9]", cleaned):
        raise ValueError("Text cannot consist only of special characters.")

    return cleaned


class CleanInputModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def clean_any_text(cls, value):
        return _validate_meaningful_text(value)


class InsightCreate(BaseModel):
    source: InsightSource
    raw_text: str = Field(min_length=1, max_length=2000)
    normalized_text: str = Field(min_length=1, max_length=2000)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    pain_category: str = Field(min_length=1, max_length=255)
    status: InsightStatus = InsightStatus.DRAFT
    duplicate_of: uuid.UUID | None = None

    @field_validator("raw_text", "normalized_text", "pain_category", mode="before")
    @classmethod
    def clean_text_fields(cls, value):
        return _validate_meaningful_text(value)


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: InsightSource
    raw_text: str
    normalized_text: str
    sentiment_score: float
    pain_category: str
    status: InsightStatus
    delivery_failed: bool
    duplicate_of: uuid.UUID | None
    created_at: datetime
