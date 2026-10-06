from fastapi import APIRouter

from app.modules.commands.schemas import CommandIn, CommandOut
from app.modules.commands.service import publish_command

router = APIRouter()


@router.post(
    "/commands",
    response_model=CommandOut,
    summary="Envoyer une commande au boîtier",
    description=(
        "Publie sur sentinelx/g6/cmd une commande LED "
        "(target led_red ou led_green, state on ou off) "
        "ou un scénario de simulation (normal, drift, gas_leak, reset). "
        "Le simulateur et la carte reçoivent le même message. "
        "L'allumage physique des LEDs n'a lieu que lorsque la carte est connectée."
    ),
)
async def post_command(body: CommandIn) -> CommandOut:
    topic = await publish_command(body)
    return CommandOut(published=True, topic=topic)
