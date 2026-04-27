import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError, RateLimitError


BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_PATH = BASE_DIR / "knowledge_base.txt"

load_dotenv(dotenv_path=BASE_DIR / ".env")

_api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=_api_key) if _api_key else None


SYSTEM_PROMPT = """
Ты — аналитический модуль Smart AI Responder.
Используй правила из knowledge_base.txt как системную инструкцию.
Твоя задача — проанализировать текст и вернуть только JSON.

Схема ответа:
{
  "sentiment_score": -1.0,
  "pain_category": "краткая категория боли",
  "normalized_text": "очищенная и кратко переформулированная версия исходного текста"
}

Требования:
- sentiment_score строго от -1.0 до 1.0
- pain_category должна быть короткой и понятной
- normalized_text должен быть очищен от мусора, повторов и лишних символов
- верни только JSON, без markdown и без пояснений
""".strip()


def read_knowledge_base() -> str:
    if not KNOWLEDGE_BASE_PATH.exists():
        KNOWLEDGE_BASE_PATH.write_text(
            "Правила ответов студии: всегда отвечай вежливо, кратко и по делу.",
            encoding="utf-8",
        )
    return KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8").strip()


def _extract_payload(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("OpenAI returned JSON, but not an object.")

    sentiment_score = payload.get("sentiment_score")
    pain_category = payload.get("pain_category")
    normalized_text = payload.get("normalized_text")

    try:
        sentiment_score = float(sentiment_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid sentiment_score.") from exc

    if sentiment_score < -1.0 or sentiment_score > 1.0:
        raise ValueError("sentiment_score must be in range [-1.0, 1.0].")

    if not isinstance(pain_category, str) or not pain_category.strip():
        raise ValueError("Invalid pain_category.")

    if not isinstance(normalized_text, str) or not normalized_text.strip():
        raise ValueError("Invalid normalized_text.")

    return {
        "sentiment_score": sentiment_score,
        "pain_category": pain_category.strip(),
        "normalized_text": normalized_text.strip(),
    }


def _fallback_analysis(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    return {
        "sentiment_score": 0.0,
        "pain_category": "general_feedback",
        "normalized_text": cleaned,
    }


async def analyze_raw_text(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise ValueError("raw_text is empty.")

    knowledge = read_knowledge_base()

    if client is None:
        return _fallback_analysis(text)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nKnowledge base:\n{knowledge}"},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError:
        return _fallback_analysis(text)
    except OpenAIError:
        return _fallback_analysis(text)

    content = response.choices[0].message.content if response.choices else None
    if not content:
        return _fallback_analysis(text)

    try:
        return _extract_payload(content)
    except ValueError:
        return _fallback_analysis(text)
