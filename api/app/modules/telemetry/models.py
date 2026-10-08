from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    device: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[int] = mapped_column(BigInteger, index=True)
    temp: Mapped[float] = mapped_column(Float)
    hum: Mapped[float] = mapped_column(Float)
    gas: Mapped[float] = mapped_column(Float)
    light: Mapped[float] = mapped_column(Float)
    simulated: Mapped[list] = mapped_column(JSONB)
    gas_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_ready: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_dark: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transitions_1min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_heat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_gas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# create_all does not add columns to a table that already exists.
BOARD_FACT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("gas_raw", "DOUBLE PRECISION"),
    ("gas_delta", "DOUBLE PRECISION"),
    ("gas_ready", "INTEGER"),
    ("light_dark", "INTEGER"),
    ("transitions_1min", "INTEGER"),
    ("alert_heat", "INTEGER"),
    ("alert_gas", "INTEGER"),
    ("manual", "INTEGER"),
    ("rssi", "INTEGER"),
)


class DeviceStatus(Base):
    __tablename__ = "device_status"

    device: Mapped[str] = mapped_column(String(64), primary_key=True)
    online: Mapped[bool] = mapped_column(Boolean)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uptime: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
