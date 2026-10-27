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


def _nombre_inscrites():
    return (
        select(func.count(Equipe.id_equipe))
        .where(Equipe.id_tournoi == Tournoi.id_tournoi)
        .scalar_subquery()
    )


def lister(session: Session, recherche: str | None, statut: str | None) -> list[tuple[Tournoi, int]]:
    """Chaque tournoi avec son nombre d'équipes inscrites."""
    requete = select(Tournoi, _nombre_inscrites()).order_by(_ORDRE_DES_STATUTS, Tournoi.cree_le.desc())
    if recherche:
        requete = requete.where(Tournoi.nom_tournoi.ilike(f"%{recherche}%"))
    if statut:
        requete = requete.where(Tournoi.statut_tournoi == statut)
    return [(tournoi, nombre) for tournoi, nombre in session.execute(requete).all()]


def par_id(session: Session, id_tournoi: int, verrouiller: bool = False) -> Tournoi | None:
    """verrouiller : pose un verrou de ligne jusqu'à la fin de la transaction.

    Toute écriture sur l'arbre verrouille d'abord son tournoi : deux
    administrateurs qui valident en même temps passent l'un après l'autre, au
    lieu de propager deux vainqueurs dans la même rencontre suivante.
    """
    requete = select(Tournoi).where(Tournoi.id_tournoi == id_tournoi)
    if verrouiller:
        requete = requete.with_for_update(of=Tournoi)
    return session.scalars(requete).first()


def nombre_equipes_inscrites(session: Session, id_tournoi: int) -> int:
    """Nombre d'équipes inscrites à ce tournoi."""
    return session.scalar(select(func.count(Equipe.id_equipe)).where(Equipe.id_tournoi == id_tournoi)) or 0


def ajouter(session: Session, nom_tournoi: str, id_jeu: int, nombre_equipes: int, cree_par: int) -> Tournoi:
    """Crée un tournoi ; le schéma le fait naître aux inscriptions ouvertes."""
    tournoi = Tournoi(
        nom_tournoi=nom_tournoi,
        id_jeu=id_jeu,
        nombre_equipes=nombre_equipes,
        cree_par=cree_par,
        statut_tournoi="INSCRIPTIONS_OUVERTES",
    )
    session.add(tournoi)
    session.flush()
    # Recharge cree_le (posé par la base) et le jeu (relation) pour la réponse.
    session.refresh(tournoi, ["cree_le", "statut_tournoi", "jeu"])
    return tournoi
