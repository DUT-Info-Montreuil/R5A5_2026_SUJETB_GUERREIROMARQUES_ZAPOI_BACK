"""Rencontres et arbre du tournoi (contrat §5)."""

from typing import Literal

from pydantic import Field, RootModel

from ..models import Rencontre
from .base import ModeleApi, ModeleEntree

StatutRencontre = Literal["EN_ATTENTE", "JOUABLE", "TERMINE"]
TypeResultat = Literal["NORMAL", "FORFAIT", "QUALIFICATION_DIRECTE"]
SCORE_MAX = 999


class EquipeDeRencontreDto(ModeleApi):
    """Une équipe telle qu'elle apparaît dans une rencontre : identifiant et nom."""
    id_equipe: int
    nom_equipe: str


class RencontreDto(ModeleApi):
    """Un nœud de l'arbre. Le front le reconstruit à partir de
    idRencontreSuivante et emplacementSuivant, sans calcul de position."""

    id_rencontre: int
    tour: int
    position: int
    equipe_a: EquipeDeRencontreDto | None = None
    equipe_b: EquipeDeRencontreDto | None = None
    id_vainqueur: int | None = None
    statut_rencontre: StatutRencontre
    type_resultat: TypeResultat | None = None
    score_a: int | None = None
    score_b: int | None = None
    id_rencontre_suivante: int | None = None
    emplacement_suivant: Literal["A", "B"] | None = None


class ArbreDto(RootModel[list[RencontreDto]]):
    """L'arbre d'un tournoi : ses rencontres, par tour puis par position."""
    pass


class ResultatRencontreDto(ModeleEntree):
    """Corps de PATCH /api/rencontres/{id}.

    Les scores ne s'envoient qu'avec un résultat NORMAL, et vont par paire.
    """

    id_vainqueur: int = Field(gt=0)
    type_resultat: TypeResultat
    score_a: int | None = Field(None, ge=0, le=SCORE_MAX)
    score_b: int | None = Field(None, ge=0, le=SCORE_MAX)


def rencontre_vers_dto(rencontre: Rencontre, noms_equipes: dict[int, str]) -> RencontreDto:
    """Convertit une rencontre en réponse d'API ; `noms_equipes` donne le nom de chaque équipe engagée."""
    def equipe(id_equipe: int | None) -> EquipeDeRencontreDto | None:
        if id_equipe is None:
            return None
        return EquipeDeRencontreDto(id_equipe=id_equipe, nom_equipe=noms_equipes[id_equipe])

    return RencontreDto(
        id_rencontre=rencontre.id_rencontre,
        tour=rencontre.tour,
        position=rencontre.position,
        equipe_a=equipe(rencontre.id_equipe_a),
        equipe_b=equipe(rencontre.id_equipe_b),
        id_vainqueur=rencontre.id_vainqueur,
        statut_rencontre=rencontre.statut_rencontre,
        type_resultat=rencontre.type_resultat,
        score_a=rencontre.score_a,
        score_b=rencontre.score_b,
        id_rencontre_suivante=rencontre.id_rencontre_suivante,
        emplacement_suivant=rencontre.emplacement_suivant,
    )
