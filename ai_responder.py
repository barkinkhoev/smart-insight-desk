import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError, RateLimitError


SYSTEM_PROMPT = """
Ты — вежливый и профессиональный саппорт-ассистент ИТ-стартапа.
Твоя задача — на основе комментария пользователя сгенерировать короткий, полезный и уважительный ответ.

Правила:
- Отвечай по-русски.
- Тон: вежливый, спокойный, человечный, без канцелярита.
- Не спорь с пользователем.
- Не обещай того, чего не можешь выполнить.
- Если в комментарии есть жалоба, сначала признай проблему, затем мягко предложи помощь или следующий шаг.
- Верни ТОЛЬКО JSON без markdown и без лишнего текста.

Формат ответа:
{
  "response_text": "готовый вежливый ответ пользователю"
}
""".strip()

FEEDBACK_REPLY_SYSTEM_PROMPT = """
Ты — профессиональный менеджер по работе с клиентами. Напиши вежливый, краткий и полезный ответ на отзыв.
Если рейтинг низкий — отработай негатив.
Если высокий — поблагодари и предложи заглянуть в магазин еще раз.
Верни ТОЛЬКО JSON без markdown и без лишнего текста.

Формат ответа:
{
  "response_text": "готовый ответ"
}
""".strip()


load_dotenv()

_api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=_api_key) if _api_key else None


def _extract_payload(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("OpenAI returned JSON, but not an object.")

    response_text = payload.get("response_text")
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError('OpenAI response is missing a valid "response_text".')

    return {"response_text": response_text.strip()}


async def generate_polite_response(comment_text: str) -> dict[str, Any]:
    text = comment_text.strip()
    if not text:
        raise ValueError("comment_text is empty.")

    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Сгенерируй вежливый ответ на комментарий:\n\n{text}",
                },
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        raise RuntimeError("OpenAI rate limit or quota exceeded.") from exc
    except OpenAIError as exc:
        raise RuntimeError("OpenAI API is unavailable or returned an error.") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise ValueError("OpenAI returned an empty response.")

    return _extract_payload(content)


async def generate_feedback_reply(
    text: str,
    platform: str,
    rating: int | None = None,
    item_name: str | None = None,
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    user_parts = [
        f"Платформа: {platform}",
        f"Отзыв: {text.strip()}",
    ]
    if rating is not None:
        user_parts.append(f"Рейтинг: {rating}")
    if item_name:
        user_parts.append(f"Товар/пост: {item_name.strip()}")

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": FEEDBACK_REPLY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "\n".join(user_parts),
                },
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        raise RuntimeError("OpenAI rate limit or quota exceeded.") from exc
    except OpenAIError as exc:
        raise RuntimeError("OpenAI API is unavailable or returned an error.") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise ValueError("OpenAI returned an empty response.")

    return _extract_payload(content)
