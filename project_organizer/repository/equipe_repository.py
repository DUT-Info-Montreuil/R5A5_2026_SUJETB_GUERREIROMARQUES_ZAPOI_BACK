"""Accès aux équipes."""

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


def par_id(session: Session, id_equipe: int) -> Equipe | None:
    return session.get(Equipe, id_equipe)


def nom_pris(session: Session, id_tournoi: int, nom_equipe: str, sauf_equipe: int | None = None) -> bool:
    """Un nom est unique dans un tournoi, sans tenir compte de la casse."""
    requete = select(Equipe.id_equipe).where(
        Equipe.id_tournoi == id_tournoi, func.lower(Equipe.nom_equipe) == nom_equipe.lower()
    )
    if sauf_equipe is not None:
        requete = requete.where(Equipe.id_equipe != sauf_equipe)
    return session.scalars(requete).first() is not None


def ajouter(session: Session, id_tournoi: int, nom_equipe: str) -> Equipe:
    equipe = Equipe(id_tournoi=id_tournoi, nom_equipe=nom_equipe, statut_equipe="EN_LICE")
    session.add(equipe)
    session.flush()
    # Recharge cree_le, posé par la base.
    session.refresh(equipe)
    return equipe