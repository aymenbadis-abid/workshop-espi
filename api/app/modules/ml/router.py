from fastapi import APIRouter

from app.modules.ml.schemas import ScoringOut
from app.modules.ml.service import scoring_snapshot

router = APIRouter()


@router.get(
    "/scoring",
    response_model=ScoringOut,
    summary="État du score des capteurs",
    description=(
        "Phrases déjà calculées pour l'écran, après au moins une mesure. "
        "joint_drift est rempli quand le couple température–gaz n'est pas jugé : "
        "« Gaz simulé : dérive conjointe inactive », "
        "« Gaz réel, modèle de salle absent : dérive conjointe inactive », "
        "ou « Modèle absent : dérive conjointe inactive ». "
        "silence vaut « Silence de 2 minutes en cours. » tant que cette pause "
        "court après un constat. Ce ne sont pas des conseils. "
        "Les mêmes champs partent sur le WebSocket, événement kind=scoring."
    ),
)
async def read_scoring() -> ScoringOut:
    return ScoringOut.model_validate(scoring_snapshot())
