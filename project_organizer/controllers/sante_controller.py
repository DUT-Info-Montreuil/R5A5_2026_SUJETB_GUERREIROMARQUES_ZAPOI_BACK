"""
Diagnostic de l'API et de sa base.

Un contrôleur traduit HTTP en appels de service, et les résultats en réponses.
Aucune règle métier, aucune requête SQL ici.
"""

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from ..dtos.sante_dto import EtatSanteDto, sante_degradee_dto, sante_vers_dto
from ..extensions import spec
from ..services import sante_service
from ..services.sante_service import BaseInjoignable
from ..utils.authentification import publique

sante_bp = Blueprint("sante", __name__)


@sante_bp.get("/health")
@publique
@spec.validate(resp=Response(HTTP_200=EtatSanteDto, HTTP_503=EtatSanteDto), tags=["Diagnostic"])
def health():
    """État de l'API et de sa base de données.

    Bascule en 503 quand la base est arrêtée : une route qui répondrait 200
    sans interroger la base ne prouverait rien.
    """
    try:
        etat = sante_service.etat_de_la_base()
    except BaseInjoignable:
        return jsonify(sante_degradee_dto().vers_json()), 503
    return jsonify(sante_vers_dto(etat).vers_json()), 200
