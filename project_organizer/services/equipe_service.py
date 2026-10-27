"""
Équipes et composition (contrat §4) : création, renommage, disqualification,
attribution des postes, passation du capitanat, exclusion et départ.

Les droits se décident ici et nulle part ailleurs (cours, « Où placer la
vérification ») : le contrôleur sait seulement si l'appelant est connecté, ce
service sait s'il est capitaine de CETTE équipe.

Toute écriture commence par verrouiller la ligne du tournoi : deux
modifications simultanées de la composition (ou une modification et la clôture
des inscriptions) passent l'une après l'autre, ce qui rend B-03 et B-11
fiables même sous charge.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dtos.rencontre_dto import rencontre_vers_dto
from ..models import Composer, Equipe, Rencontre, Tournoi, Utilisateur
from ..repository import composer_repository, equipe_repository, role_repository, tournoi_repository
from ..sockets import diffusion
from ..utils import database
from ..utils.erreurs import BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity
from . import arbre as arbre_du_tournoi
from . import espace_service
from .tournoi_service import arbre_de, tournoi_ou_404

logger = logging.getLogger(__name__)

# Champs de PATCH /api/equipes/{id}, par rôle (contrat §1.4). Tout champ envoyé
# en dehors de la liste de l'appelant fait échouer la requête entière.
CHAMPS_CAPITAINE = {"nom_equipe"}
CHAMPS_ADMINISTRATEUR = {"statut_equipe", "motif_sortie"}
_NOMS_JSON = {"nom_equipe": "nomEquipe", "statut_equipe": "statutEquipe", "motif_sortie": "motifSortie"}

MembresEquipe = list[tuple[Composer, str, str | None]]


# --- Lecture -----------------------------------------------------------------

def detail(id_equipe: int) -> tuple[Equipe, MembresEquipe]:
    """B-02 : une équipe est publique, avec la liste de ses membres."""
    with database.session() as session:
        equipe = equipe_ou_404(session, id_equipe)
        return equipe, composer_repository.membres_de(session, id_equipe)


def de_l_utilisateur(utilisateur: Utilisateur) -> list[tuple[Equipe, bool, Tournoi]]:
    """Les équipes du joueur connecté, avec son rôle de capitaine et leur tournoi."""
    with database.session() as session:
        return equipe_repository.de_l_utilisateur(session, utilisateur.id_utilisateur)


# --- Création ----------------------------------------------------------------

def creer(id_tournoi: int, createur: Utilisateur, nom_equipe: str, id_role: int) -> tuple[Equipe, MembresEquipe]:
    """B-05 : le créateur devient capitaine et premier membre, dans la même transaction."""
    with database.session() as session:
        tournoi = tournoi_ou_404(session, id_tournoi, verrouiller=True)
        exiger_inscriptions_ouvertes(tournoi)
        if composer_repository.equipe_du_joueur(session, id_tournoi, createur.id_utilisateur) is not None:
            raise UnprocessableEntity("Vous avez déjà une équipe dans ce tournoi.")
        verifier_poste_du_jeu(session, tournoi, id_role)
        if equipe_repository.nom_pris(session, id_tournoi, nom_equipe):
            raise Conflict("Ce nom d'équipe est déjà pris dans ce tournoi.")
        if tournoi_repository.nombre_equipes_inscrites(session, id_tournoi) >= tournoi.nombre_equipes:
            raise Conflict("Le tournoi est complet.")

        equipe = equipe_repository.ajouter(session, id_tournoi, nom_equipe)
        composer_repository.ajouter(
            session, equipe.id_equipe, id_tournoi, createur.id_utilisateur, id_role, est_capitaine=True
        )
        membres = composer_repository.membres_de(session, equipe.id_equipe)

    logger.info(
        "Équipe créée",
        extra={"contexte": {"idEquipe": equipe.id_equipe, "idTournoi": id_tournoi, "idCapitaine": createur.id_utilisateur}},
    )
    return equipe, membres


# --- Modification de l'équipe --------------------------------------------------

def modifier(id_equipe: int, appelant: Utilisateur, champs: dict) -> tuple[Equipe, MembresEquipe]:
    """PATCH /api/equipes/{id} : renommage (capitaine) ou disqualification (administrateur).

    `champs` ne contient que les champs réellement envoyés par le client.
    """
    if not champs:
        raise BadRequest("Aucun champ à modifier.")

    rencontres_modifiees: list[Rencontre] = []
    noms: dict[int, str] = {}
    revocations: list[espace_service.Revocation] = []
    with database.session() as session:
        equipe = equipe_ou_404(session, id_equipe)
        tournoi = tournoi_ou_404(session, equipe.id_tournoi, verrouiller=True)

        capitaine = est_capitaine(session, id_equipe, appelant.id_utilisateur)
        if not (capitaine or appelant.est_administrateur):
            raise Forbidden("Seul le capitaine peut modifier son équipe.")

        autorises: set[str] = set()
        if capitaine:
            autorises |= CHAMPS_CAPITAINE
        if appelant.est_administrateur:
            autorises |= CHAMPS_ADMINISTRATEUR
        interdits = sorted(_NOMS_JSON[champ] for champ in set(champs) - autorises)
        if interdits:
            raise BadRequest(f"Champ non modifiable par vous : {', '.join(interdits)}.")

        if "nom_equipe" in champs:
            if equipe_repository.nom_pris(session, equipe.id_tournoi, champs["nom_equipe"], sauf_equipe=id_equipe):
                raise Conflict("Ce nom d'équipe est déjà pris dans ce tournoi.")
            equipe.nom_equipe = champs["nom_equipe"]

        if "statut_equipe" in champs:
            rencontres_modifiees, noms = _disqualifier(session, tournoi, equipe, champs.get("motif_sortie"))
            # B-18 : l'espace d'échange d'une équipe disqualifiée se ferme pour ses membres.
            revocations.append(espace_service.revocation_de_l_equipe(session, id_equipe, "disqualification"))
        elif "motif_sortie" in champs:
            raise BadRequest("motifSortie s'envoie avec statutEquipe.")

        session.flush()
        membres = composer_repository.membres_de(session, id_equipe)

    for rencontre in rencontres_modifiees:
        diffusion.rencontre_maj(equipe.id_tournoi, rencontre_vers_dto(rencontre, noms).vers_json())
    espace_service.notifier(revocations)
    return equipe, membres


def _disqualifier(
    session: Session, tournoi: Tournoi, equipe: Equipe, motif: str | None
) -> tuple[list[Rencontre], dict[int, str]]:
    """B-15 : l'équipe sort ; sa rencontre en cours ou à venir est perdue par forfait.

    Si l'adversaire est déjà connu, il est qualifié tout de suite. Sinon, le
    côté de l'équipe devient un emplacement mort : quand l'adversaire arrivera,
    la rencontre sera jouable et l'administrateur la résoudra par un forfait.
    """
    if tournoi.statut_tournoi != "EN_COURS":
        raise Conflict("Le tournoi n'est pas en cours.")
    if equipe.statut_equipe != "EN_LICE":
        raise Conflict("Cette équipe n'est plus en lice.")

    equipe.statut_equipe = "DISQUALIFIEE"
    equipe.motif_sortie = motif

    equipes_par_id = {e.id_equipe: e for e, _ in equipe_repository.du_tournoi(session, tournoi.id_tournoi)}
    arbre = arbre_de(session, tournoi.id_tournoi, equipes_par_id)
    avant = {r.id_rencontre: _etat(r) for r in arbre.rencontres}

    en_cours = next(
        (r for r in arbre.rencontres
         if r.statut_rencontre != "TERMINE" and equipe.id_equipe in (r.id_equipe_a, r.id_equipe_b)),
        None,
    )
    if en_cours is not None:
        adversaire = arbre_du_tournoi.adversaire(en_cours, equipe.id_equipe)
        if arbre.est_en_lice(adversaire):
            arbre.enregistrer_resultat(en_cours, adversaire, "FORFAIT", func.now())
    arbre.actualiser_statuts()
    session.flush()

    logger.info(
        "Équipe disqualifiée",
        extra={"contexte": {"idEquipe": equipe.id_equipe, "idTournoi": tournoi.id_tournoi}},
    )
    noms = {id_equipe: e.nom_equipe for id_equipe, e in equipes_par_id.items()}
    return [r for r in arbre.rencontres if _etat(r) != avant[r.id_rencontre]], noms


# --- Composition : postes, capitanat, départs ------------------------------------

def modifier_membre(
    id_equipe: int, id_membre: int, appelant: Utilisateur, champs: dict
) -> tuple[Equipe, MembresEquipe]:
    """PATCH …/membres/{id} : attribue un poste (B-08) ou passe la main (B-09). Capitaine seul."""
    if not champs:
        raise BadRequest("Aucun champ à modifier.")

    with database.session() as session:
        equipe = equipe_ou_404(session, id_equipe)
        tournoi = tournoi_ou_404(session, equipe.id_tournoi, verrouiller=True)
        _exiger_capitaine(session, id_equipe, appelant)
        exiger_inscriptions_ouvertes(tournoi)

        membre = composer_repository.membre(session, id_equipe, id_membre)
        if membre is None:
            raise NotFound("Ce joueur n'est pas membre de cette équipe.")

        if "id_role" in champs:
            id_role = champs["id_role"]
            verifier_poste_du_jeu(session, tournoi, id_role)
            if composer_repository.poste_occupe(session, id_equipe, id_role, sauf_utilisateur=id_membre):
                raise UnprocessableEntity("Ce poste est déjà tenu par un autre membre de l'équipe.")
            membre.id_role = id_role

        if champs.get("est_capitaine"):
            if membre.est_capitaine:
                raise UnprocessableEntity("Ce joueur est déjà capitaine.")
            ancien = composer_repository.capitaine_de(session, id_equipe)
            if ancien is not None:
                ancien.est_capitaine = False
                # flush avant la promotion : l'index unique partiel interdit deux capitaines, même un instant.
                session.flush()
            membre.est_capitaine = True
            logger.info(
                "Capitanat transmis",
                extra={"contexte": {"idEquipe": id_equipe, "idNouveauCapitaine": id_membre}},
            )

        session.flush()
        membres = composer_repository.membres_de(session, id_equipe)
    return equipe, membres


def retirer_membre(id_equipe: int, id_membre: int, appelant: Utilisateur) -> None:
    """DELETE …/membres/{id} : le capitaine exclut (B-09) ou le joueur part de lui-même (B-06)."""
    with database.session() as session:
        equipe = equipe_ou_404(session, id_equipe)
        tournoi = tournoi_ou_404(session, equipe.id_tournoi, verrouiller=True)

        capitaine = est_capitaine(session, id_equipe, appelant.id_utilisateur)
        part_de_lui_meme = appelant.id_utilisateur == id_membre
        if not (capitaine or part_de_lui_meme):
            raise Forbidden("Seul le capitaine peut exclure un membre.")
        exiger_inscriptions_ouvertes(tournoi)

        membre = composer_repository.membre(session, id_equipe, id_membre)
        if membre is None:
            raise NotFound("Ce joueur n'est pas membre de cette équipe.")
        if membre.est_capitaine:
            raise UnprocessableEntity("Le capitaine doit passer la main avant de quitter l'équipe.")
        revocation = espace_service.revocation_d_un_membre(session, id_equipe, id_membre, "exclusion")
        composer_repository.supprimer(session, membre)

    logger.info(
        "Joueur exclu" if not part_de_lui_meme else "Joueur parti",
        extra={"contexte": {"idEquipe": id_equipe, "idJoueur": id_membre, "idAppelant": appelant.id_utilisateur}},
    )
    # B-17 : sans cet événement, un socket déjà ouvert continuerait de recevoir les messages.
    espace_service.notifier([revocation])


# --- Règles partagées (utilisées aussi par demande_service) ---------------------

def equipe_ou_404(session: Session, id_equipe: int) -> Equipe:
    """L'équipe d'identifiant donné ; 404 si elle n'existe pas."""
    equipe = equipe_repository.par_id(session, id_equipe)
    if equipe is None:
        raise NotFound("Équipe introuvable.")
    return equipe


