from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def ensure_schema() -> None:
    """Create missing tables, then add board-fact columns on an existing telemetry table."""
    from app.modules.alerts import models as alert_models  # noqa: F401
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.telemetry import models as telemetry_models  # noqa: F401
    from app.modules.telemetry.models import BOARD_FACT_COLUMNS

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for name, column_type in BOARD_FACT_COLUMNS:
            await connection.execute(
                text(f"ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS {name} {column_type}")
            )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
