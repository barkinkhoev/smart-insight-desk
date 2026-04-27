import os
import html
import logging
import traceback
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Load environment variables from .env before importing database settings.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

from ai_analyser import analyze_customer_pains
from ai_responder import generate_polite_response
from app.connectors.tg_bridge import send_approval_card
from app.api.v1.telegram import router as telegram_router
from app.core.database import Base as AppBase, async_engine, get_async_session
from app.models import Insight, InsightSource, InsightStatus, StatusLog
from app.schemas import InsightRead, StatusLogRead, WBWebhookRequest
from app.services.audit import log_status_change
from app.services.analyzer import analyze_raw_text
from app.services.responder import generate_smart_reply
from models import AnalysisHistory, Base as LegacyBase, SessionLocal, Ticket, engine
from services import generate_ai_reply, save_ai_reply_to_db
from schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalyticsResponse,
    FeedbackRequest,
    GenerateReplyResponse,
    HistoryResponse,
    RespondRequest,
    RespondResponse,
)


TELEGRAM_FALLBACK_PREFIX = "⚠️ [ТЕСТОВЫЙ ЗАПУСК] "
FALLBACK_PAIN_POINT = "ТЕСТОВЫЙ РЕЖИМ: OpenAI недоступен"

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Smart Insight Desk MVP",
    description="Генератор умных ответов для маркетплейсов и соцсетей",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

app.include_router(telegram_router)


def _get_telegram_token() -> str | None:
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_TOKEN")
        or os.getenv("ORCHESTRATOR_BOT_TOKEN")
    )


def _get_telegram_chat_id() -> int | None:
    raw_value = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("ANALYTICS_CHAT_ID")
        or os.getenv("BOT_CHAT_ID")
    )
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _get_telegram_fallback_chat_id() -> int | None:
    return (
        int(os.getenv("TELEGRAM_FALLBACK_CHAT_ID"))
        if os.getenv("TELEGRAM_FALLBACK_CHAT_ID") and os.getenv("TELEGRAM_FALLBACK_CHAT_ID").lstrip("-").isdigit()
        else None
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def store_analysis_to_db(
    db: Session,
    raw_text: str,
    sentiment_score: float,
    pain_point: str,
    source: str,
) -> AnalysisHistory:
    analysis = AnalysisHistory(
        raw_text=raw_text,
        sentiment_score=sentiment_score,
        pain_point=pain_point,
        source=source,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


async def send_telegram_alert(pain_point: str, source: str) -> None:
    token = _get_telegram_token()
    chat_id = _get_telegram_chat_id()

    if not token or not chat_id:
        return

    is_fallback = pain_point.startswith(TELEGRAM_FALLBACK_PREFIX)
    clean_pain_point = (
        pain_point.removeprefix(TELEGRAM_FALLBACK_PREFIX) if is_fallback else pain_point
    )
    escaped_pain_point = html.escape(clean_pain_point)
    escaped_source = html.escape(source)

    message = (
        "🚀 <b>Smart Insight Desk: Новый инсайт!</b>\n\n"
        f"💡 <b>Боль:</b> {escaped_pain_point}\n"
        f"📂 <b>Источник:</b> {escaped_source}\n\n"
        "<i>Инсайт успешно классифицирован и сохранен в базу.</i>"
    )
    if is_fallback:
        message = f"{TELEGRAM_FALLBACK_PREFIX}{message}"

    logger.debug("DEBUG: Попытка отправки в CHAT_ID: %s", chat_id)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Telegram sendMessage failed with HTTP status error: status=%s body=%s",
            exc.response.status_code if exc.response is not None else "unknown",
            exc.response.text if exc.response is not None else "no response body",
        )
        fallback_chat_id = _get_telegram_fallback_chat_id()
        if fallback_chat_id is not None:
            payload["chat_id"] = fallback_chat_id
            logger.debug("DEBUG: Попытка отправки в fallback CHAT_ID: %s", fallback_chat_id)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                return
            except httpx.HTTPStatusError as fallback_exc:
                logger.error(
                    "Telegram fallback sendMessage failed with HTTP status error: status=%s body=%s",
                    fallback_exc.response.status_code if fallback_exc.response is not None else "unknown",
                    fallback_exc.response.text if fallback_exc.response is not None else "no response body",
                )
            except httpx.HTTPError:
                logger.exception("Telegram fallback sendMessage failed with network error")
        return
    except httpx.HTTPError:
        logger.exception("Telegram sendMessage failed with network error")


async def _create_async_tables() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)


