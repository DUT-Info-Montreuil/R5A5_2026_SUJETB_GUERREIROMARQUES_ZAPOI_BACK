"""
Rencontres (contrat §5) : lecture de l'arbre, saisie d'un résultat.

Un seul point d'entrée pour les trois situations — match joué, forfait,
qualification directe — puisque le mécanisme est le même : un vainqueur est
désigné et remonte dans l'arbre (B-13, B-14, B-15).
"""

import logging

from sqlalchemy import func

from ..dtos.rencontre_dto import rencontre_vers_dto
from ..models import Rencontre
from ..repository import equipe_repository, rencontre_repository
from ..sockets import diffusion
from ..utils import database
from ..utils.erreurs import BadRequest, Conflict, NotFound, UnprocessableEntity
from . import arbre as arbre_du_tournoi
from .tournoi_service import arbre_de, tournoi_ou_404

logger = logging.getLogger(__name__)


def arbre(id_tournoi: int) -> tuple[list[Rencontre], dict[int, str]]:
    """Les rencontres du tournoi et le nom de chaque équipe (B-12, B-19).

    Liste vide tant que les inscriptions sont ouvertes : l'arbre naît à la clôture.
    """
    with database.session() as session:
        tournoi_ou_404(session, id_tournoi)
        noms = {equipe.id_equipe: equipe.nom_equipe for equipe, _ in equipe_repository.du_tournoi(session, id_tournoi)}
        return rencontre_repository.du_tournoi(session, id_tournoi), noms


def saisir_resultat(
    id_rencontre: int, id_vainqueur: int, type_resultat: str, score_a: int | None, score_b: int | None,
) -> tuple[Rencontre, dict[int, str]]:
    _verifier_scores(type_resultat, score_a, score_b)

    with database.session() as session:
        id_tournoi = rencontre_repository.id_tournoi_de(session, id_rencontre)
        if id_tournoi is None:
            raise NotFound("Rencontre introuvable.")
        # Verrou sur le tournoi : deux saisies simultanées passent l'une après l'autre.
        tournoi = tournoi_ou_404(session, id_tournoi, verrouiller=True)
        if tournoi.statut_tournoi != "EN_COURS":
            raise Conflict("Le tournoi n'est pas en cours.")

        equipes_par_id = {equipe.id_equipe: equipe for equipe, _ in equipe_repository.du_tournoi(session, id_tournoi)}
        arbre = arbre_de(session, id_tournoi, equipes_par_id)
        rencontre = next(r for r in arbre.rencontres if r.id_rencontre == id_rencontre)
        _verifier_resultat(rencontre, id_vainqueur, type_resultat, score_a, score_b)

        avant = {r.id_rencontre: _etat(r) for r in arbre.rencontres}
        perdant = arbre.enregistrer_resultat(
            rencontre, id_vainqueur, type_resultat, func.now(), score_a, score_b
        )
        if perdant is not None:
            equipes_par_id[perdant].statut_equipe = "ELIMINEE"
        arbre.actualiser_statuts()
        session.flush()

        noms = {id_equipe: equipe.nom_equipe for id_equipe, equipe in equipes_par_id.items()}
        modifiees = [r for r in arbre.rencontres if _etat(r) != avant[r.id_rencontre]]

    logger.info(
        "Résultat saisi",
        extra={"contexte": {"idRencontre": id_rencontre, "idVainqueur": id_vainqueur, "type": type_resultat}},
    )
    for modifiee in modifiees:
        diffusion.rencontre_maj(id_tournoi, rencontre_vers_dto(modifiee, noms).vers_json())
    return rencontre, noms


def _etat(rencontre: Rencontre) -> tuple:
    return (rencontre.statut_rencontre, rencontre.id_equipe_a, rencontre.id_equipe_b, rencontre.id_vainqueur)


def _verifier_scores(type_resultat: str, score_a: int | None, score_b: int | None) -> None:
    """Forme de la charge : 400, avant d'ouvrir la moindre transaction."""
    if (score_a is None) != (score_b is None):
        raise BadRequest("scoreA et scoreB s'envoient ensemble.")
    if score_a is not None and type_resultat != "NORMAL":
        raise BadRequest("Les scores ne s'envoient qu'avec un résultat NORMAL.")


def _verifier_resultat(
    rencontre: Rencontre, id_vainqueur: int, type_resultat: str, score_a: int | None, score_b: int | None,
) -> None:
    if rencontre.statut_rencontre == "TERMINE":
        raise Conflict("Cette rencontre a déjà un vainqueur.")
    if rencontre.statut_rencontre != "JOUABLE":
        raise Conflict("Cette rencontre attend encore ses équipes.")
    if id_vainqueur not in (rencontre.id_equipe_a, rencontre.id_equipe_b):
        raise UnprocessableEntity("Le vainqueur désigné ne participe pas à cette rencontre.")

    a_un_adversaire = arbre_du_tournoi.adversaire(rencontre, id_vainqueur) is not None
    if type_resultat == "QUALIFICATION_DIRECTE" and a_un_adversaire:
        raise UnprocessableEntity("Les deux équipes sont connues : la qualification directe est impossible.")
    if type_resultat != "QUALIFICATION_DIRECTE" and not a_un_adversaire:
        raise UnprocessableEntity("Pas d'adversaire : le résultat est une QUALIFICATION_DIRECTE.")

    if score_a is not None:
        score_vainqueur, score_perdant = (
            (score_a, score_b) if id_vainqueur == rencontre.id_equipe_a else (score_b, score_a)
        )
        if score_vainqueur <= score_perdant:
            raise UnprocessableEntity("Le score du vainqueur doit être supérieur à celui de son adversaire.")
