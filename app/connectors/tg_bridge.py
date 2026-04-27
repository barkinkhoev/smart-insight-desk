import os
import html
import logging
from typing import Any

import httpx

from app.core.database import AsyncSessionLocal
from app.models import Insight

logger = logging.getLogger(__name__)


def _get_token() -> str | None:
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_TOKEN")
        or os.getenv("ORCHESTRATOR_BOT_TOKEN")
    )


def _get_chat_id() -> int | None:
    raw_value = os.getenv("TELEGRAM_CHAT_ID")
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _get_thread_id() -> int | None:
    raw_value = os.getenv("TELEGRAM_THREAD_ID")
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


async def _set_delivery_failed(insight_id: Any, failed: bool) -> None:
    async with AsyncSessionLocal() as session:
        insight = await session.get(Insight, insight_id)
        if insight is None:
            return
        insight.delivery_failed = failed
        await session.commit()


def _build_message(insight: Insight, ai_reply: str) -> str:
    escaped_text = html.escape(insight.raw_text)
    escaped_reply = html.escape(ai_reply)
    return (
        "<b>Smart Insight Desk</b>\n"
        "<b>Карточка инсайта</b>\n\n"
        f"<b>Источник:</b> {insight.source.value}\n"
        f"<b>Текст:</b> {escaped_text}\n"
        f"<b>Тональность:</b> {insight.sentiment_score:.2f}\n"
        f"<b>Боль:</b> {insight.pain_category}\n"
        f"<b>AI-ответ:</b> {escaped_reply}\n"
        f"<b>Статус:</b> {insight.status.value}"
    )


def _build_buttons(insight_id: Any) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Одобрить", "callback_data": f"insight:approve:{insight_id}"},
                {"text": "❌ Отклонить", "callback_data": f"insight:reject:{insight_id}"},
            ]
        ]
    }


async def send_approval_card(insight: Insight) -> None:
    ai_reply = getattr(insight, "ai_reply", None)
    await send_insight_notification(insight, ai_reply)


async def send_insight_notification(insight: Insight, ai_reply: str | None = None) -> None:
    token = _get_token()
    chat_id = _get_chat_id()
    thread_id = _get_thread_id()
    if not token or not chat_id:
        await _set_delivery_failed(insight.id, True)
        return

    if not ai_reply or not ai_reply.strip():
        ai_reply = "Спасибо за ваш отзыв, мы уже изучаем детали"

    logger.debug("DEBUG: Попытка отправки в CHAT_ID: %s", chat_id)

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": _build_message(insight, ai_reply),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": _build_buttons(insight.id),
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception("Telegram sendMessage failed with HTTP status error", exc_info=exc)
        await _set_delivery_failed(insight.id, True)
        return
    except httpx.HTTPError:
        logger.exception("Telegram sendMessage failed with network error")
        await _set_delivery_failed(insight.id, True)
        return

    await _set_delivery_failed(insight.id, False)


async def edit_telegram_message(
    *,
    message_id: int,
    new_text: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    token = _get_token()
    chat_id = _get_chat_id()
    if not token or not chat_id:
        return

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{token}/editMessageText"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError:
        return
