"""Accès aux rencontres de l'arbre."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Rencontre


def du_tournoi(session: Session, id_tournoi: int) -> list[Rencontre]:
    """Du premier tour à la finale, de haut en bas dans chaque tour."""
    requete = (
        select(Rencontre)
        .where(Rencontre.id_tournoi == id_tournoi)
        .order_by(Rencontre.tour, Rencontre.position)
    )
    return list(session.scalars(requete))


def id_tournoi_de(session: Session, id_rencontre: int) -> int | None:
    """Le tournoi d'une rencontre, ou None si elle n'existe pas : le service s'en sert pour verrouiller le tournoi avant de la modifier.
    """
    return session.scalar(select(Rencontre.id_tournoi).where(Rencontre.id_rencontre == id_rencontre))


def ajouter(session: Session, rencontre: Rencontre) -> Rencontre:
    """Insère une rencontre de l'arbre."""
    session.add(rencontre)
    # flush : l'identifiant sert aussitôt aux rencontres du tour précédent.
    session.flush()
    return rencontre
