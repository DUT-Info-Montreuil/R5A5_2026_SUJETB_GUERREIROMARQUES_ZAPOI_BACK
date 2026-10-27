"""Accès aux postes de jeu (table role_jeu)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import RoleJeu


def par_id(session: Session, id_role: int) -> RoleJeu | None:
    """Le poste de jeu d'identifiant donné, ou None."""
    return session.get(RoleJeu, id_role)


def du_jeu(session: Session, id_jeu: int) -> list[RoleJeu]:
    """Les postes d'un jeu, dans l'ordre de leur création (Top, Jungle, Mid…)."""
    return list(session.scalars(select(RoleJeu).where(RoleJeu.id_jeu == id_jeu).order_by(RoleJeu.id_role)))
