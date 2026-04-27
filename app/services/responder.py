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
Ты — модуль генерации ответов Smart AI Responder.
Используй правила из knowledge_base.txt как системную инструкцию.

Если тональность негативная (sentiment_score < 0), используй шаблон отработки претензий из базы знаний.
Если тональность позитивная, предложи мягкий апсейл или благодарность.
Верни только JSON со схемой:
{
  "response_text": "короткий ответ"
}
Ответ должен быть коротким.
""".strip()


DEFAULT_FALLBACK_REPLY = "Спасибо за ваш отзыв, мы уже изучаем детали"
MAX_REPLY_LENGTH = 500
RETRY_SUFFIX = (
    "Сократи ответ до 500 символов, сохрани вежливый Tone of Voice и не добавляй лишних деталей."
)


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

    response_text = payload.get("response_text")
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("Invalid response_text.")

    return {"response_text": response_text.strip()}


def _fallback_reply() -> dict[str, str]:
    return {"response_text": DEFAULT_FALLBACK_REPLY}


def _build_prompt(knowledge: str, raw_text: str, sentiment_score: float) -> str:
    return (
        f"Используй правила из {knowledge} и ответь на отзыв {raw_text}. "
        f"Будь вежлив, соблюдай Tone of Voice. "
        f"Тональность: {sentiment_score}."
    )


async def _call_openai(prompt: str, knowledge: str) -> dict[str, Any]:
    if client is None:
        return _fallback_reply()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{prompt}\n\nKnowledge base:\n{knowledge}"},
            ],
            response_format={"type": "json_object"},
        )
    except RateLimitError:
        return _fallback_reply()
    except OpenAIError:
        return _fallback_reply()

    content = response.choices[0].message.content if response.choices else None
    if not content:
        return _fallback_reply()

    try:
        return _extract_payload(content)
    except ValueError:
        return _fallback_reply()


async def generate_smart_reply(insight_text: str, sentiment_score: float | None = None, knowledge_override: str | None = None) -> str:
    text = insight_text.strip()
    if not text:
        raise ValueError("insight_text is empty.")

    knowledge = knowledge_override or read_knowledge_base()
    score = 0.0 if sentiment_score is None else sentiment_score

    initial_prompt = _build_prompt(knowledge, text, score)
    initial_result = await _call_openai(initial_prompt, knowledge)
    reply_text = initial_result["response_text"]

    if len(reply_text) <= MAX_REPLY_LENGTH:
        return reply_text

    shorten_prompt = (
        f"{initial_prompt}\n"
        f"Предыдущий ответ получился слишком длинным ({len(reply_text)} символов).\n"
        f"{RETRY_SUFFIX}"
    )
    shortened_result = await _call_openai(shorten_prompt, knowledge)
    shortened_text = shortened_result["response_text"]

    if len(shortened_text) <= MAX_REPLY_LENGTH:
        return shortened_text

    return shortened_text[:MAX_REPLY_LENGTH].rstrip()


async def generate_reply(
    sentiment_score: float,
    raw_text: str,
    knowledge_override: str | None = None,
) -> dict[str, Any]:
    reply_text = await generate_smart_reply(
        insight_text=raw_text,
        sentiment_score=sentiment_score,
        knowledge_override=knowledge_override,
    )
    return {"response_text": reply_text}
