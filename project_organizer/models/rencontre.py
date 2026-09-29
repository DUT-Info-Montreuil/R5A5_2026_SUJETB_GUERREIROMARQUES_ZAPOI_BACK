from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..utils.database import Base
from .types import EnumPostgres

STATUTS_RENCONTRE = ("EN_ATTENTE", "JOUABLE", "TERMINE")
TYPES_RESULTAT = ("NORMAL", "FORFAIT", "QUALIFICATION_DIRECTE")


class Rencontre(Base):
    """Un match de l'arbre. Nommée « rencontre » : « match » est réservé en SQL."""

    __tablename__ = "rencontre"

    id_rencontre: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_tournoi: Mapped[int] = mapped_column(ForeignKey("tournoi.id_tournoi"))
    tour: Mapped[int] = mapped_column(SmallInteger)
    position: Mapped[int] = mapped_column(SmallInteger)

    id_equipe_a: Mapped[int | None] = mapped_column(ForeignKey("equipe.id_equipe"))
    id_equipe_b: Mapped[int | None] = mapped_column(ForeignKey("equipe.id_equipe"))
    id_vainqueur: Mapped[int | None] = mapped_column(ForeignKey("equipe.id_equipe"))

    statut_rencontre: Mapped[str] = mapped_column(
        EnumPostgres(*STATUTS_RENCONTRE, nom="statut_match"), server_default="EN_ATTENTE"
    )
    type_resultat: Mapped[str | None] = mapped_column(EnumPostgres(*TYPES_RESULTAT, nom="type_resultat"))
    score_a: Mapped[int | None] = mapped_column(SmallInteger)
    score_b: Mapped[int | None] = mapped_column(SmallInteger)
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    id_rencontre_suivante: Mapped[int | None] = mapped_column(ForeignKey("rencontre.id_rencontre"))
    emplacement_suivant: Mapped[str | None] = mapped_column(String(1))
