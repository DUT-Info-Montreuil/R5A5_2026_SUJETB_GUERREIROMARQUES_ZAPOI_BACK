"""
Règles des tournois (contrat §3) : création, et machine à états.

La machine à états vit ici et nulle part ailleurs : une contrainte SQL ne voit
pas la valeur précédente d'une colonne, elle ne peut donc pas refuser
TERMINE → INSCRIPTIONS_OUVERTES. Chaque transition et ses effets tiennent dans
une seule transaction.
"""

import logging
import random
from collections.abc import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dtos.tournoi_dto import tournoi_complet_vers_dto
from ..models import Equipe, Jeu, Rencontre, Tournoi
from ..repository import composer_repository, equipe_repository, jeu_repository, rencontre_repository, tournoi_repository
from ..sockets import diffusion
from ..utils import database
from ..utils.erreurs import BadRequest, Conflict, NotFound, UnprocessableEntity
from . import arbre as arbre_du_tournoi
from . import espace_service

logger = logging.getLogger(__name__)

NOMBRE_MIN_EQUIPES = 2


def lister(recherche: str | None, statut: str | None) -> list[tuple[Tournoi, int]]:
    """Les tournois, filtrables par nom et par état, chacun avec son nombre d'équipes inscrites."""
    with database.session() as session:
        return tournoi_repository.lister(session, recherche.strip() if recherche else None, statut)


def lister_jeux() -> list[Jeu]:
    """Tous les jeux, pour proposer le choix à la création d'un tournoi."""
    with database.session() as session:
        return jeu_repository.lister(session)


def detail(id_tournoi: int) -> tuple[Tournoi, int]:
    """Un tournoi et son nombre d'équipes inscrites ; 404 s'il n'existe pas."""
    with database.session() as session:
        tournoi = tournoi_ou_404(session, id_tournoi)
        return tournoi, tournoi_repository.nombre_equipes_inscrites(session, id_tournoi)


def equipes(id_tournoi: int) -> list[tuple[Equipe, int]]:
    """Les équipes d'un tournoi avec leur effectif ; 404 si le tournoi n'existe pas."""
    with database.session() as session:
        tournoi_ou_404(session, id_tournoi)
        return equipe_repository.du_tournoi(session, id_tournoi)


def creer(nom_tournoi: str, id_jeu: int, nombre_equipes: int, id_administrateur: int) -> Tournoi:
    """B-01. Le tournoi naît inscriptions ouvertes."""
    with database.session() as session:
        if jeu_repository.par_id(session, id_jeu) is None:
            raise UnprocessableEntity("Ce jeu n'existe pas.")
        tournoi = tournoi_repository.ajouter(session, nom_tournoi, id_jeu, nombre_equipes, id_administrateur)
    logger.info("Tournoi créé", extra={"contexte": {"idTournoi": tournoi.id_tournoi}})
    return tournoi


def modifier(id_tournoi: int, nom_tournoi: str | None, statut_tournoi: str | None) -> tuple[Tournoi, int]:
    """PATCH /api/tournois/{id} : renommage et/ou transition d'état."""
    if nom_tournoi is None and statut_tournoi is None:
        raise BadRequest("Aucun champ à modifier.")

    with database.session() as session:
        tournoi = tournoi_ou_404(session, id_tournoi, verrouiller=True)
        statut_precedent = tournoi.statut_tournoi
        revocations: list[espace_service.Revocation] = []

        if nom_tournoi is not None:
            tournoi.nom_tournoi = nom_tournoi
        if statut_tournoi is not None:
            transition = _TRANSITIONS.get((statut_precedent, statut_tournoi))
            if transition is None:
                raise Conflict(f"Transition impossible : {statut_precedent} → {statut_tournoi}.")
            revocations = transition(session, tournoi) or []
            tournoi.statut_tournoi = statut_tournoi

        session.flush()
        # Les dates posées par now() sont calculées par la base : on les relit.
        session.refresh(tournoi)
        nombre_inscrites = tournoi_repository.nombre_equipes_inscrites(session, id_tournoi)

    if statut_tournoi is not None:
        logger.info(
            "Transition de tournoi",
            extra={"contexte": {"idTournoi": id_tournoi, "de": statut_precedent, "vers": statut_tournoi}},
        )
    diffusion.tournoi_maj(id_tournoi, tournoi_complet_vers_dto(tournoi, nombre_inscrites).vers_json())
    espace_service.notifier(revocations)
    return tournoi, nombre_inscrites


