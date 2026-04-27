import json
import os
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError, RateLimitError


SYSTEM_PROMPT = """
Ты — старший бизнес-аналитик в ИТ-стартапе. Проанализируй текст пользователя и верни ТОЛЬКО JSON.

Твоя задача:
- определить эмоциональную окраску и силу проблемы;
- выделить краткую суть боли, которую можно решить автоматизацией, ИИ или софтом.

Правила:
- Верни только JSON, без markdown, без пояснений и без лишних ключей.
- Используй только два поля:
  - "sentiment_score": число от -1.0 до 1.0, где -1.0 = сильный негатив, 0 = нейтрально, 1.0 = сильный позитив.
  - "pain_point": короткая строка с названием боли/проблемы.
- Игнорируй флуд, токсичность и бессмысленные сообщения.
- Если в тексте нет явной боли, поставь sentiment_score ближе к 0 и pain_point как короткое нейтральное описание контекста.

Формат ответа:
{
  "sentiment_score": -0.7,
  "pain_point": "ручной перенос данных"
}
""".strip()


load_dotenv()

_api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=_api_key) if _api_key else None


def _normalize_text(text_to_analyze: Any) -> str:
    if isinstance(text_to_analyze, str):
        text = text_to_analyze.strip()
        if text:
            return text
        raise ValueError("text_to_analyze is empty.")

    if isinstance(text_to_analyze, Iterable) and not isinstance(text_to_analyze, (dict, bytes, bytearray)):
        parts: list[str] = []
        for item in text_to_analyze:
            if item is None:
                continue
            part = str(item).strip()
            if part:
                parts.append(part)

        if not parts:
            raise ValueError("text_to_analyze does not contain any usable text.")

        return "\n".join(parts)

    raise TypeError("text_to_analyze must be a string or an iterable of comments.")


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sentiment_score = payload.get("sentiment_score")
    pain_point = payload.get("pain_point")

    try:
        sentiment_score = float(sentiment_score)
    except (TypeError, ValueError) as exc:
        raise ValueError('OpenAI response has invalid "sentiment_score".') from exc

    if sentiment_score < -1.0 or sentiment_score > 1.0:
        raise ValueError('"sentiment_score" must be in range [-1.0, 1.0].')

    if not isinstance(pain_point, str) or not pain_point.strip():
        raise ValueError('OpenAI response has invalid "pain_point".')

    return {
        "sentiment_score": sentiment_score,
        "pain_point": pain_point.strip(),
    }


async def analyze_customer_pains(text_to_analyze: Any) -> dict[str, Any]:
    """Analyze text/comments and return only sentiment_score + pain_point."""
    user_content = _normalize_text(text_to_analyze)

    if client is None:
        return {
            "sentiment_score": 0.0,
            "pain_point": "ТЕСТОВЫЙ РЕЖИМ: OpenAI недоступен",
        }

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Проанализируй текст и верни JSON строго по схеме.\n\n"
                        f"{user_content}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        return {
            "sentiment_score": 0.0,
            "pain_point": "ТЕСТОВЫЙ РЕЖИМ: OpenAI недоступен",
        }
    except OpenAIError as exc:
        raise RuntimeError("OpenAI API is unavailable or returned an error.") from exc
    except Exception as exc:
        raise RuntimeError("Unexpected error while calling OpenAI.") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise ValueError("OpenAI returned an empty response.")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("OpenAI returned JSON, but not an object.")

    return _validate_payload(payload)
