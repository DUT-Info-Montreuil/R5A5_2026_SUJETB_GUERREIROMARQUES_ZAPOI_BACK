"""Accès aux jeux."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Jeu


def lister(session: Session) -> list[Jeu]:
    """Tous les jeux, par ordre alphabétique."""
    return list(session.scalars(select(Jeu).order_by(Jeu.nom_jeu)))


def par_id(session: Session, id_jeu: int) -> Jeu | None:
    """Le jeu d'identifiant donné, ou None."""
    return session.get(Jeu, id_jeu)
