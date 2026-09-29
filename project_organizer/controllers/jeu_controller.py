"""Jeux : le catalogue proposé à la création d'un tournoi."""

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from ..dtos.tournoi_dto import ListeJeuxDto, jeu_vers_dto
from ..extensions import spec
from ..services import tournoi_service
from ..utils.authentification import publique

jeu_bp = Blueprint("jeux", __name__, url_prefix="/api/jeux")


@jeu_bp.get("")
@publique
@spec.validate(resp=Response(HTTP_200=ListeJeuxDto), tags=["Tournois"])
def lister_jeux():
    """Les jeux disponibles, par ordre alphabétique. Public."""
    return jsonify([jeu_vers_dto(jeu).vers_json() for jeu in tournoi_service.lister_jeux()]), 200
