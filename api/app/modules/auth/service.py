"""Password hashing, JWT, and the seeded admin account.

Passwords and signing keys stay in the environment. The table is filled once:
an existing admin is never overwritten on restart.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

TOKEN_HOURS = 12
ADMIN_ROLE = "admin"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(email: str, role: str = ADMIN_ROLE) -> str:
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    email = payload.get("sub")
    role = payload.get("role")
    if not isinstance(email, str) or not email:
        return None
    if not isinstance(role, str) or not role:
        return None
    return {"email": email, "role": role}


def vision_token_ok(received: str | None) -> bool:
    expected = settings.vision_token
    if not expected or not received:
        return False
    return secrets.compare_digest(received, expected)


async def authenticate(email: str, password: str) -> User | None:
    async with SessionLocal() as session:
        row = await session.scalar(select(User).where(User.email == email.strip().lower()))
        if row is None:
            return None
        if not verify_password(password, row.password_hash):
            return None
        return row


async def seed_admin() -> None:
    email = settings.admin_email.strip().lower()
    password = settings.admin_password
    if not email or not password:
        logger.error("ADMIN_EMAIL or ADMIN_PASSWORD is empty; login stays closed.")
        return
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(User))
        if count:
            logger.info("Admin table already has %s account(s); seed skipped.", count)
            return
        session.add(
            User(email=email, password_hash=hash_password(password), role=ADMIN_ROLE)
        )
        await session.commit()
        logger.info("Admin account ready for %s", email)
