from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base
from .types import EnumPostgres

STATUTS_EQUIPE = ("EN_LICE", "ELIMINEE", "DISQUALIFIEE", "VAINQUEUR")


class Equipe(Base):
    __tablename__ = "equipe"

    id_equipe: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_tournoi: Mapped[int] = mapped_column(ForeignKey("tournoi.id_tournoi"))
    nom_equipe: Mapped[str] = mapped_column(String(100))
    statut_equipe: Mapped[str] = mapped_column(
        EnumPostgres(*STATUTS_EQUIPE, nom="statut_equipe"), server_default="EN_LICE"
    )
    motif_sortie: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
