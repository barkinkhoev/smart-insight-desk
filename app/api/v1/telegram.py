from __future__ import annotations

import os
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models import Insight, InsightStatus
from app.schemas.telegram import (
    TelegramUpdate,
    TelegramWebhookSetRequest,
    TelegramWebhookSetResponse,
)
from app.services.audit import log_status_change
from app.connectors.tg_bridge import edit_telegram_message


router = APIRouter(prefix="/api/v1", tags=["Telegram"])


def _get_token() -> str | None:
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")


def _get_public_base_url() -> str:
    return (
        os.getenv("APP_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or os.getenv("BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


async def _answer_callback_query(callback_query_id: str) -> None:
    token = _get_token()
    if not token:
        return

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(url, json=payload)
        except httpx.HTTPError:
            return


def _parse_action(data: str | None) -> tuple[str | None, UUID | None]:
    if not data:
        return None, None

    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "insight":
        return None, None

    action = parts[1].lower()
    try:
        insight_id = UUID(parts[2])
    except ValueError:
        return None, None

    return action, insight_id


def _action_to_status(action: str) -> InsightStatus | None:
    mapping = {
        "approve": InsightStatus.POSTED,
        "publish": InsightStatus.POSTED,
        "edit": InsightStatus.PENDING,
        "reject": InsightStatus.DRAFT,
        "trash": InsightStatus.DRAFT,
        "posted": InsightStatus.POSTED,
    }
    return mapping.get(action)


@router.post(
    "/telegram/set-webhook",
    response_model=TelegramWebhookSetResponse,
    tags=["Telegram"],
    summary="Set Telegram webhook for callback buttons",
)
async def set_telegram_webhook(payload: TelegramWebhookSetRequest):
    token = _get_token()
    if not token:
        raise HTTPException(status_code=503, detail="Telegram token is not configured.")

    webhook_url = (
        payload.webhook_url
        or f"{_get_public_base_url()}/api/v1/telegram/webhook"
    )

    request_payload: dict[str, object] = {
        "url": webhook_url,
        "drop_pending_updates": payload.drop_pending_updates,
    }
    if payload.secret_token:
        request_payload["secret_token"] = payload.secret_token

    url = f"https://api.telegram.org/bot{token}/setWebhook"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=request_payload)
        response.raise_for_status()

    body = response.json()
    return TelegramWebhookSetResponse(
        ok=bool(body.get("ok", False)),
        description=body.get("description"),
        result=body.get("result"),
    )


@router.post("/telegram/webhook")
async def telegram_webhook(
    update: TelegramUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    callback_query = update.callback_query
    if callback_query is None:
        return {"ok": True, "ignored": True}

    await _answer_callback_query(callback_query.id)

    action, insight_id = _parse_action(callback_query.data)
    if action is None or insight_id is None:
        raise HTTPException(status_code=400, detail="Unsupported callback data.")

    new_status = _action_to_status(action)
    if new_status is None:
        raise HTTPException(status_code=400, detail="Unsupported insight action.")

    insight = await db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found.")

    old_status = insight.status
    insight.status = new_status

    actor = callback_query.from_user.username or f"telegram_user:{callback_query.from_user.id}"
    comment = callback_query.message.text if callback_query.message and callback_query.message.text else "Telegram callback update"

    await log_status_change(
        db,
        insight=insight,
        old_status=old_status,
        new_status=new_status,
        changed_by=actor,
        comment=comment,
    )
    await db.commit()
    await db.refresh(insight)

    if action in {"approve", "publish"} and callback_query.message and callback_query.message.message_id is not None:
        await edit_telegram_message(
            message_id=callback_query.message.message_id,
            new_text="✅ <b>Опубликовано</b>",
            reply_markup=None,
        )

    return {
        "ok": True,
        "insight_id": str(insight.id),
        "old_status": old_status.value,
        "new_status": new_status.value,
    }
