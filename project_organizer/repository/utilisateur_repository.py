"""Accès à la table utilisateur (ORM : requêtes d'une ligne)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Utilisateur


def par_id(session: Session, id_utilisateur: int) -> Utilisateur | None:
    return session.get(Utilisateur, id_utilisateur)


def par_email(session: Session, email: str) -> Utilisateur | None:
    return session.scalars(select(Utilisateur).where(Utilisateur.email == email)).first()


def pseudo_existe(session: Session, pseudo: str) -> bool:
    return session.scalars(select(Utilisateur.id_utilisateur).where(Utilisateur.pseudo == pseudo)).first() is not None


def ajouter(session: Session, pseudo: str, email: str, mot_de_passe_hash: str) -> Utilisateur:
    utilisateur = Utilisateur(pseudo=pseudo, email=email, mot_de_passe_hash=mot_de_passe_hash)
    session.add(utilisateur)
    # flush : PostgreSQL attribue l'identifiant sans attendre la fin de la transaction.
    session.flush()
    return utilisateur
