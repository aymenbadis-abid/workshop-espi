from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.models import Alert
from app.modules.alerts.schemas import AlertCreate


async def create_alert(session: AsyncSession, payload: AlertCreate, source: str) -> Alert:
    row = Alert(
        device=payload.device,
        type=payload.type,
        message=payload.message,
        severity=payload.severity,
        ts=payload.ts,
        payload=payload.payload,
        source=source,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_alerts(session: AsyncSession, limit: int) -> list[Alert]:
    result = await session.execute(
        select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
    )
    return list(result.scalars().all())
