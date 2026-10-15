"""Accès aux demandes d'adhésion."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DemandeAdhesion, Utilisateur


def par_id(session: Session, id_demande: int) -> DemandeAdhesion | None:
    return session.get(DemandeAdhesion, id_demande)


def en_attente_existe(session: Session, id_equipe: int, id_utilisateur: int) -> bool:
    requete = select(DemandeAdhesion.id_demande).where(
        DemandeAdhesion.id_equipe == id_equipe,
        DemandeAdhesion.id_utilisateur == id_utilisateur,
        DemandeAdhesion.statut_demande == "EN_ATTENTE",
    )
    return session.scalars(requete).first() is not None


def de_l_equipe(session: Session, id_equipe: int, statut: str | None) -> list[tuple[DemandeAdhesion, str]]:
    """Les demandes d'une équipe avec le pseudo du demandeur, les plus récentes d'abord."""
    requete = (
        select(DemandeAdhesion, Utilisateur.pseudo)
        .join(Utilisateur, Utilisateur.id_utilisateur == DemandeAdhesion.id_utilisateur)
        .where(DemandeAdhesion.id_equipe == id_equipe)
        .order_by(DemandeAdhesion.cree_le.desc(), DemandeAdhesion.id_demande.desc())
    )
    if statut:
        requete = requete.where(DemandeAdhesion.statut_demande == statut)
    return [(demande, pseudo) for demande, pseudo in session.execute(requete).all()]


def ajouter(session: Session, id_equipe: int, id_utilisateur: int) -> DemandeAdhesion:
    demande = DemandeAdhesion(id_equipe=id_equipe, id_utilisateur=id_utilisateur, statut_demande="EN_ATTENTE")
    session.add(demande)
    session.flush()
    # Recharge cree_le, posé par la base.
    session.refresh(demande)
    return demande