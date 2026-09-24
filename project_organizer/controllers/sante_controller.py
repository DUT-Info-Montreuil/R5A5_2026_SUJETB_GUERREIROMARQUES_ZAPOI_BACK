"""
Diagnostic de l'API et de sa base.

Un contrôleur traduit HTTP en appels de service, et les résultats en réponses.
Aucune règle métier, aucune requête SQL ici.
"""

from flask import Blueprint, jsonify

from ..dtos.sante_dto import sante_degradee_dto, sante_vers_dto
from ..services import sante_service
from ..services.sante_service import BaseInjoignable

sante_bp = Blueprint("sante", __name__)


@sante_bp.get("/health")
def health():
    """État de l'API et de sa base de données.

    Bascule en 503 quand la base est arrêtée : une route qui répondrait 200
    sans interroger la base ne prouverait rien.
    """
    try:
        etat = sante_service.etat_de_la_base()
    except BaseInjoignable:
        return jsonify(sante_degradee_dto()), 503
    return jsonify(sante_vers_dto(etat)), 200
