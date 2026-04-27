from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str | None = None


class TelegramMessage(BaseModel):
    message_id: int | None = None
    chat: TelegramChat | None = None
    text: str | None = None


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    from_user: TelegramUser = Field(alias="from")
    data: str | None = None
    message: TelegramMessage | None = None


class TelegramUpdate(BaseModel):
    update_id: int
    callback_query: Optional[TelegramCallbackQuery] = None


class TelegramWebhookSetRequest(BaseModel):
    webhook_url: str | None = Field(
        default=None,
        description="Public webhook URL. Defaults to APP_PUBLIC_BASE_URL/api/v1/telegram/webhook",
    )
    secret_token: str | None = Field(default=None, max_length=255)
    drop_pending_updates: bool = True


class TelegramWebhookSetResponse(BaseModel):
    ok: bool
    description: str | None = None
    result: dict | None = None
