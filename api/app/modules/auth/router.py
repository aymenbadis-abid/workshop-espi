from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.deps import require_user
from app.modules.auth.schemas import LoginIn, MeOut, Token
from app.modules.auth.service import authenticate, create_access_token

router = APIRouter()


@router.post(
    "/auth/login",
    response_model=Token,
    summary="Connexion admin",
    description="Échange un email et un mot de passe contre un jeton Bearer. Pas d'inscription.",
)
async def login(body: LoginIn) -> Token:
    user = await authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants refusés")
    return Token(access_token=create_access_token(user.email, user.role))


@router.get(
    "/auth/me",
    response_model=MeOut,
    summary="Compte connecté",
)
async def read_me(user: dict = Depends(require_user)) -> MeOut:
    return MeOut(email=user["email"], role=user["role"])
