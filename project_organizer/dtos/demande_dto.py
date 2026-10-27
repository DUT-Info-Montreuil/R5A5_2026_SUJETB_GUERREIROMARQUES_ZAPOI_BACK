"""Demandes d'adhésion (contrat §4, B-06)."""

from datetime import datetime
from typing import Literal

from pydantic import Field, RootModel

from ..models import DemandeAdhesion
from .base import ModeleApi, ModeleEntree

StatutDemande = Literal["EN_ATTENTE", "ACCEPTEE", "REFUSEE", "ANNULEE"]


class FiltreDemandesDto(ModeleEntree):
    """Paramètre de GET /api/equipes/{id}/demandes?statut=…"""

    statut: StatutDemande | None = Field(None, description="Sans filtre : tout l'historique")


class TraitementDemandeDto(ModeleEntree):
    """Corps de PATCH /api/demandes/{id} : le capitaine accepte ou refuse."""

    statut_demande: Literal["ACCEPTEE", "REFUSEE"]


class DemandeDto(ModeleApi):
    """Une demande d'adhésion vue par le capitaine : qui demande, quand, et où elle en est."""
    id_demande: int
    id_equipe: int
    id_utilisateur: int
    pseudo: str
    statut_demande: StatutDemande
    cree_le: datetime
    traite_le: datetime | None = None


class ListeDemandesDto(RootModel[list[DemandeDto]]):
    """Liste de demandes d'adhésion."""
    pass


def demande_vers_dto(demande: DemandeAdhesion, pseudo: str) -> DemandeDto:
    """Convertit une demande en réponse d'API, avec le pseudo du demandeur."""
    return DemandeDto(
        id_demande=demande.id_demande,
        id_equipe=demande.id_equipe,
        id_utilisateur=demande.id_utilisateur,
        pseudo=pseudo,
        statut_demande=demande.statut_demande,
        cree_le=demande.cree_le,
        traite_le=demande.traite_le,
    )
