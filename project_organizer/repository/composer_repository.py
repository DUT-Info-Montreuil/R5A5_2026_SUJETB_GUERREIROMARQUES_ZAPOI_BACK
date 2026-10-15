"""Accès à la composition des équipes (table composer)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Composer, RoleJeu, Utilisateur


def membres_de(session: Session, id_equipe: int) -> list[tuple[Composer, str, str | None]]:
    """Chaque membre avec son pseudo et le libellé de son poste, par ordre d'arrivée."""
    requete = (
        select(Composer, Utilisateur.pseudo, RoleJeu.libelle_role)
        .join(Utilisateur, Utilisateur.id_utilisateur == Composer.id_utilisateur)
        .outerjoin(RoleJeu, RoleJeu.id_role == Composer.id_role)
        .where(Composer.id_equipe == id_equipe)
        .order_by(Composer.rejoint_le, Composer.id_utilisateur)
    )
    return [(membre, pseudo, libelle) for membre, pseudo, libelle in session.execute(requete).all()]


def membre(session: Session, id_equipe: int, id_utilisateur: int) -> Composer | None:
    return session.get(Composer, (id_equipe, id_utilisateur))


def capitaine_de(session: Session, id_equipe: int) -> Composer | None:
    requete = select(Composer).where(Composer.id_equipe == id_equipe, Composer.est_capitaine.is_(True))
    return session.scalars(requete).first()


def equipe_du_joueur(session: Session, id_tournoi: int, id_utilisateur: int) -> int | None:
    """L'équipe du joueur dans ce tournoi, ou None (B-07 : une seule par tournoi)."""
    requete = select(Composer.id_equipe).where(
        Composer.id_tournoi == id_tournoi, Composer.id_utilisateur == id_utilisateur
    )
    return session.scalars(requete).first()


def compter(session: Session, id_equipe: int) -> int:
    return session.scalar(select(func.count()).select_from(Composer).where(Composer.id_equipe == id_equipe)) or 0


def poste_occupe(session: Session, id_equipe: int, id_role: int, sauf_utilisateur: int) -> bool:
    """Le poste est-il tenu par un autre membre de l'équipe ? (B-08)"""
    requete = select(Composer.id_utilisateur).where(
        Composer.id_equipe == id_equipe,
        Composer.id_role == id_role,
        Composer.id_utilisateur != sauf_utilisateur,
    )
    return session.scalars(requete).first() is not None


def ajouter(
    session: Session, id_equipe: int, id_tournoi: int, id_utilisateur: int,
    id_role: int | None, est_capitaine: bool,
) -> Composer:
    composer = Composer(
        id_equipe=id_equipe,
        id_tournoi=id_tournoi,
        id_utilisateur=id_utilisateur,
        id_role=id_role,
        est_capitaine=est_capitaine,
    )
    session.add(composer)
    session.flush()
    return composer


def supprimer(session: Session, composer: Composer) -> None:
    session.delete(composer)
    session.flush()