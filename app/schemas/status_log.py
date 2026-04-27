import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.insight import InsightStatus


class StatusLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    insight_id: uuid.UUID
    old_status: InsightStatus
    new_status: InsightStatus
    changed_by: str
    comment: str | None
    changed_at: datetime
