from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insight import Insight, InsightStatus
from app.models.status_log import StatusLog


async def log_status_change(
    db: AsyncSession,
    *,
    insight: Insight,
    old_status: InsightStatus,
    new_status: InsightStatus,
    changed_by: str,
    comment: str | None = None,
) -> StatusLog:
    audit_row = StatusLog(
        insight_id=insight.id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        comment=comment,
    )
    db.add(audit_row)
    return audit_row
