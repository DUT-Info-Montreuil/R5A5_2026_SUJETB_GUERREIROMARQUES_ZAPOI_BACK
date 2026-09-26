from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id_utilisateur: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pseudo: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(255))
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    est_administrateur: Mapped[bool] = mapped_column(Boolean, default=False)
    version_jeton: Mapped[int] = mapped_column(Integer, default=1)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
