"""Login token and locked routes. No database, no broker."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sentinelx:x@localhost/sentinelx")
os.environ.setdefault("MQTT_API_USERNAME", "api")
os.environ.setdefault("MQTT_API_PASSWORD", "x")
os.environ.setdefault("JWT_SECRET", "test-secret-for-auth-32b-minimum")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ADMIN_EMAIL", "admin@sentinel-x.local")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")
os.environ.setdefault("VISION_TOKEN", "vision-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.deps import require_user, require_vision
from app.modules.auth.service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    vision_token_ok,
)

tiny = FastAPI()


@tiny.get("/locked")
async def locked(user: dict = Depends(require_user)) -> dict:
    return {"email": user["email"]}


@tiny.post("/vision-in")
async def vision_in(_vision: None = Depends(require_vision)) -> dict:
    return {"ok": True}


client = TestClient(tiny)


def test_password_roundtrip() -> None:
    hashed = hash_password("secret-admin")
    assert hashed != "secret-admin"
    assert verify_password("secret-admin", hashed)
    assert not verify_password("other", hashed)


def test_token_roundtrip() -> None:
    token = create_access_token("admin@sentinel-x.local", "admin")
    payload = decode_access_token(token)
    assert payload == {"email": "admin@sentinel-x.local", "role": "admin"}
    assert decode_access_token("not-a-token") is None


def test_locked_route_needs_bearer() -> None:
    missing = client.get("/locked")
    assert missing.status_code == 401
    token = create_access_token("admin@sentinel-x.local")
    ok = client.get("/locked", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "admin@sentinel-x.local"


def test_vision_token_rejects_wrong_header() -> None:
    assert vision_token_ok("vision-secret")
    assert not vision_token_ok("wrong")
    assert not vision_token_ok(None)
    refused = client.post("/vision-in", headers={"X-Vision-Token": "wrong"})
    assert refused.status_code == 401
    accepted = client.post("/vision-in", headers={"X-Vision-Token": "vision-secret"})
    assert accepted.status_code == 200


if __name__ == "__main__":
    test_password_roundtrip()
    test_token_roundtrip()
    test_locked_route_needs_bearer()
    test_vision_token_rejects_wrong_header()
    print("auth checks ok")
