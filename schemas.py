from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class TicketCreate(BaseModel):
    text: str


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
