import random

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from models import Base, SessionLocal, Ticket, engine
from schemas import AnalyticsResponse, TicketCreate, TicketRead


app = FastAPI(
    title="Smart Insight Desk MVP",
    version="0.1.0",
    docs_url="/doc",
    redoc_url=None,
)


def fake_ai_analyze(text: str) -> tuple[float, str]:
    """Placeholder for future AI analysis."""
    sentiment_score = round(random.uniform(-1.0, 1.0), 3)

    lowered = text.lower()
    if any(keyword in lowered for keyword in ["refund", "money", "payment", "invoice"]):
        pain_point = "billing"
    elif any(keyword in lowered for keyword in ["login", "password", "access", "sign in"]):
        pain_point = "authentication"
    elif any(keyword in lowered for keyword in ["slow", "lag", "crash", "error"]):
        pain_point = "product stability"
    elif any(keyword in lowered for keyword in ["support", "agent", "operator"]):
        pain_point = "customer support"
    else:
        pain_point = "general dissatisfaction"

    return sentiment_score, pain_point


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def analyze_and_store_ticket(db: Session, text: str) -> Ticket:
    sentiment_score, pain_point = fake_ai_analyze(text)
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
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Ticket text must not be empty.")

    return analyze_and_store_ticket(db, payload.text)


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
