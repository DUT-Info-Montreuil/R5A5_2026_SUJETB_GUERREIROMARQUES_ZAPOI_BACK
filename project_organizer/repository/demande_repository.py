"""Accès aux demandes d'adhésion."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DemandeAdhesion, Equipe, Tournoi, Utilisateur


def par_id(session: Session, id_demande: int) -> DemandeAdhesion | None:
    """La demande d'adhésion d'identifiant donné, ou None."""
    return session.get(DemandeAdhesion, id_demande)


def en_attente_existe(session: Session, id_equipe: int, id_utilisateur: int) -> bool:
    """Vrai si ce joueur a déjà une demande EN_ATTENTE pour cette équipe."""
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
    """Crée une demande d'adhésion EN_ATTENTE."""
    demande = DemandeAdhesion(id_equipe=id_equipe, id_utilisateur=id_utilisateur, statut_demande="EN_ATTENTE")
    session.add(demande)
    session.flush()
    # Recharge cree_le, posé par la base.
    session.refresh(demande)
    return demande

def en_attente_de(session: Session, id_utilisateur: int) -> list[tuple[DemandeAdhesion, Equipe, Tournoi]]:
    """Les demandes d'un joueur qui attendent encore une réponse, avec l'équipe et le tournoi visés."""
    requete = (
        select(DemandeAdhesion, Equipe, Tournoi)
        .join(Equipe, Equipe.id_equipe == DemandeAdhesion.id_equipe)
        .join(Tournoi, Tournoi.id_tournoi == Equipe.id_tournoi)
        .where(DemandeAdhesion.id_utilisateur == id_utilisateur, DemandeAdhesion.statut_demande == "EN_ATTENTE")
        .order_by(DemandeAdhesion.cree_le.desc(), DemandeAdhesion.id_demande.desc())
    )
    return [(demande, equipe, tournoi) for demande, equipe, tournoi in session.execute(requete).all()]
