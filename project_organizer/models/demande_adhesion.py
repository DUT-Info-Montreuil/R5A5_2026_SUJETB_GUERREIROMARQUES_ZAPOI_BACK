from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base
from .types import EnumPostgres

STATUTS_DEMANDE = ("EN_ATTENTE", "ACCEPTEE", "REFUSEE", "ANNULEE")


class DemandeAdhesion(Base):
    """Demande d'un joueur pour rejoindre une équipe (B-06)."""

    __tablename__ = "demande_adhesion"

    id_demande: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_equipe: Mapped[int] = mapped_column(ForeignKey("equipe.id_equipe"))
    id_utilisateur: Mapped[int] = mapped_column(ForeignKey("utilisateur.id_utilisateur"))
    statut_demande: Mapped[str] = mapped_column(
        EnumPostgres(*STATUTS_DEMANDE, nom="statut_demande"), server_default="EN_ATTENTE"
    )
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    traite_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    traite_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id_utilisateur"))