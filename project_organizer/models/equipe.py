from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class Equipe(Base):
    __tablename__ = "equipe"

    id_equipe: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_tournoi: Mapped[int] = mapped_column(ForeignKey("tournoi.id_tournoi"))
    nom_equipe: Mapped[str] = mapped_column(String(100))