# --- Transitions -------------------------------------------------------------

def _clore_inscriptions(session: Session, tournoi: Tournoi) -> None:
    """INSCRIPTIONS_OUVERTES → INSCRIPTIONS_CLOSES.

    Fige la composition (B-03 : les écritures d'équipe vérifient ce statut) et
    génère l'arbre (B-12), équipes placées par tirage au sort.
    """
    inscrites = [equipe.id_equipe for equipe, _ in equipe_repository.du_tournoi(session, tournoi.id_tournoi)]
    if len(inscrites) < NOMBRE_MIN_EQUIPES:
        raise Conflict("Il faut au moins deux équipes inscrites pour clore les inscriptions.")
    if len(inscrites) > tournoi.nombre_equipes:
        raise Conflict("Plus d'équipes inscrites que de places dans l'arbre.")
    if rencontre_repository.du_tournoi(session, tournoi.id_tournoi):
        raise Conflict("L'arbre de ce tournoi existe déjà.")

    random.shuffle(inscrites)
    ids_crees: dict[tuple[int, int], int] = {}
    rencontres = []
    for place in arbre_du_tournoi.places(tournoi.nombre_equipes, inscrites):
        rencontre = Rencontre(
            id_tournoi=tournoi.id_tournoi,
            tour=place.tour,
            position=place.position,
            id_equipe_a=place.id_equipe_a,
            id_equipe_b=place.id_equipe_b,
            statut_rencontre="EN_ATTENTE",
        )
        if place.tour < arbre_du_tournoi.nombre_de_tours(tournoi.nombre_equipes):
            tour_suivant, position_suivante, emplacement = arbre_du_tournoi.suite_de(place.tour, place.position)
            rencontre.id_rencontre_suivante = ids_crees[(tour_suivant, position_suivante)]
            rencontre.emplacement_suivant = emplacement
        rencontre_repository.ajouter(session, rencontre)
        ids_crees[(place.tour, place.position)] = rencontre.id_rencontre
        rencontres.append(rencontre)

    arbre_du_tournoi.Arbre(rencontres, {id_equipe: "EN_LICE" for id_equipe in inscrites}).actualiser_statuts()
    tournoi.inscriptions_closes_le = _pas_avant(Tournoi.cree_le)


def _pas_avant(etape_precedente):
    """L'heure de la base, sans jamais précéder l'étape d'avant.

    La contrainte ck_tournoi_chronologie exige des dates qui se suivent. Si
    l'horloge de la machine qui héberge la base recule d'un instant (resynchronisation
    d'une machine virtuelle Docker au réveil, par exemple), `now()` seul violerait la
    contrainte et la transition échouerait en 500 : on reste alors à la date précédente.
    """
    return func.greatest(func.now(), etape_precedente)


