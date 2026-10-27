"""Équipes et composition (contrat §4)."""

from typing import Literal

from pydantic import Field, RootModel, field_validator

from ..models import Composer, Equipe, RoleJeu
from .base import ModeleApi, ModeleEntree
from .tournoi_dto import StatutEquipe

LONGUEUR_MAX_NOM_EQUIPE = 100
LONGUEUR_MAX_MOTIF = 500


def _texte_non_vide(valeur: str | None, message: str) -> str | None:
    if valeur is None:
        return None
    valeur = valeur.strip()
    if not valeur:
        raise ValueError(message)
    return valeur


# --- Entrées ------------------------------------------------------------------

class CreationEquipeDto(ModeleEntree):
    """Corps de POST /api/tournois/{id}/equipes. idRole est le poste du créateur."""

    nom_equipe: str = Field(max_length=LONGUEUR_MAX_NOM_EQUIPE, examples=["Les Rouges"])
    id_role: int = Field(gt=0, examples=[3])

    @field_validator("nom_equipe")
    @classmethod
    def _nom(cls, valeur: str) -> str | None:
        return _texte_non_vide(valeur, "Le nom ne peut pas être vide.")


class ModificationEquipeDto(ModeleEntree):
    """Liste blanche de PATCH /api/equipes/{id} (contrat §1.4).

    nomEquipe : capitaine. statutEquipe et motifSortie : administrateur.
    Seule la disqualification se demande : VAINQUEUR et ELIMINEE sont calculés
    par l'API, jamais écrits par un client.
    """

    nom_equipe: str | None = Field(None, max_length=LONGUEUR_MAX_NOM_EQUIPE)
    statut_equipe: Literal["DISQUALIFIEE"] | None = None
    motif_sortie: str | None = Field(None, max_length=LONGUEUR_MAX_MOTIF)

    @field_validator("nom_equipe")
    @classmethod
    def _nom(cls, valeur: str | None) -> str | None:
        return _texte_non_vide(valeur, "Le nom ne peut pas être vide.")

    @field_validator("motif_sortie")
    @classmethod
    def _motif(cls, valeur: str | None) -> str | None:
        return _texte_non_vide(valeur, "Le motif ne peut pas être vide.")


class ModificationMembreDto(ModeleEntree):
    """Corps de PATCH /api/equipes/{id}/membres/{idUtilisateur} (capitaine).

    idRole : attribue un poste (B-08). estCapitaine : passe la main (B-09) ;
    seule la valeur true existe, le capitanat ne se retire pas, il se transmet.
    """

    id_role: int | None = Field(None, gt=0)
    est_capitaine: Literal[True] | None = None


# --- Sorties ------------------------------------------------------------------

class RoleJeuDto(ModeleApi):
    """Un poste proposé par un jeu (Top, Tank, Duelliste…)."""
    id_role: int
    libelle_role: str


class ListeRolesDto(RootModel[list[RoleJeuDto]]):
    """Les postes d'un jeu."""
    pass


class MembreDto(ModeleApi):
    """Un membre d'équipe : pseudo, capitaine ou non, et son poste s'il en a un."""
    id_utilisateur: int
    pseudo: str
    est_capitaine: bool
    role: RoleJeuDto | None = None


class EquipeDto(ModeleApi):
    """L'équipe et ses membres : réponse de toutes les routes d'écriture d'équipe."""

    id_equipe: int
    id_tournoi: int
    nom_equipe: str
    statut_equipe: StatutEquipe
    motif_sortie: str | None = None
    membres: list[MembreDto]


def role_vers_dto(role: RoleJeu) -> RoleJeuDto:
    """Convertit un poste de jeu en réponse d'API."""
    return RoleJeuDto(id_role=role.id_role, libelle_role=role.libelle_role)


def equipe_vers_dto(equipe: Equipe, membres: list[tuple[Composer, str, str | None]]) -> EquipeDto:
    """Convertit une équipe et ses membres (liaison, pseudo, poste) en réponse d'API."""
    return EquipeDto(
        id_equipe=equipe.id_equipe,
        id_tournoi=equipe.id_tournoi,
        nom_equipe=equipe.nom_equipe,
        statut_equipe=equipe.statut_equipe,
        motif_sortie=equipe.motif_sortie,
        membres=[
            MembreDto(
                id_utilisateur=composer.id_utilisateur,
                pseudo=pseudo,
                est_capitaine=composer.est_capitaine,
                role=RoleJeuDto(id_role=composer.id_role, libelle_role=libelle) if composer.id_role else None,
            )
            for composer, pseudo, libelle in membres
        ],
    )
