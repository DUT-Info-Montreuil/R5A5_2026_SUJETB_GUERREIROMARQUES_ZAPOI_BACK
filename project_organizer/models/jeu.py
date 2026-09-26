from sqlalchemy import BigInteger, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base


class Jeu(Base):
    __tablename__ = "jeu"

    id_jeu: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nom_jeu: Mapped[str] = mapped_column(String(100))
    joueurs_par_equipe: Mapped[int] = mapped_column(SmallInteger)
