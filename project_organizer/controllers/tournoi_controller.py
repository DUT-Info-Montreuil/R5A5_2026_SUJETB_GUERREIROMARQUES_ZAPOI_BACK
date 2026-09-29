"""Tournois (contrat §3)."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.rencontre_dto import ArbreDto, rencontre_vers_dto
from ..dtos.tournoi_dto import (
    CreationTournoiDto,
    FiltreTournoisDto,
    ListeEquipesDuTournoiDto,
    ListeTournoisDto,
    ModificationTournoiDto,
    TournoiDto,
    equipe_du_tournoi_vers_dto,
    tournoi_complet_vers_dto,
    tournoi_vers_dto,
)
from ..extensions import spec
from ..services import rencontre_service, tournoi_service
from ..utils.authentification import administrateur_requis, publique, utilisateur_courant

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


@tournoi_bp.post("")
@administrateur_requis
@spec.validate(
    body=CreationTournoiDto,
    resp=Response(HTTP_201=TournoiDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto, HTTP_422=ErreurDto),
    tags=["Tournois"],
)
def creer_tournoi():
    """Créer un tournoi (B-01). Administrateur.

    Le tournoi naît INSCRIPTIONS_OUVERTES. nombreEquipes vaut 8 par défaut.
    422 si le jeu n'existe pas.
    """
    donnees: CreationTournoiDto = request.context.body
    tournoi = tournoi_service.creer(
        donnees.nom_tournoi, donnees.id_jeu, donnees.nombre_equipes, utilisateur_courant().id_utilisateur
    )
    return jsonify(tournoi_complet_vers_dto(tournoi, 0).vers_json()), 201


@tournoi_bp.get("/<int:id_tournoi>")
@publique
@spec.validate(resp=Response(HTTP_200=TournoiDto, HTTP_404=ErreurDto), tags=["Tournois"])
def detail_tournoi(id_tournoi: int):
    """Détail d'un tournoi (B-02). Public."""
    tournoi, nombre_inscrites = tournoi_service.detail(id_tournoi)
    return jsonify(tournoi_complet_vers_dto(tournoi, nombre_inscrites).vers_json()), 200


@tournoi_bp.patch("/<int:id_tournoi>")
@administrateur_requis
@spec.validate(
    body=ModificationTournoiDto,
    resp=Response(
        HTTP_200=TournoiDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_409=ErreurDto, HTTP_422=ErreurDto,
    ),
    tags=["Tournois"],
)
def modifier_tournoi(id_tournoi: int):
    """Renommer un tournoi ou le faire changer d'état (B-03, B-04, B-12). Administrateur.

    Transitions permises, chacune dans une seule transaction :

    - INSCRIPTIONS_OUVERTES → INSCRIPTIONS_CLOSES : fige les équipes et génère l'arbre ;
    - INSCRIPTIONS_CLOSES → EN_COURS : déclare forfait les équipes incomplètes ;
    - EN_COURS → TERMINE : la finale doit avoir un vainqueur.

    Toute autre transition : 409. Émet tournoi:maj sur le salon du tournoi.
    """
    donnees: ModificationTournoiDto = request.context.body
    tournoi, nombre_inscrites = tournoi_service.modifier(id_tournoi, donnees.nom_tournoi, donnees.statut_tournoi)
    return jsonify(tournoi_complet_vers_dto(tournoi, nombre_inscrites).vers_json()), 200


@tournoi_bp.get("/<int:id_tournoi>/equipes")
@publique
@spec.validate(resp=Response(HTTP_200=ListeEquipesDuTournoiDto, HTTP_404=ErreurDto), tags=["Tournois"])
def equipes_du_tournoi(id_tournoi: int):
    """Les équipes inscrites, par ordre d'inscription (B-02). Public."""
    equipes = tournoi_service.equipes(id_tournoi)
    return jsonify([equipe_du_tournoi_vers_dto(e, n).vers_json() for e, n in equipes]), 200


@tournoi_bp.get("/<int:id_tournoi>/arbre")
@publique
@spec.validate(resp=Response(HTTP_200=ArbreDto, HTTP_404=ErreurDto), tags=["Tournois"])
def arbre_du_tournoi(id_tournoi: int):
    """L'arbre du tournoi (B-12, B-19). Public.

    Vide tant que les inscriptions sont ouvertes. Le front le reconstruit à
    partir de idRencontreSuivante et emplacementSuivant.
    """
    rencontres, noms = rencontre_service.arbre(id_tournoi)
    return jsonify([rencontre_vers_dto(r, noms).vers_json() for r in rencontres]), 200
