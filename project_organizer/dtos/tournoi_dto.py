"""Tournois (contrat §3)."""

from datetime import datetime
from typing import Literal

from pydantic import Field, RootModel

from ..models import Tournoi
from .base import ModeleApi, ModeleEntree

StatutTournoi = Literal["INSCRIPTIONS_OUVERTES", "INSCRIPTIONS_CLOSES", "EN_COURS", "TERMINE"]


class FiltreTournoisDto(ModeleEntree):
    """Paramètres de GET /api/tournois?recherche=…&statut=…"""

    recherche: str | None = Field(None, max_length=150, description="Texte cherché dans le nom du tournoi")
    statut: StatutTournoi | None = None


class JeuDto(ModeleApi):
    id_jeu: int
    nom_jeu: str
    joueurs_par_equipe: int


class TournoiResumeDto(ModeleApi):
    id_tournoi: int
    nom_tournoi: str
    jeu: JeuDto
    statut_tournoi: StatutTournoi
    nombre_equipes: int
    nombre_equipes_inscrites: int
    cree_le: datetime


class ListeTournoisDto(RootModel[list[TournoiResumeDto]]):
    pass


def tournoi_vers_dto(tournoi: Tournoi, nombre_equipes_inscrites: int) -> TournoiResumeDto:
    return TournoiResumeDto(
        id_tournoi=tournoi.id_tournoi,
        nom_tournoi=tournoi.nom_tournoi,
        jeu=JeuDto(
            id_jeu=tournoi.jeu.id_jeu,
            nom_jeu=tournoi.jeu.nom_jeu,
            joueurs_par_equipe=tournoi.jeu.joueurs_par_equipe,
        ),
        statut_tournoi=tournoi.statut_tournoi,
        nombre_equipes=tournoi.nombre_equipes,
        nombre_equipes_inscrites=nombre_equipes_inscrites,
        cree_le=tournoi.cree_le,
    )
