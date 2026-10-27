"""Modèle de la table role_jeu : un poste proposé par un jeu."""

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class RoleJeu(Base):
    """Un poste proposé par un jeu (Top, Jungle, Tank…)."""

    __tablename__ = "role_jeu"

    id_role: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_jeu: Mapped[int] = mapped_column(ForeignKey("jeu.id_jeu"))
    libelle_role: Mapped[str] = mapped_column(String(50))