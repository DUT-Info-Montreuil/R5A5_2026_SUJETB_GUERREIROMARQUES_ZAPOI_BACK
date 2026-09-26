"""Tournois (contrat §3). Seule la liste existe pour l'instant."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response

from ..dtos.tournoi_dto import FiltreTournoisDto, ListeTournoisDto, tournoi_vers_dto
from ..extensions import spec
from ..services import tournoi_service
from ..utils.authentification import publique

tournoi_bp = Blueprint("tournois", __name__, url_prefix="/api/tournois")


@tournoi_bp.get("")
@publique
@spec.validate(query=FiltreTournoisDto, resp=Response(HTTP_200=ListeTournoisDto), tags=["Tournois"])
def lister_tournois():
    """Lister les tournois (B-02).

    Public. Ordre : en cours, inscriptions ouvertes, inscriptions closes,
    terminés ; les plus récents d'abord dans chaque groupe.
    """
    filtre: FiltreTournoisDto = request.context.query
    tournois = tournoi_service.lister(filtre.recherche, filtre.statut)
    return jsonify([tournoi_vers_dto(t, n).vers_json() for t, n in tournois]), 200
