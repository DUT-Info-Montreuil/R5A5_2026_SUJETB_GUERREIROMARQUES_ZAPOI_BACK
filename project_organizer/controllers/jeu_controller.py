"""Jeux : le catalogue proposé à la création d'un tournoi, et les postes de chaque jeu."""

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.equipe_dto import ListeRolesDto, role_vers_dto
from ..dtos.tournoi_dto import ListeJeuxDto, jeu_vers_dto
from ..extensions import spec
from ..services import jeu_service, tournoi_service
from ..utils.authentification import publique

jeu_bp = Blueprint("jeux", __name__, url_prefix="/api/jeux")


@jeu_bp.get("")
@publique
@spec.validate(resp=Response(HTTP_200=ListeJeuxDto), tags=["Tournois"])
def lister_jeux():
    """Les jeux disponibles, par ordre alphabétique. Public."""
    return jsonify([jeu_vers_dto(jeu).vers_json() for jeu in tournoi_service.lister_jeux()]), 200


@jeu_bp.get("/<int:id_jeu>/roles")
@publique
@spec.validate(resp=Response(HTTP_200=ListeRolesDto, HTTP_404=ErreurDto), tags=["Tournois"])
def lister_roles(id_jeu: int):
    """Les postes d'un jeu (Top, Jungle, Tank…), à proposer à la création d'une équipe. Public."""
    return jsonify([role_vers_dto(role).vers_json() for role in jeu_service.postes_du_jeu(id_jeu)]), 200