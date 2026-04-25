import json
import os
import traceback

from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException
from openai import OpenAI, RateLimitError
import openai
from sqlalchemy.orm import Session

# Load environment variables from .env before importing database settings.
load_dotenv()

from models import Base, SessionLocal, Ticket, engine
from schemas import AnalyticsResponse, TicketCreate, TicketRead


app = FastAPI(
    title="Smart Insight Desk MVP",
    version="0.1.0",
    docs_url="/doc",
    redoc_url=None,
)

client = OpenAI()

def analyze_with_openai(text: str) -> tuple[float, str]:
    """Run ticket analysis through OpenAI and return normalized results."""
    print(f"OPENAI_API_KEY set: {bool(os.getenv('OPENAI_API_KEY'))}")  # TEMP: debug only.

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze customer support tickets. "
                        "Return only valid JSON with keys sentiment_score and pain_point. "
                        "sentiment_score must be a number from -1.0 to 1.0, where negative means unhappy and positive means happy. "
                        "pain_point must be a short lowercase label."
                    ),
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            response_format={"type": "json_object"},
        )
    except Exception:
        traceback.print_exc()
        raise

    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenAI returned an empty analysis response.")

    try:
        payload = json.loads(content)
        sentiment_score = float(payload["sentiment_score"])
        pain_point = str(payload["pain_point"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("OpenAI returned invalid analysis data.") from exc

    return sentiment_score, pain_point


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def store_ticket_to_db(db: Session, text: str, sentiment_score: float, pain_point: str) -> Ticket:
    """Persist the analyzed ticket fields needed for analytics reporting."""
    ticket = Ticket(
        text=text,
        status="processed",
        sentiment_score=sentiment_score,
        pain_point=pain_point,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/submit-ticket", response_model=TicketRead)
def submit_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    try:
        sentiment_score, pain_point = analyze_with_openai(payload.text)
        return store_ticket_to_db(db, payload.text, sentiment_score, pain_point)
    except RateLimitError as exc:
        traceback.print_exc()
        detail = "OpenAI quota exceeded. Please check billing or usage limits."
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", {})
            if isinstance(error, dict) and error.get("code") == "insufficient_quota":
                detail = "OpenAI quota exceeded: insufficient quota for this request."
        raise HTTPException(status_code=502, detail=detail) from exc
    except openai.OpenAIError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail="OpenAI analysis failed. Please try again later.",
        ) from exc
    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned invalid analysis data.",
        ) from exc


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
    return {"message": "Smart Insight Desk MVP is running. Open /doc for Swagger UI."}
