from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.service import decode_access_token, vision_token_ok

_bearer = HTTPBearer(auto_error=False)

MISSING = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Jeton manquant",
    headers={"WWW-Authenticate": "Bearer"},
)
REFUSED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Jeton refusé",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise MISSING
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise REFUSED
    return payload


async def require_vision(x_vision_token: str | None = Header(default=None)) -> None:
    if not vision_token_ok(x_vision_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton vision refusé")
