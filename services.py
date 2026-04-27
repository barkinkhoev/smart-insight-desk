import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any
import uuid

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError, RateLimitError

from database import SessionLocal
from models import Insight, InsightSource, InsightStatus, ReplyHistory
from schemas import FeedbackRequest


BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_BASE_PATH = BASE_DIR / "knowledge_base.txt"
MAX_REPLY_LENGTH = 250


DEFAULT_KNOWLEDGE_BASE = """Правила ответов студии:
1. Всегда отвечай вежливо и кратко.
2. Для негативных отзывов сначала признай проблему, затем предложи помощь или следующий шаг.
3. Для позитивных отзывов поблагодари клиента и пригласи заглянуть снова.
4. Не спорь с клиентом и не давай невыполнимых обещаний.
5. Избегай лишней воды, маркетинговых штампов и слишком длинных ответов.
6. Ответ должен быть полезным, человечным и умещаться в 250 символов.
"""


FEEDBACK_REPLY_SYSTEM_PROMPT = (
    "Ты — профессиональный менеджер по работе с клиентами. "
    "Напиши вежливый, краткий и полезный ответ на отзыв. "
    "Если рейтинг низкий — отработай негатив. "
    "Если высокий — поблагодари и предложи заглянуть в магазин еще раз. "
    "Ответ должен быть коротким, до 250 символов."
)


load_dotenv(dotenv_path=BASE_DIR / ".env")

_api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=_api_key) if _api_key else None


def ensure_knowledge_base() -> None:
    if not KNOWLEDGE_BASE_PATH.exists():
        KNOWLEDGE_BASE_PATH.write_text(DEFAULT_KNOWLEDGE_BASE, encoding="utf-8")


def read_knowledge_base() -> str:
    ensure_knowledge_base()
    return KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8").strip()


def _trim_reply(reply_text: str) -> str:
    reply_text = reply_text.strip()
    if len(reply_text) <= MAX_REPLY_LENGTH:
        return reply_text
    return reply_text[: MAX_REPLY_LENGTH - 1].rstrip() + "…"


def _normalize_text_for_insight(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    normalized = re.sub(r"[^\w\s\u0400-\u04FF-]", "", normalized, flags=re.UNICODE)
    return normalized


def _map_platform_to_source(platform: str) -> InsightSource:
    mapping = {
        "WB": InsightSource.WB,
        "OZON": InsightSource.OZON,
        "VK": InsightSource.VK,
        "TG": InsightSource.TG,
    }
    normalized = platform.strip().upper()
    return mapping.get(normalized, InsightSource.MANUAL)


def _heuristic_sentiment_and_pain(feedback: FeedbackRequest) -> tuple[float, str]:
    rating = feedback.rating
    if rating is None:
        return 0.0, "feedback"
    if rating <= 2:
        return -0.7, "negative_feedback"
    if rating >= 4:
        return 0.7, "positive_feedback"
    return 0.0, "neutral_feedback"


def _fallback_reply(feedback: FeedbackRequest) -> str:
    rating = feedback.rating
    if rating is not None and rating <= 2:
        text = (
            "Сожалеем, что опыт оказался неудачным. Спасибо за обратную связь — "
            "передадим её команде и постараемся помочь."
        )
    elif rating is not None and rating >= 4:
        text = (
            "Спасибо за отзыв! Очень рады, что вам понравилось. "
            "Будем рады видеть вас снова в магазине."
        )
    else:
        text = (
            "Спасибо за обратную связь! Мы передали комментарий команде и "
            "постараемся сделать сервис лучше."
        )
    return _trim_reply(text)


def _extract_reply_text(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("OpenAI returned JSON, but not an object.")

    reply_text = payload.get("reply_text")
    if not isinstance(reply_text, str) or not reply_text.strip():
        raise ValueError('OpenAI response is missing a valid "reply_text".')

    return _trim_reply(reply_text)


async def generate_ai_reply(feedback: FeedbackRequest) -> str:
    knowledge = read_knowledge_base()

    if client is None:
        return _fallback_reply(feedback)

    user_prompt_parts = [
        f"Используя эти правила: {knowledge}",
        f"Ответь на отзыв: {feedback.text}",
        f"Платформа: {feedback.platform}",
    ]
    if feedback.rating is not None:
        user_prompt_parts.append(f"Рейтинг: {feedback.rating}")
    if feedback.item_name:
        user_prompt_parts.append(f"Название товара/поста: {feedback.item_name}")

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": FEEDBACK_REPLY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "\n".join(user_prompt_parts),
                },
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError:
        return _fallback_reply(feedback)
    except OpenAIError:
        return _fallback_reply(feedback)

    content = response.choices[0].message.content if response.choices else None
    if not content:
        return _fallback_reply(feedback)

    try:
        return _extract_reply_text(content)
    except ValueError:
        return _fallback_reply(feedback)


def save_ai_reply_to_db(feedback: FeedbackRequest, ai_response: str) -> None:
    db = SessionLocal()
    try:
        sentiment_score, pain_point = _heuristic_sentiment_and_pain(feedback)
        insight = Insight(
            id=str(uuid.uuid4()),
            source=_map_platform_to_source(feedback.platform),
            raw_text=feedback.text,
            normalized_text=_normalize_text_for_insight(feedback.text),
            sentiment_score=sentiment_score,
            pain_point=pain_point,
            status=InsightStatus.DRAFT,
            duplicate_of=None,
        )
        db.add(insight)
        db.flush()

        record = ReplyHistory(
            insight_id=insight.id,
            ai_response=ai_response,
            feedback_comment=feedback.text,
            is_approved=False,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()
