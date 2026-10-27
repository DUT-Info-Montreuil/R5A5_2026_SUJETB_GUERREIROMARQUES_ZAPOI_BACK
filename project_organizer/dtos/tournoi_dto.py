"""Tournois (contrat §3)."""

from datetime import datetime
from typing import Literal

from pydantic import Field, RootModel, field_validator

from ..models import Equipe, Jeu, Tournoi
from .base import ModeleApi, ModeleEntree

StatutTournoi = Literal["INSCRIPTIONS_OUVERTES", "INSCRIPTIONS_CLOSES", "EN_COURS", "TERMINE"]
StatutEquipe = Literal["EN_LICE", "ELIMINEE", "DISQUALIFIEE", "VAINQUEUR"]
# Le sujet impose 8 équipes (B-12) ; le schéma accepte toute puissance de 2 jusqu'à 16.
NombreEquipes = Literal[2, 4, 8, 16]
NOMBRE_EQUIPES_PAR_DEFAUT = 8


class FiltreTournoisDto(ModeleEntree):
    """Paramètres de GET /api/tournois?recherche=…&statut=…"""

    recherche: str | None = Field(None, max_length=150, description="Texte cherché dans le nom du tournoi")
    statut: StatutTournoi | None = None


class JeuDto(ModeleApi):
    """Un jeu proposé aux tournois, avec la taille de ses équipes."""
    id_jeu: int
    nom_jeu: str
    joueurs_par_equipe: int


class ListeJeuxDto(RootModel[list[JeuDto]]):
    """Les jeux disponibles, par ordre alphabétique."""
    pass


class TournoiResumeDto(ModeleApi):
    """Un tournoi vu dans une liste : nom, jeu, état et remplissage."""
    id_tournoi: int
    nom_tournoi: str
    jeu: JeuDto
    statut_tournoi: StatutTournoi
    nombre_equipes: int
    nombre_equipes_inscrites: int
    cree_le: datetime


class ListeTournoisDto(RootModel[list[TournoiResumeDto]]):
    """Une liste de tournois."""
    pass


class TournoiDto(TournoiResumeDto):
    """L'objet Tournoi complet : détail, création, modification, événement tournoi:maj."""

    inscriptions_closes_le: datetime | None = None
    demarre_le: datetime | None = None
    termine_le: datetime | None = None


def _nom_non_vide(valeur: str | None) -> str | None:
    if valeur is None:
        return None
    valeur = valeur.strip()
    if not valeur:
        raise ValueError("Le nom ne peut pas être vide.")
    return valeur


class CreationTournoiDto(ModeleEntree):
    """Corps de POST /api/tournois : nom, jeu et nombre d'équipes (8 par défaut ; 2, 4 ou 16 acceptés)."""
    nom_tournoi: str = Field(max_length=150, examples=["Coupe de printemps"])
    id_jeu: int = Field(gt=0, examples=[1])
    nombre_equipes: NombreEquipes = NOMBRE_EQUIPES_PAR_DEFAUT

    @field_validator("nom_tournoi")
    @classmethod
    def _nom(cls, valeur: str | None) -> str | None:
        return _nom_non_vide(valeur)


class ModificationTournoiDto(ModeleEntree):
    """Liste blanche de PATCH /api/tournois/{id} (contrat §1.4) : tout autre champ → 400.

    Changer statutTournoi déclenche une transition d'état et ses effets (§3).
    """

    nom_tournoi: str | None = Field(None, max_length=150)
    statut_tournoi: StatutTournoi | None = None

    @field_validator("nom_tournoi")
    @classmethod
    def _nom(cls, valeur: str | None) -> str | None:
        return _nom_non_vide(valeur)


class EquipeDuTournoiDto(ModeleApi):
    """Une équipe inscrite à un tournoi : effectif et état dans la compétition."""
    id_equipe: int
    nom_equipe: str
    statut_equipe: StatutEquipe
    motif_sortie: str | None = None
    nombre_membres: int


class ListeEquipesDuTournoiDto(RootModel[list[EquipeDuTournoiDto]]):
    """Les équipes d'un tournoi, par ordre d'inscription."""
    pass


def jeu_vers_dto(jeu: Jeu) -> JeuDto:
    """Convertit un jeu en réponse d'API."""
    return JeuDto(id_jeu=jeu.id_jeu, nom_jeu=jeu.nom_jeu, joueurs_par_equipe=jeu.joueurs_par_equipe)


def tournoi_vers_dto(tournoi: Tournoi, nombre_equipes_inscrites: int) -> TournoiResumeDto:
    """Convertit un tournoi en réponse d'API de liste, avec le nombre d'équipes inscrites."""
    return TournoiResumeDto(
        id_tournoi=tournoi.id_tournoi,
        nom_tournoi=tournoi.nom_tournoi,
        jeu=jeu_vers_dto(tournoi.jeu),
        statut_tournoi=tournoi.statut_tournoi,
        nombre_equipes=tournoi.nombre_equipes,
        nombre_equipes_inscrites=nombre_equipes_inscrites,
        cree_le=tournoi.cree_le,
    )


def tournoi_complet_vers_dto(tournoi: Tournoi, nombre_equipes_inscrites: int) -> TournoiDto:
    """Convertit un tournoi en réponse d'API complète : celle de la liste, plus les dates des étapes atteintes."""
    return TournoiDto(
        **tournoi_vers_dto(tournoi, nombre_equipes_inscrites).model_dump(),
        inscriptions_closes_le=tournoi.inscriptions_closes_le,
        demarre_le=tournoi.demarre_le,
        termine_le=tournoi.termine_le,
    )


def equipe_du_tournoi_vers_dto(equipe: Equipe, nombre_membres: int) -> EquipeDuTournoiDto:
    """Convertit une équipe inscrite et son effectif en réponse d'API."""
    return EquipeDuTournoiDto(
        id_equipe=equipe.id_equipe,
        nom_equipe=equipe.nom_equipe,
        statut_equipe=equipe.statut_equipe,
        motif_sortie=equipe.motif_sortie,
        nombre_membres=nombre_membres,
    )
