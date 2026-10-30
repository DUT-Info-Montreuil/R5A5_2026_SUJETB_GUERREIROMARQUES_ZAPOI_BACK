"""Équipes et composition (contrat §4)."""

from flask import Blueprint, Response as ReponseFlask, jsonify, request
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.equipe_dto import (
    CreationEquipeDto,
    EquipeDto,
    ModificationEquipeDto,
    ModificationMembreDto,
    equipe_vers_dto,
)
from ..extensions import spec
from ..services import equipe_service
from ..utils.authentification import publique, utilisateur_courant

equipe_bp = Blueprint("equipes", __name__)


@equipe_bp.post("/api/tournois/<int:id_tournoi>/equipes")
@spec.validate(
    body=CreationEquipeDto,
    resp=Response(
        HTTP_201=EquipeDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Équipes"],
)
def creer_equipe(id_tournoi: int):
    """Créer une équipe pour un tournoi et en devenir capitaine (B-05). Joueur connecté.

    idRole est le poste du créateur : il doit appartenir au jeu du tournoi.

    403 si l'appelant est administrateur (il organise, il ne joue pas) ;
    409 si les inscriptions sont closes, si le nom est déjà pris dans ce
    tournoi ou si le tournoi est complet ; 422 si le joueur a déjà une équipe
    dans ce tournoi (B-07) ou si le poste n'existe pas pour ce jeu.
    """
    donnees: CreationEquipeDto = request.context.body
    equipe, membres = equipe_service.creer(id_tournoi, utilisateur_courant(), donnees.nom_equipe, donnees.id_role)
    return jsonify(equipe_vers_dto(equipe, membres).vers_json()), 201


@equipe_bp.get("/api/equipes/<int:id_equipe>")
@publique
@spec.validate(resp=Response(HTTP_200=EquipeDto, HTTP_404=ErreurDto), tags=["Équipes"])
def detail_equipe(id_equipe: int):
    """Une équipe et ses membres (B-02). Public."""
    equipe, membres = equipe_service.detail(id_equipe)
    return jsonify(equipe_vers_dto(equipe, membres).vers_json()), 200


@equipe_bp.patch("/api/equipes/<int:id_equipe>")
@spec.validate(
    body=ModificationEquipeDto,
    resp=Response(
        HTTP_200=EquipeDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto,
    ),
    tags=["Équipes"],
)
def modifier_equipe(id_equipe: int):
    """Renommer une équipe ou la disqualifier (B-09, B-10, B-15).

    Champs autorisés selon l'appelant : nomEquipe pour le capitaine ;
    statutEquipe (seule valeur : DISQUALIFIEE) et motifSortie pour
    l'administrateur. Un champ hors de votre liste fait échouer toute la
    requête en 400.

    403 si l'appelant n'est ni capitaine de l'équipe ni administrateur ; 409 si
    le nom est pris ou si les inscriptions sont closes (renommage, B-11), si le
    tournoi n'est pas en cours ou si l'équipe n'est plus en lice (disqualification). La disqualification passe par forfait la rencontre de l'équipe et
    émet rencontre:maj.
    """
    donnees: ModificationEquipeDto = request.context.body
    equipe, membres = equipe_service.modifier(id_equipe, utilisateur_courant(), donnees.model_dump(exclude_unset=True))
    return jsonify(equipe_vers_dto(equipe, membres).vers_json()), 200


@equipe_bp.patch("/api/equipes/<int:id_equipe>/membres/<int:id_utilisateur>")
@spec.validate(
    body=ModificationMembreDto,
    resp=Response(
        HTTP_200=EquipeDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Équipes"],
)
def modifier_membre(id_equipe: int, id_utilisateur: int):
    """Attribuer un poste ou passer la main (B-08, B-09). Capitaine seul.

    idRole : le poste doit appartenir au jeu et ne pas être tenu par un autre
    membre (422). estCapitaine=true : le joueur devient capitaine, l'ancien est
    rétrogradé dans la même transaction.

    403 si l'appelant n'est pas capitaine ; 409 si les inscriptions sont
    closes (B-11) ; 404 si le joueur n'est pas membre.
    """
    donnees: ModificationMembreDto = request.context.body
    equipe, membres = equipe_service.modifier_membre(
        id_equipe, id_utilisateur, utilisateur_courant(), donnees.model_dump(exclude_unset=True)
    )
    return jsonify(equipe_vers_dto(equipe, membres).vers_json()), 200


@equipe_bp.delete("/api/equipes/<int:id_equipe>")
@spec.validate(
    resp=Response(HTTP_204=None, HTTP_401=ErreurDto, HTTP_403=ErreurDto, HTTP_404=ErreurDto, HTTP_409=ErreurDto),
    tags=["Équipes"],
)
def dissoudre_equipe(id_equipe: int):
    """Se désister : le capitaine dissout son équipe (B-06).

    403 si l'appelant n'est pas le capitaine ; 409 si les inscriptions sont
    closes. Les membres perdent l'accès à l'espace d'échange (motif `dissolution`).
    """
    equipe_service.dissoudre(id_equipe, utilisateur_courant())
    return ReponseFlask(status=204)


@equipe_bp.delete("/api/equipes/<int:id_equipe>/membres/<int:id_utilisateur>")
@spec.validate(
    resp=Response(
        HTTP_204=None, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Équipes"],
)
def retirer_membre(id_equipe: int, id_utilisateur: int):
    """Exclure un membre (capitaine) ou quitter l'équipe (le membre lui-même) (B-06, B-09).

    403 si l'appelant n'est ni capitaine ni le membre concerné ; 409 si les
    inscriptions sont closes (B-11) ; 422 si le capitaine tente de partir sans
    avoir passé la main.
    """
    equipe_service.retirer_membre(id_equipe, id_utilisateur, utilisateur_courant())
    return ReponseFlask(status=204)