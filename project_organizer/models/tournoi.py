"""Modèle de la table tournoi : un tournoi, son jeu, son état et les dates de ses étapes."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..utils.database import Base
from .jeu import Jeu
from .types import EnumPostgres

STATUTS_TOURNOI = ("INSCRIPTIONS_OUVERTES", "INSCRIPTIONS_CLOSES", "EN_COURS", "TERMINE")


class Tournoi(Base):
    """Table tournoi : un tournoi, son jeu, son état et les dates de ses étapes."""
    __tablename__ = "tournoi"

    id_tournoi: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nom_tournoi: Mapped[str] = mapped_column(String(150))
    id_jeu: Mapped[int] = mapped_column(ForeignKey("jeu.id_jeu"))
    statut_tournoi: Mapped[str] = mapped_column(
        EnumPostgres(*STATUTS_TOURNOI, nom="statut_tournoi"), server_default="INSCRIPTIONS_OUVERTES"
    )
    nombre_equipes: Mapped[int] = mapped_column(SmallInteger)
    cree_par: Mapped[int] = mapped_column(ForeignKey("utilisateur.id_utilisateur"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    inscriptions_closes_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    demarre_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    termine_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    jeu: Mapped[Jeu] = relationship(lazy="joined")
