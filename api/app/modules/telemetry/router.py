from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.hub import hub
from app.modules.auth.deps import require_user
from app.modules.auth.service import decode_access_token
from app.modules.telemetry.schemas import StatusOut, TelemetryOut
from app.modules.telemetry.service import list_status, list_telemetry

router = APIRouter()


@router.get(
    "/telemetry",
    response_model=list[TelemetryOut],
    summary="Dernières mesures",
    description=(
        "Retourne les mesures stockées, de la plus ancienne à la plus récente "
        "dans la fenêtre demandée. Le champ simulated indique les voies produites "
        "par le moteur de scénarios et non par un capteur. Les faits de la carte "
        "(gas_ready, gas_delta, gas_raw, alert_heat, alert_gas, light_dark, "
        "transitions_1min, manual, rssi) sont renvoyés tels quels : une clé absente "
        "reste nulle, ce n'est pas un préchauffage inventé. Les nouvelles mesures "
        "arrivent aussi sur le WebSocket /api/v1/ws, événement kind=telemetry."
    ),
)
async def read_telemetry(
    limit: int = Query(default=60, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _user: dict = Depends(require_user),
) -> list[TelemetryOut]:
    rows = await list_telemetry(session, limit)
    return [TelemetryOut.model_validate(row) for row in rows]


@router.get(
    "/status",
    response_model=list[StatusOut],
    summary="État des boîtiers",
    description=(
        "Dernier état connu de chaque boîtier (en ligne, adresse IP, uptime), "
        "issu du sujet MQTT status et du testament MQTT. "
        "Les mises à jour arrivent sur /api/v1/ws, événement kind=status."
    ),
)
async def read_status(
    session: AsyncSession = Depends(get_session),
    _user: dict = Depends(require_user),
) -> list[StatusOut]:
    rows = await list_status(session)
    return [StatusOut.model_validate(row) for row in rows]


@router.websocket("/ws")
async def live_events(websocket: WebSocket) -> None:
    """Push telemetry, alert and status events as JSON objects with a kind field."""
    payload = decode_access_token(websocket.query_params.get("token") or "")
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.discard(websocket)
