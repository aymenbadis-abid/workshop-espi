import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, ensure_schema
from app.modules.alerts import models as alert_models  # noqa: F401
from app.modules.alerts.router import router as alerts_router
from app.modules.commands.router import router as commands_router
from app.modules.ml.router import router as ml_router
from app.modules.ml.service import load_model
from app.modules.telemetry import models as telemetry_models  # noqa: F401
from app.modules.telemetry.router import router as telemetry_router
from app.mqtt.consumer import mqtt_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema()
    load_model()
    task = asyncio.create_task(mqtt_loop())
    logger.info("API ready")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await engine.dispose()


app = FastAPI(
    title="Sentinel-X API",
    summary="Ingestion MQTT, alertes et mesures de la micro-centrale.",
    description=(
        "L'API stocke la télémétrie et les alertes du boîtier (ou du simulateur) "
        "et expose POST /api/v1/alerts pour les événements produits sur le serveur, "
        "notamment la détection de personne. "
        "L'authentification JWT sera branchée avant la soutenance."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(commands_router, prefix="/api/v1")
app.include_router(ml_router, prefix="/api/v1")


@app.get(
    "/api/v1/health",
    summary="Disponibilité de l'API",
    description=(
        "Répond lorsque le processus FastAPI est lancé. "
        "Les mesures en direct sont poussées sur le WebSocket /api/v1/ws "
        "(événements kind=telemetry, kind=alert, kind=status, kind=scoring)."
    ),
)
async def health() -> dict[str, str]:
    return {"status": "ok"}
