from fastapi import APIRouter

from app.modules.commands.schemas import CommandIn, CommandOut
from app.modules.commands.service import publish_command

router = APIRouter()


@router.post(
    "/commands",
    response_model=CommandOut,
    summary="Envoyer une commande au boîtier",
    description=(
        "Envoie une commande au boîtier ESP32 sur sentinelx/esp32-01/cmd "
        "(led_red:1, led_green:0, buzzer:1, auto, scenario:drift) "
        "et, pour les LED et les scénarios, le JSON équivalent au simulateur "
        "sur sentinelx/g6/cmd. La carte répond sur sentinelx/esp32-01/ack."
    ),
)
async def post_command(body: CommandIn) -> CommandOut:
    topic = await publish_command(body)
    return CommandOut(published=True, topic=topic)
