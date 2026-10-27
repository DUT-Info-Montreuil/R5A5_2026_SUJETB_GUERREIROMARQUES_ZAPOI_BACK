"""
Espace d'échange d'une équipe (contrat §6, B-16 à B-18).

Une seule fonction décide qui a le droit : `verifier_acces`. Elle est appelée
par la route de lecture, la route d'écriture ET le gestionnaire d'abonnement
WebSocket. Trois implémentations séparées, ce serait trois occasions de
diverger — et ce sont précisément les points que visent les tests de sécurité.

    Lecture   membre de l'équipe ET équipe EN_LICE, ou administrateur (B-18)
    Écriture  membre de l'équipe ET équipe EN_LICE. L'administrateur lit, n'écrit pas.

Pour qui n'a pas accès, l'espace n'existe pas : 404, avec le même message que
l'équipe existe ou non (contrat §1.3). Seul l'administrateur qui tente
d'écrire reçoit un 403 : il voit l'espace, c'est l'action qui lui est interdite.
"""

import logging

from sqlalchemy.orm import Session

from ..dtos.message_dto import message_vers_dto
from ..models import Equipe, Message, Utilisateur
from ..repository import composer_repository, equipe_repository, message_repository, utilisateur_repository
from ..sockets import diffusion
from ..utils import database
from ..utils.metriques import metriques
from ..utils.erreurs import ApiError, Forbidden, NotFound
from . import auth_service

logger = logging.getLogger(__name__)

MESSAGE_INTROUVABLE = "Espace d'échange introuvable."

# Un accès à retirer : (idEquipe, motif, identifiants des utilisateurs concernés).
# Le motif est celui de l'événement equipe:acces-revoque : exclusion, elimination, disqualification.
Revocation = tuple[int, str, list[int]]


def verifier_acces(session: Session, id_equipe: int, utilisateur: Utilisateur, ecriture: bool = False) -> Equipe:
    """LA règle d'accès à l'espace d'échange. Renvoie l'équipe, ou lève NotFound / Forbidden."""
    equipe = equipe_repository.par_id(session, id_equipe)
    if equipe is None:
        _journaliser_refus(id_equipe, utilisateur, ecriture, False)
        raise NotFound(MESSAGE_INTROUVABLE)

    membre = composer_repository.membre(session, id_equipe, utilisateur.id_utilisateur)
    membre_actif = membre is not None and equipe.statut_equipe == "EN_LICE"

    if membre_actif:
        return equipe
    if utilisateur.est_administrateur:
        if ecriture:
            raise Forbidden("Les administrateurs consultent les espaces d'échange, ils n'y écrivent pas.")
        return equipe
    _journaliser_refus(id_equipe, utilisateur, ecriture, membre is not None)
    raise NotFound(MESSAGE_INTROUVABLE)


def _journaliser_refus(id_equipe: int, utilisateur: Utilisateur, ecriture: bool, etait_membre: bool) -> None:
    """Un refus répond 404 : sans cette ligne, il ne laisserait aucune trace de sécurité.

    Les 401 et 403 sont journalisés en WARNING par `utils/requetes.py` ; les 404
    ne le sont pas, car la plupart sont anodins. Ceux-ci ne le sont pas.
    """
    logger.warning(
        "Accès refusé à l'espace d'échange",
        extra={"contexte": {
            "idEquipe": id_equipe,
            "idUtilisateur": utilisateur.id_utilisateur,
            "action": "écriture" if ecriture else "lecture",
            "etaitMembre": etait_membre,
        }},
    )


def lire(id_equipe: int, utilisateur: Utilisateur) -> list[tuple[Message, str | None]]:
    """B-16 : tous les messages de l'équipe, du plus ancien au plus récent."""
    with database.session() as session:
        verifier_acces(session, id_equipe, utilisateur)
        return message_repository.de_l_equipe(session, id_equipe)


def envoyer(id_equipe: int, auteur: Utilisateur, contenu: str) -> tuple[Message, str]:
    """B-16 : enregistre le message, puis le pousse aux membres abonnés."""
    with database.session() as session:
        verifier_acces(session, id_equipe, auteur, ecriture=True)
        message = message_repository.ajouter(session, id_equipe, auteur.id_utilisateur, contenu)

    logger.info(
        "Message envoyé",
        extra={"contexte": {"idMessage": message.id_message, "idEquipe": id_equipe, "idAuteur": auteur.id_utilisateur}},
    )
    metriques.message_envoye()
    diffusion.message_nouveau(id_equipe, message_vers_dto(message, auteur.pseudo).vers_json())
    return message, auteur.pseudo


def autoriser_abonnement(id_equipe: int, id_utilisateur: int, version_jeton: int) -> bool:
    """Le gestionnaire WebSocket demande ici si une connexion peut entrer dans le salon.

    Le compte est relu en base : jeton révoqué (version_jeton changée) ou compte
    supprimé depuis la connexion → refus. Les droits sont ceux d'AUJOURD'HUI.
    """
    utilisateur = auth_service.utilisateur_du_jeton(id_utilisateur, version_jeton)
    if utilisateur is None:
        return False
    with database.session() as session:
        try:
            verifier_acces(session, id_equipe, utilisateur)
        except ApiError:
            logger.warning(
                "Abonnement refusé à un espace d'échange",
                extra={"contexte": {"idEquipe": id_equipe, "idUtilisateur": id_utilisateur}},
            )
            return False
    return True


# --- Fin d'accès (B-17, B-18) -------------------------------------------------------

def revocation_de_l_equipe(session: Session, id_equipe: int, motif: str) -> Revocation:
    """Tous les membres de l'équipe perdent l'accès (élimination, disqualification)."""
    ids = [composer.id_utilisateur for composer, _, _ in composer_repository.membres_de(session, id_equipe)]
    return id_equipe, motif, utilisateur_repository.sans_administrateurs(session, ids)


def revocation_d_un_membre(session: Session, id_equipe: int, id_utilisateur: int, motif: str) -> Revocation:
    """Un seul membre perd l'accès (exclusion ou départ)."""
    return id_equipe, motif, utilisateur_repository.sans_administrateurs(session, [id_utilisateur])


def notifier(revocations: list[Revocation]) -> None:
    """À appeler APRÈS la validation de la transaction qui a retiré les droits."""
    for id_equipe, motif, ids_utilisateurs in revocations:
        if ids_utilisateurs:
            diffusion.acces_revoque(id_equipe, motif, ids_utilisateurs)
