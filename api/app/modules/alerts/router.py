from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.hub import hub
from app.modules.alerts.schemas import AlertCreate, AlertOut
from app.modules.alerts.service import create_alert, list_alerts

router = APIRouter()


@router.get(
    "/alerts",
    response_model=list[AlertOut],
    summary="Liste des alertes",
    description=(
        "Alertes enregistrées, la plus récente en premier. "
        "La source vaut mqtt quand le message vient du boîtier ou du simulateur, "
        "et http quand elle a été créée par POST /api/v1/alerts "
        "(caméra, ou un autre service du serveur). "
        "Les nouvelles alertes sont aussi poussées sur /api/v1/ws, événement kind=alert."
    ),
)
async def read_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[AlertOut]:
    rows = await list_alerts(session, limit)
    return [AlertOut.model_validate(row) for row in rows]


@router.post(
    "/alerts",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une alerte",
    description=(
        "Point d'entrée obligatoire du sujet pour les alertes produites hors de la carte. "
        "Le service Vision l'appellera en HTTPS pour une personne détectée. "
        "Le corps est validé (type, message, sévérité info|warning|critical) "
        "puis stocké dans PostgreSQL et diffusé sur le WebSocket du dashboard."
    ),
)
async def post_alert(
    body: AlertCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    row = await create_alert(session, body, source="http")
    payload = AlertOut.model_validate(row).model_dump(mode="json")
    await hub.broadcast({"kind": "alert", "data": payload})
    return AlertOut.model_validate(row)
