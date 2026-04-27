from app.models import Insight
from app.connectors.tg_bridge import send_approval_card


async def notify_insight_to_telegram(insight: Insight) -> None:
    await send_approval_card(insight)