def _lancer(session: Session, tournoi: Tournoi) -> list[espace_service.Revocation]:
    """INSCRIPTIONS_CLOSES → EN_COURS.

    B-04 : une équipe incomplète est déclarée forfait ; son adversaire du premier
    tour est qualifié d'office.
    B-08 : une équipe est complète quand elle a le nombre de joueurs requis par
    le jeu ET que chacun a un poste. Cinq joueurs dont deux sans poste ne
    forment pas une équipe de cinq « chacun avec un rôle de jeu ».
    Renvoie les accès d'espace d'échange à retirer aux équipes éliminées (B-18).
    """
    joueurs_requis = tournoi.jeu.joueurs_par_equipe
    inscrites = equipe_repository.du_tournoi(session, tournoi.id_tournoi)
    postes = composer_repository.postes_attribues(session, tournoi.id_tournoi)

    def est_complete(equipe: Equipe, membres: int) -> bool:
        return membres >= joueurs_requis and postes.get(equipe.id_equipe, 0) >= joueurs_requis

    completes = [equipe for equipe, membres in inscrites if est_complete(equipe, membres)]
    if len(completes) < NOMBRE_MIN_EQUIPES:
        raise UnprocessableEntity(
            f"Moins de deux équipes sont complètes ({joueurs_requis} joueurs, chacun avec un poste) : "
            "le tournoi ne peut pas commencer."
        )

    equipes_par_id = {equipe.id_equipe: equipe for equipe, _ in inscrites}
    incompletes = {equipe.id_equipe for equipe, membres in inscrites if not est_complete(equipe, membres)}
    for id_equipe in incompletes:
        equipes_par_id[id_equipe].statut_equipe = "ELIMINEE"

    arbre = arbre_de(session, tournoi.id_tournoi, equipes_par_id)
    for rencontre in arbre.rencontres:
        if rencontre.tour != 1 or rencontre.id_equipe_a is None or rencontre.id_equipe_b is None:
            continue
        forfaits = {rencontre.id_equipe_a, rencontre.id_equipe_b} & incompletes
        if len(forfaits) == 1:
            vainqueur = arbre_du_tournoi.adversaire(rencontre, forfaits.pop())
            arbre.enregistrer_resultat(rencontre, vainqueur, "FORFAIT", func.now())
    arbre.actualiser_statuts()

    if incompletes:
        logger.info(
            "Équipes forfait au lancement",
            extra={"contexte": {"idTournoi": tournoi.id_tournoi, "idEquipes": sorted(incompletes)}},
        )
    tournoi.demarre_le = _pas_avant(Tournoi.inscriptions_closes_le)
    return [espace_service.revocation_de_l_equipe(session, id_equipe, "elimination") for id_equipe in sorted(incompletes)]


def _terminer(session: Session, tournoi: Tournoi) -> None:
    """EN_COURS → TERMINE : le vainqueur de la finale devient VAINQUEUR."""
    equipes_par_id = {equipe.id_equipe: equipe for equipe, _ in equipe_repository.du_tournoi(session, tournoi.id_tournoi)}
    finale = arbre_de(session, tournoi.id_tournoi, equipes_par_id).finale()
    if finale is None or finale.statut_rencontre != "TERMINE":
        raise Conflict("La finale n'a pas encore de vainqueur.")
    equipes_par_id[finale.id_vainqueur].statut_equipe = "VAINQUEUR"
    tournoi.termine_le = _pas_avant(Tournoi.demarre_le)


_TRANSITIONS: dict[tuple[str, str], Callable[[Session, Tournoi], list[espace_service.Revocation] | None]] = {
    ("INSCRIPTIONS_OUVERTES", "INSCRIPTIONS_CLOSES"): _clore_inscriptions,
    ("INSCRIPTIONS_CLOSES", "EN_COURS"): _lancer,
    ("EN_COURS", "TERMINE"): _terminer,
}


# --- Outils partagés avec rencontre_service -----------------------------------

def tournoi_ou_404(session: Session, id_tournoi: int, verrouiller: bool = False) -> Tournoi:
    """Le tournoi d'identifiant donné ; 404 s'il n'existe pas. `verrouiller` pose un verrou jusqu'à la fin de la transaction.
    """
    tournoi = tournoi_repository.par_id(session, id_tournoi, verrouiller)
    if tournoi is None:
        raise NotFound("Tournoi introuvable.")
    return tournoi


def arbre_de(session: Session, id_tournoi: int, equipes_par_id: dict[int, Equipe]) -> arbre_du_tournoi.Arbre:
    """L'arbre (logique pure) d'un tournoi, avec le statut courant de chaque équipe."""
    return arbre_du_tournoi.Arbre(
        rencontre_repository.du_tournoi(session, id_tournoi),
        {id_equipe: equipe.statut_equipe for id_equipe, equipe in equipes_par_id.items()},
    )
