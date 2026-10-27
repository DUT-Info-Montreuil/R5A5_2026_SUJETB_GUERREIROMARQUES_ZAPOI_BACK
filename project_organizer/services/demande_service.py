"""
Demandes d'adhésion (contrat §4, B-06) : un joueur demande à rejoindre une
équipe, son capitaine accepte ou refuse.

Les demandes ne sont visibles que du capitaine concerné : pour tout autre
appelant, y compris l'administrateur, elles n'existent pas (404, contrat §1.3).
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import DemandeAdhesion, Utilisateur
from ..repository import composer_repository, demande_repository, equipe_repository, utilisateur_repository
from ..utils import database
from ..utils.erreurs import Conflict, NotFound, UnprocessableEntity
from .equipe_service import equipe_ou_404, est_capitaine, exiger_inscriptions_ouvertes
from .tournoi_service import tournoi_ou_404

logger = logging.getLogger(__name__)

MESSAGE_INTROUVABLE = "Ressource introuvable."


def creer(id_equipe: int, demandeur: Utilisateur) -> tuple[DemandeAdhesion, str]:
    """B-06 : demander à rejoindre une équipe."""
    with database.session() as session:
        equipe = equipe_ou_404(session, id_equipe)
        tournoi = tournoi_ou_404(session, equipe.id_tournoi, verrouiller=True)
        exiger_inscriptions_ouvertes(tournoi)

        if composer_repository.equipe_du_joueur(session, tournoi.id_tournoi, demandeur.id_utilisateur) is not None:
            raise UnprocessableEntity("Vous avez déjà une équipe dans ce tournoi.")
        _exiger_une_place(session, id_equipe, tournoi.jeu.joueurs_par_equipe)
        if demande_repository.en_attente_existe(session, id_equipe, demandeur.id_utilisateur):
            raise Conflict("Vous avez déjà une demande en attente pour cette équipe.")

        demande = demande_repository.ajouter(session, id_equipe, demandeur.id_utilisateur)

    logger.info(
        "Demande d'adhésion créée",
        extra={"contexte": {"idDemande": demande.id_demande, "idEquipe": id_equipe}},
    )
    return demande, demandeur.pseudo


def lister(id_equipe: int, appelant: Utilisateur, statut: str | None) -> list[tuple[DemandeAdhesion, str]]:
    """Les demandes de l'équipe, pour son capitaine seulement."""
    with database.session() as session:
        equipe_ou_404(session, id_equipe)
        if not est_capitaine(session, id_equipe, appelant.id_utilisateur):
            raise NotFound(MESSAGE_INTROUVABLE)
        return demande_repository.de_l_equipe(session, id_equipe, statut)


def traiter(id_demande: int, capitaine: Utilisateur, statut: str) -> tuple[DemandeAdhesion, str]:
    """Le capitaine accepte (le joueur entre dans l'équipe, même transaction) ou refuse."""
    with database.session() as session:
        demande = demande_repository.par_id(session, id_demande)
        if demande is None:
            raise NotFound(MESSAGE_INTROUVABLE)
        equipe = equipe_repository.par_id(session, demande.id_equipe)
        # Une demande dont on n'est pas le capitaine n'existe pas : 404, pas 403.
        if not est_capitaine(session, equipe.id_equipe, capitaine.id_utilisateur):
            raise NotFound(MESSAGE_INTROUVABLE)

        tournoi = tournoi_ou_404(session, equipe.id_tournoi, verrouiller=True)
        # Relue après le verrou : un autre traitement a pu passer entre-temps.
        session.refresh(demande)
        if demande.statut_demande != "EN_ATTENTE":
            raise Conflict("Cette demande a déjà été traitée.")
        exiger_inscriptions_ouvertes(tournoi)

        if statut == "ACCEPTEE":
            if composer_repository.equipe_du_joueur(session, tournoi.id_tournoi, demande.id_utilisateur) is not None:
                raise UnprocessableEntity("Ce joueur a déjà rejoint une équipe de ce tournoi.")
            _exiger_une_place(session, equipe.id_equipe, tournoi.jeu.joueurs_par_equipe)
            # Sans poste : le capitaine l'attribue ensuite (B-08).
            composer_repository.ajouter(
                session, equipe.id_equipe, tournoi.id_tournoi, demande.id_utilisateur, None, est_capitaine=False
            )

        demande.statut_demande = statut
        demande.traite_le = func.now()
        demande.traite_par = capitaine.id_utilisateur
        session.flush()
        session.refresh(demande)
        demandeur = utilisateur_repository.par_id(session, demande.id_utilisateur)

    logger.info(
        "Demande d'adhésion traitée",
        extra={"contexte": {"idDemande": id_demande, "idEquipe": equipe.id_equipe, "statut": statut}},
    )
    return demande, demandeur.pseudo


def _exiger_une_place(session: Session, id_equipe: int, joueurs_par_equipe: int) -> None:
    if composer_repository.compter(session, id_equipe) >= joueurs_par_equipe:
        raise UnprocessableEntity("Cette équipe est déjà complète.")