@app.on_event("startup")
async def on_startup() -> None:
    LegacyBase.metadata.create_all(bind=engine)
    await _create_async_tables()


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze(
    payload: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        result = await analyze_customer_pains(payload.text)
        analysis = store_analysis_to_db(
            db=db,
            raw_text=payload.text,
            sentiment_score=result["sentiment_score"],
            pain_point=result["pain_point"],
            source=payload.source,
        )
        telegram_pain_point = result["pain_point"]
        if telegram_pain_point == FALLBACK_PAIN_POINT:
            telegram_pain_point = f"{TELEGRAM_FALLBACK_PREFIX}{telegram_pain_point}"
        background_tasks.add_task(
            send_telegram_alert,
            telegram_pain_point,
            payload.source,
        )
        return analysis
    except RuntimeError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@app.get("/api/v1/history", response_model=HistoryResponse)
def history(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source: str | None = Query(default=None),
):
    query = db.query(AnalysisHistory)
    if source is not None:
        normalized_source = source.strip()
        if normalized_source:
            query = query.filter(AnalysisHistory.source == normalized_source)

    total = query.count()
    items = (
        query.order_by(AnalysisHistory.timestamp.desc(), AnalysisHistory.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return HistoryResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/api/v1/webhook/wb",
    response_model=InsightRead,
    tags=["Webhooks"],
    summary="Receive new Wildberries review",
)
async def webhook_wb(
    payload: WBWebhookRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    try:
        analysis = await analyze_raw_text(payload.text)
        insight = Insight(
            source=InsightSource.WB,
            raw_text=payload.text,
            normalized_text=analysis["normalized_text"],
            sentiment_score=analysis["sentiment_score"],
            pain_category=analysis["pain_category"],
            status=InsightStatus.DRAFT,
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)

        ai_reply = await generate_smart_reply(
            insight_text=payload.text,
            sentiment_score=analysis["sentiment_score"],
        )
        setattr(insight, "ai_reply", ai_reply)
        background_tasks.add_task(
            send_approval_card,
            insight,
        )
        return insight
    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail="WB webhook processing failed.") from exc


@app.get("/api/v1/insights/{insight_id}/approve")
async def approve_insight(
    insight_id: UUID,
    changed_by: str = Query(default="mentor", min_length=1, max_length=255),
    comment: str | None = Query(default=None, max_length=2000),
    db: AsyncSession = Depends(get_async_session),
):
    insight = await db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found.")

    old_status = insight.status
    insight.status = InsightStatus.POSTED
    await log_status_change(
        db,
        insight=insight,
        old_status=old_status,
        new_status=InsightStatus.POSTED,
        changed_by=changed_by.strip(),
        comment=comment.strip() if isinstance(comment, str) and comment.strip() else None,
    )
    await db.commit()
    await db.refresh(insight)
    return {"id": str(insight.id), "status": insight.status.value}


@app.get("/api/v1/insights/{insight_id}/reject")
async def reject_insight(
    insight_id: UUID,
    changed_by: str = Query(default="mentor", min_length=1, max_length=255),
    comment: str | None = Query(default=None, max_length=2000),
    db: AsyncSession = Depends(get_async_session),
):
    insight = await db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found.")

    old_status = insight.status
    insight.status = InsightStatus.DRAFT
    await log_status_change(
        db,
        insight=insight,
        old_status=old_status,
        new_status=InsightStatus.DRAFT,
        changed_by=changed_by.strip(),
        comment=comment.strip() if isinstance(comment, str) and comment.strip() else None,
    )
    await db.commit()
    await db.refresh(insight)
    return {"id": str(insight.id), "status": insight.status.value}


@app.get(
    "/api/v1/insights/{insight_id}/status-logs",
    response_model=list[StatusLogRead],
    tags=["Audit"],
    summary="Get status change history for an insight",
)
async def get_status_logs(
    insight_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(StatusLog)
        .where(StatusLog.insight_id == insight_id)
        .order_by(StatusLog.changed_at.desc(), StatusLog.id.desc())
    )
    return result.scalars().all()


@app.post("/api/v1/respond", response_model=RespondResponse)
async def respond(payload: RespondRequest):
    try:
        result = await generate_polite_response(payload.comment_text)
        return result
    except RuntimeError as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/v1/generate-reply",
    response_model=GenerateReplyResponse,
    tags=["Replies"],
    summary="Generate an auto-reply for marketplace/social feedback",
)
async def generate_reply(
    payload: FeedbackRequest,
    background_tasks: BackgroundTasks,
):
    try:
        reply_text = await generate_ai_reply(payload)
        background_tasks.add_task(save_ai_reply_to_db, payload, reply_text)
        return {"reply_text": reply_text}
    except RuntimeError as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/analytics", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    if tickets:
        average_sentiment_score = sum(ticket.sentiment_score for ticket in tickets) / len(tickets)
    else:
        average_sentiment_score = None

    return AnalyticsResponse(
        total_tickets=len(tickets),
        average_sentiment_score=average_sentiment_score,
        tickets=tickets,
    )


@app.get("/")
def root():
    return {"message": "Smart Insight Desk MVP is running. Open /docs for Swagger UI."}
