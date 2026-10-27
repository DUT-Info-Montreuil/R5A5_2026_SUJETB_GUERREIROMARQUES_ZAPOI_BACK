"""Supervision du temps réel."""

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.metriques_dto import MetriquesTempsReelDto
from ..extensions import spec
from ..services import metriques_service
from ..utils.authentification import administrateur_requis

metriques_bp = Blueprint("metriques", __name__, url_prefix="/api/metriques")


@metriques_bp.get("/temps-reel")
@administrateur_requis
@spec.validate(
    resp=Response(HTTP_200=MetriquesTempsReelDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto),
    tags=["Supervision"],
)
def metriques_temps_reel():
    """Connexions actives, débit de messages, ouvertures sur la dernière minute. Administrateur.

    Les ouvertures de la dernière minute sont la « fréquence des reconnexions » :
    une hausse inhabituelle révèle un problème réseau, un délai d'inactivité
    mal réglé ou des redémarrages fréquents. Compteurs en mémoire, remis à zéro
    au redémarrage du serveur.
    """
    return jsonify(MetriquesTempsReelDto.model_validate(metriques_service.temps_reel()).vers_json()), 200
