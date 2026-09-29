"""Rencontres (contrat §5)."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.rencontre_dto import RencontreDto, ResultatRencontreDto, rencontre_vers_dto
from ..extensions import spec
from ..services import rencontre_service
from ..utils.authentification import administrateur_requis

rencontre_bp = Blueprint("rencontres", __name__, url_prefix="/api/rencontres")


@rencontre_bp.patch("/<int:id_rencontre>")
@administrateur_requis
@spec.validate(
    body=ResultatRencontreDto,
    resp=Response(
        HTTP_200=RencontreDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Rencontres"],
)
def saisir_resultat(id_rencontre: int):
    """Désigner le vainqueur d'une rencontre (B-13, B-14, B-15). Administrateur.

    typeResultat : NORMAL (scores facultatifs, par paire), FORFAIT, ou
    QUALIFICATION_DIRECTE quand il n'y a pas d'adversaire. Le perdant est
    éliminé et le vainqueur placé dans la rencontre suivante, dans une seule
    transaction.

    409 si la rencontre n'est pas JOUABLE ou si le tournoi n'est pas en cours ;
    422 si le vainqueur ne joue pas cette rencontre. Émet rencontre:maj.
    """
    donnees: ResultatRencontreDto = request.context.body
    rencontre, noms = rencontre_service.saisir_resultat(
        id_rencontre, donnees.id_vainqueur, donnees.type_resultat, donnees.score_a, donnees.score_b
    )
    return jsonify(rencontre_vers_dto(rencontre, noms).vers_json()), 200
