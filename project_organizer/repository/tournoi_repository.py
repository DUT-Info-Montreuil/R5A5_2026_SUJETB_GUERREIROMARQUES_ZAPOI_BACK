"""Accès aux tournois."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import Equipe, Tournoi

# Ordre d'affichage : ce qui se joue maintenant, puis ce qui recrute, puis le reste.
_ORDRE_DES_STATUTS = case(
    *((Tournoi.statut_tournoi == statut, rang) for rang, statut in enumerate(
        ("EN_COURS", "INSCRIPTIONS_OUVERTES", "INSCRIPTIONS_CLOSES", "TERMINE")
    )),
)


def lister(session: Session, recherche: str | None, statut: str | None) -> list[tuple[Tournoi, int]]:
    """Chaque tournoi avec son nombre d'équipes inscrites."""
    nombre_inscrites = (
        select(func.count(Equipe.id_equipe))
        .where(Equipe.id_tournoi == Tournoi.id_tournoi)
        .scalar_subquery()
    )
    requete = select(Tournoi, nombre_inscrites).order_by(_ORDRE_DES_STATUTS, Tournoi.cree_le.desc())
    if recherche:
        requete = requete.where(Tournoi.nom_tournoi.ilike(f"%{recherche}%"))
    if statut:
        requete = requete.where(Tournoi.statut_tournoi == statut)
    return [(tournoi, nombre) for tournoi, nombre in session.execute(requete).all()]
