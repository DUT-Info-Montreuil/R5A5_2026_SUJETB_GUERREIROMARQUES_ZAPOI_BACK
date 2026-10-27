"""Modèle de la table message : un message de l'espace d'échange d'une équipe."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class Message(Base):
    """Un message de l'espace d'échange d'une équipe (B-16).

    L'auteur est une référence à l'utilisateur, pas à la composition : un
    joueur exclu (B-17) perd sa ligne `composer`, ses messages doivent rester.
    """

    __tablename__ = "message"

    id_message: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_equipe: Mapped[int] = mapped_column(ForeignKey("equipe.id_equipe"))
    id_auteur: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id_utilisateur"))
    contenu: Mapped[str] = mapped_column(Text)
    envoye_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
