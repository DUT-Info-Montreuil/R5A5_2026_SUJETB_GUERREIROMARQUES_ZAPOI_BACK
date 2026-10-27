"""Demandes d'adhésion (contrat §4, B-06)."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.demande_dto import (
    DemandeDto,
    FiltreDemandesDto,
    ListeDemandesDto,
    TraitementDemandeDto,
    demande_vers_dto,
)
from ..extensions import spec
from ..services import demande_service
from ..utils.authentification import utilisateur_courant

demande_bp = Blueprint("demandes", __name__)


@demande_bp.post("/api/equipes/<int:id_equipe>/demandes")
@spec.validate(
    resp=Response(
        HTTP_201=DemandeDto, HTTP_401=ErreurDto, HTTP_404=ErreurDto,
        HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Demandes d'adhésion"],
)
def creer_demande(id_equipe: int):
    """Demander à rejoindre une équipe (B-06). Joueur connecté.

    409 si les inscriptions sont closes ou si une demande est déjà en attente ;
    422 si le joueur a déjà une équipe dans ce tournoi (B-07) ou si l'équipe
    est complète. Un joueur refusé peut redemander.
    """
    demande, pseudo = demande_service.creer(id_equipe, utilisateur_courant())
    return jsonify(demande_vers_dto(demande, pseudo).vers_json()), 201


@demande_bp.get("/api/equipes/<int:id_equipe>/demandes")
@spec.validate(
    query=FiltreDemandesDto,
    resp=Response(HTTP_200=ListeDemandesDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_404=ErreurDto),
    tags=["Demandes d'adhésion"],
)
def lister_demandes(id_equipe: int):
    """Les demandes d'une équipe, les plus récentes d'abord. Capitaine seul.

    404 pour tout autre appelant, administrateur compris : les demandes sont
    invisibles de qui n'en est pas destinataire.
    """
    filtre: FiltreDemandesDto = request.context.query
    demandes = demande_service.lister(id_equipe, utilisateur_courant(), filtre.statut)
    return jsonify([demande_vers_dto(d, pseudo).vers_json() for d, pseudo in demandes]), 200


@demande_bp.patch("/api/demandes/<int:id_demande>")
@spec.validate(
    body=TraitementDemandeDto,
    resp=Response(
        HTTP_200=DemandeDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_404=ErreurDto,
        HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Demandes d'adhésion"],
)
def traiter_demande(id_demande: int):
    """Accepter ou refuser une demande (B-06). Capitaine de l'équipe seul.

    L'acceptation ajoute le joueur à l'équipe, sans poste, dans la même
    transaction. 404 si l'appelant n'est pas le capitaine ; 409 si la demande
    est déjà traitée ou les inscriptions closes ; 422 si le joueur a rejoint
    une autre équipe entre-temps (B-07) ou si l'équipe est complète.
    """
    donnees: TraitementDemandeDto = request.context.body
    demande, pseudo = demande_service.traiter(id_demande, utilisateur_courant(), donnees.statut_demande)
    return jsonify(demande_vers_dto(demande, pseudo).vers_json()), 200