from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketCreate(BaseModel):
    text: str = Field(min_length=10, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
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
    tickets: List[TicketRead]
