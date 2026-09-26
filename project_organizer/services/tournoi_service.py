"""Règles des tournois."""

from ..models import Tournoi
from ..repository import tournoi_repository
from ..utils import database


def lister(recherche: str | None, statut: str | None) -> list[tuple[Tournoi, int]]:
    with database.session() as session:
        return tournoi_repository.lister(session, recherche.strip() if recherche else None, statut)
