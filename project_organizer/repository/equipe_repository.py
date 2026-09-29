"""Accès aux équipes, vues depuis leur tournoi."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Composer, Equipe


def du_tournoi(session: Session, id_tournoi: int) -> list[tuple[Equipe, int]]:
    """Chaque équipe du tournoi avec son nombre de membres, par ordre d'inscription."""
    nombre_membres = (
        select(func.count()).where(Composer.id_equipe == Equipe.id_equipe).scalar_subquery()
    )
    requete = (
        select(Equipe, nombre_membres)
        .where(Equipe.id_tournoi == id_tournoi)
        .order_by(Equipe.cree_le, Equipe.id_equipe)
    )
    return [(equipe, nombre) for equipe, nombre in session.execute(requete).all()]
