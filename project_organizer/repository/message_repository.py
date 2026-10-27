"""Accès aux messages de l'espace d'échange."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Message, Utilisateur


def de_l_equipe(session: Session, id_equipe: int) -> list[tuple[Message, str | None]]:
    """Tous les messages de l'équipe, du plus ancien au plus récent, avec le pseudo de l'auteur.

    Le pseudo est None quand le compte de l'auteur a été supprimé.
    """
    requete = (
        select(Message, Utilisateur.pseudo)
        .outerjoin(Utilisateur, Utilisateur.id_utilisateur == Message.id_auteur)
        .where(Message.id_equipe == id_equipe)
        .order_by(Message.envoye_le, Message.id_message)
    )
    return [(message, pseudo) for message, pseudo in session.execute(requete).all()]


def ajouter(session: Session, id_equipe: int, id_auteur: int, contenu: str) -> Message:
    """Enregistre un message de l'auteur dans l'espace d'échange de l'équipe."""
    message = Message(id_equipe=id_equipe, id_auteur=id_auteur, contenu=contenu)
    session.add(message)
    session.flush()
    # Recharge envoye_le, posé par la base.
    session.refresh(message)
    return message
