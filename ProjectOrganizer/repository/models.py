from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from repository.database import db


class Utilisateur(db.Model):
    __tablename__ = "utilisateur"

    id_utilisateur: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pseudo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    est_administrateur: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    version_jeton: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
