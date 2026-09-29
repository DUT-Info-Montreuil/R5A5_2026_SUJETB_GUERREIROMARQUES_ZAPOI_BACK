from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class Composer(Base):
    """Appartenance d'un joueur à une équipe."""

    __tablename__ = "composer"

    id_equipe: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_utilisateur: Mapped[int] = mapped_column(ForeignKey("utilisateur.id_utilisateur"), primary_key=True)
    id_tournoi: Mapped[int] = mapped_column(BigInteger)
    id_role: Mapped[int | None] = mapped_column(ForeignKey("role_jeu.id_role"))
    est_capitaine: Mapped[bool] = mapped_column(Boolean, default=False)
    rejoint_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
