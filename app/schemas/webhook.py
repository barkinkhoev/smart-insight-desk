from typing import Optional

from pydantic import Field, field_validator

from app.schemas.insight import CleanInputModel


class WBWebhookRequest(CleanInputModel):
    text: str = Field(min_length=1, max_length=4000)
    item_name: Optional[str] = Field(default=None, max_length=255)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    review_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("text", "item_name", mode="before")
    @classmethod
    def strip_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value
