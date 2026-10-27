"""Ce qui concerne l'utilisateur connecté : ses équipes et ses demandes en attente."""

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.moi_dto import (
    ListeMesDemandesDto,
    ListeMesEquipesDto,
    ma_demande_vers_dto,
    mon_equipe_vers_dto,
)
from ..extensions import spec
from ..services import demande_service, equipe_service
from ..utils.authentification import utilisateur_courant

moi_bp = Blueprint("moi", __name__, url_prefix="/api/moi")


@moi_bp.get("/equipes")
@spec.validate(resp=Response(HTTP_200=ListeMesEquipesDto, HTTP_401=ErreurDto), tags=["Mon compte"])
def mes_equipes():
    """Les équipes de l'utilisateur connecté, les plus récentes d'abord.

    Sert à savoir où il joue (accès à l'espace d'échange) sans interroger
    chaque équipe de chaque tournoi.
    """
    equipes = equipe_service.de_l_utilisateur(utilisateur_courant())
    return jsonify([mon_equipe_vers_dto(e, capitaine, t).vers_json() for e, capitaine, t in equipes]), 200


@moi_bp.get("/demandes")
@spec.validate(resp=Response(HTTP_200=ListeMesDemandesDto, HTTP_401=ErreurDto), tags=["Mon compte"])
def mes_demandes():
    """Les demandes d'adhésion de l'utilisateur connecté qui attendent une réponse."""
    demandes = demande_service.en_attente_de(utilisateur_courant())
    return jsonify([ma_demande_vers_dto(d, e, t).vers_json() for d, e, t in demandes]), 200