def exiger_inscriptions_ouvertes(tournoi: Tournoi) -> None:
    """B-03, B-11 : après la clôture, la composition des équipes ne bouge plus."""
    if tournoi.statut_tournoi != "INSCRIPTIONS_OUVERTES":
        raise Conflict("Les inscriptions sont closes : la composition des équipes ne peut plus changer.")


def verifier_poste_du_jeu(session: Session, tournoi: Tournoi, id_role: int) -> None:
    """Rien n'empêche en base d'assigner un poste de League of Legends dans un tournoi Overwatch."""
    role = role_repository.par_id(session, id_role)
    if role is None or role.id_jeu != tournoi.id_jeu:
        raise UnprocessableEntity("Ce poste n'existe pas pour le jeu de ce tournoi.")


def est_capitaine(session: Session, id_equipe: int, id_utilisateur: int) -> bool:
    """Vrai si ce joueur est le capitaine de cette équipe."""
    membre = composer_repository.membre(session, id_equipe, id_utilisateur)
    return membre is not None and membre.est_capitaine


def _exiger_capitaine(session: Session, id_equipe: int, appelant: Utilisateur) -> None:
    """Capitaine de CETTE équipe : un administrateur n'y touche pas non plus (B-10)."""
    if not est_capitaine(session, id_equipe, appelant.id_utilisateur):
        raise Forbidden("Seul le capitaine peut gérer la composition de son équipe.")


def _etat(rencontre: Rencontre) -> tuple:
    return (rencontre.statut_rencontre, rencontre.id_equipe_a, rencontre.id_equipe_b, rencontre.id_vainqueur)
