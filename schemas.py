from datetime import datetime
import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, AliasChoices, field_validator


def _clean_text(value):
    if not isinstance(value, str):
        return value

    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        raise ValueError("Text cannot be empty.")

    if len(re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)) == 0:
        raise ValueError("Text contains only noise.")

    if re.fullmatch(r"(.)\1{6,}", normalized):
        raise ValueError("Text looks like repeated noise.")

    return normalized


class CleanInputModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def clean_incoming_strings(cls, value):
        return _clean_text(value)


class AnalysisRequest(CleanInputModel):
    source: str = Field(min_length=1, max_length=128)
    text: str = Field(
        min_length=10,
        max_length=2000,
        validation_alias=AliasChoices("text", "raw_text"),
    )
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value):
        if not isinstance(value, str):
            return value

        normalized = unicodedata.normalize("NFKC", value).strip()
        if not normalized:
            raise ValueError("source cannot be empty.")
        return normalized


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sentiment_score: float
    pain_point: str
    source: str
    timestamp: datetime


class HistoryResponse(BaseModel):
    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int


class RespondRequest(CleanInputModel):
    comment_text: str = Field(min_length=1, max_length=2000)


class RespondResponse(BaseModel):
    response_text: str


class FeedbackRequest(CleanInputModel):
    text: str = Field(min_length=1, max_length=2000)
    platform: str = Field(min_length=2, max_length=16)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    item_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value):
        if not isinstance(value, str):
            return value

        normalized = unicodedata.normalize("NFKC", value).strip().upper()
        mapping = {
            "WB": "WB",
            "OZON": "Ozon",
            "VK": "VK",
            "TG": "TG",
        }
        if normalized not in mapping:
            raise ValueError("platform must be one of: WB, Ozon, VK, TG.")
        return mapping[normalized]

    @field_validator("item_name", mode="before")
    @classmethod
    def strip_item_name(cls, value):
        if isinstance(value, str):
            return _clean_text(value)
        return value


class FeedbackReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    insight_id: str
    ai_response: str
    feedback_comment: str
    is_approved: bool


class GenerateReplyResponse(BaseModel):
    reply_text: str


class InsightUpsertRequest(CleanInputModel):
    source: str = Field(min_length=2, max_length=16)
    raw_text: str = Field(min_length=1, max_length=2000)
    normalized_text: str = Field(min_length=1, max_length=2000)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    pain_point: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=16)
    duplicate_of: Optional[str] = Field(default=None, max_length=36)


# Backward-compatible schemas for the existing MVP routes.
class TicketCreate(BaseModel):
    text: str = Field(min_length=10, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_ticket_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    status: str
    sentiment_score: float
    pain_point: str
    created_at: datetime


class AnalyticsResponse(BaseModel):
    total_tickets: int
    average_sentiment_score: Optional[float]
    tickets: list[TicketRead]
