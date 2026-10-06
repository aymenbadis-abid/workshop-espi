from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.telemetry.models import DeviceStatus, Telemetry
from app.modules.telemetry.schemas import StatusIn, TelemetryIn


async def record_telemetry(session: AsyncSession, payload: TelemetryIn) -> Telemetry:
    row = Telemetry(
        device=payload.device,
        ts=payload.ts,
        temp=payload.temp,
        hum=payload.hum,
        gas=payload.gas,
        light=payload.light,
        simulated=payload.simulated,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_telemetry(session: AsyncSession, limit: int) -> list[Telemetry]:
    result = await session.execute(
        select(Telemetry).order_by(Telemetry.ts.desc(), Telemetry.id.desc()).limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def upsert_status(session: AsyncSession, payload: StatusIn) -> DeviceStatus:
    stmt = (
        insert(DeviceStatus)
        .values(
            device=payload.device,
            online=payload.online,
            ip=payload.ip,
            uptime=payload.uptime,
        )
        .on_conflict_do_update(
            index_elements=[DeviceStatus.device],
            set_={
                "online": payload.online,
                "ip": payload.ip,
                "uptime": payload.uptime,
                "updated_at": func.now(),
            },
        )
        .returning(DeviceStatus)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def recent_device_window(session: AsyncSession, device: str, limit: int) -> list[Telemetry]:
    result = await session.execute(
        select(Telemetry)
        .where(Telemetry.device == device)
        .order_by(Telemetry.ts.desc(), Telemetry.id.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def list_status(session: AsyncSession) -> list[DeviceStatus]:
    result = await session.execute(select(DeviceStatus).order_by(DeviceStatus.device))
    return list(result.scalars().all())
