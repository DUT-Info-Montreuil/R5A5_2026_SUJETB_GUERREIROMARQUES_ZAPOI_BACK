"""Ce qui concerne l'utilisateur connecté : ses équipes et ses demandes en attente."""

from datetime import datetime

from pydantic import RootModel

from ..models import DemandeAdhesion, Equipe, Tournoi
from .base import ModeleApi
from .demande_dto import StatutDemande
from .tournoi_dto import StatutEquipe, StatutTournoi


class MonEquipeDto(ModeleApi):
    """Une équipe de l'utilisateur connecté, avec son tournoi et son rôle (capitaine ou non)."""
    id_equipe: int
    nom_equipe: str
    statut_equipe: StatutEquipe
    est_capitaine: bool
    id_tournoi: int
    nom_tournoi: str
    statut_tournoi: StatutTournoi


class ListeMesEquipesDto(RootModel[list[MonEquipeDto]]):
    """Les équipes de l'utilisateur connecté."""
    pass


class MaDemandeDto(ModeleApi):
    """Une demande d'adhésion de l'utilisateur connecté qui attend encore une réponse, avec l'équipe et le tournoi visés.
    """
    id_demande: int
    statut_demande: StatutDemande
    cree_le: datetime
    id_equipe: int
    nom_equipe: str
    id_tournoi: int
    nom_tournoi: str


class ListeMesDemandesDto(RootModel[list[MaDemandeDto]]):
    """Les demandes en attente de l'utilisateur connecté."""
    pass


def mon_equipe_vers_dto(equipe: Equipe, est_capitaine: bool, tournoi: Tournoi) -> MonEquipeDto:
    """Convertit une équipe de l'utilisateur, son rôle et son tournoi en réponse d'API."""
    return MonEquipeDto(
        id_equipe=equipe.id_equipe,
        nom_equipe=equipe.nom_equipe,
        statut_equipe=equipe.statut_equipe,
        est_capitaine=est_capitaine,
        id_tournoi=tournoi.id_tournoi,
        nom_tournoi=tournoi.nom_tournoi,
        statut_tournoi=tournoi.statut_tournoi,
    )


def ma_demande_vers_dto(demande: DemandeAdhesion, equipe: Equipe, tournoi: Tournoi) -> MaDemandeDto:
    """Convertit une demande de l'utilisateur, l'équipe et le tournoi visés en réponse d'API."""
    return MaDemandeDto(
        id_demande=demande.id_demande,
        statut_demande=demande.statut_demande,
        cree_le=demande.cree_le,
        id_equipe=equipe.id_equipe,
        nom_equipe=equipe.nom_equipe,
        id_tournoi=tournoi.id_tournoi,
        nom_tournoi=tournoi.nom_tournoi,
    )
