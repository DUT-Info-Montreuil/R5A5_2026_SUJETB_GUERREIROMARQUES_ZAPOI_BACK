"""
Canal temps réel (Flask-SocketIO).

Les gestionnaires d'événements vivent ici. Comme un contrôleur, un gestionnaire
ne porte aucune règle métier : il appelle un service, qui décide.

Salons (contrat §7) :
    tournoi:{idTournoi}   ouvert à tous (B-19)
    equipe:{idEquipe}     membres de l'équipe, et administrateurs (B-16, B-18)

Authentification : le navigateur joint le cookie `jeton` à la connexion. Un
visiteur sans cookie valide se connecte quand même (le salon d'un tournoi est
public), mais n'entrera dans aucun salon d'équipe. L'identité est lue du
cookie, jamais d'un message du client. Elle est revérifiée à CHAQUE
abonnement : le jeton a pu être révoqué et les droits ont pu changer depuis la
connexion (cours, « Un contrôle à l'ouverture seulement »).

Le cours propose trois réponses à une connexion qui reste ouverte des heures :
    1. revérifier les droits à chaque action sensible  → chaque abonnement
    2. fermer la connexion quand les droits changent   → diffusion.acces_revoque
    3. fermer la connexion à l'expiration du jeton     → fermer_les_connexions_expirees
    4. fermer la connexion quand le jeton est révoqué  → fermer_les_connexions_revoquees

Les écritures (envoyer un message) restent en HTTP : validation, codes de
statut et journalisation sont ceux des autres routes. Le socket ne fait que
notifier. Il n'accepte que des identifiants, donc de très petits messages :
taille et nombre d'événements par connexion sont plafonnés (cours, « Valider
les messages entrants »).
"""

import logging
import threading
import time
from collections import deque
from functools import wraps

from flask import request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_socketio import disconnect, emit, join_room, leave_room

from ..config import Config
from ..extensions import socketio
from ..services import auth_service, espace_service
from ..utils.metriques import metriques
from .diffusion import salon_equipe, salon_tournoi, salon_utilisateur

logger = logging.getLogger(__name__)

# Identité des connexions authentifiées : idSocket → { id, ver, exp }.
# En mémoire : suffisant pour un seul processus, comme le limiteur de débit.
_CONNEXIONS: dict[str, dict] = {}
# Instants des derniers événements reçus de chaque connexion, pour le plafond de débit.
_EVENEMENTS_RECENTS: dict[str, deque[float]] = {}
# Connexions déjà coupées pour débit : leurs derniers événements en file ne sont pas recomptés.
_COUPEES_POUR_DEBIT: set[str] = set()

_verrou_surveillance = threading.Lock()
_surveillance_demarree = False


def _identifier_le_client() -> dict | None:
    """L'identité portée par le cookie de la connexion, ou None pour un visiteur.

    Un cookie absent, expiré, falsifié ou révoqué ne refuse pas la connexion :
    il en fait celle d'un visiteur.
    """
    try:
        verify_jwt_in_request(optional=True)
        charge = get_jwt()
    except Exception:  # noqa: BLE001 — toute anomalie du jeton = visiteur
        return None
    if not charge:
        return None
    return {"id": int(charge["sub"]), "ver": charge.get("ver", 0), "exp": charge["exp"]}


@socketio.on("connect")
def connexion():
    """À l'ouverture : identifie le client d'après son cookie (visiteur sinon), le place dans son salon personnel et l'accueille.
    """
    identite = _identifier_le_client()
    if identite is not None:
        _CONNEXIONS[request.sid] = identite
        join_room(salon_utilisateur(identite["id"]))
    metriques.ouverture(authentifiee=identite is not None)
    _demarrer_la_surveillance()
    logger.info(
        "Client temps réel connecté",
        extra={"contexte": {"idSocket": request.sid, "authentifie": identite is not None}},
    )
    emit("bienvenue", {"message": "Canal temps réel opérationnel"})


@socketio.on("disconnect")
def deconnexion(*_):
    """À la fermeture : oublie l'identité et les compteurs de cette connexion."""
    identite = _CONNEXIONS.pop(request.sid, None)
    _EVENEMENTS_RECENTS.pop(request.sid, None)
    _COUPEES_POUR_DEBIT.discard(request.sid)
    metriques.fermeture(authentifiee=identite is not None)
    logger.info("Client temps réel déconnecté", extra={"contexte": {"idSocket": request.sid}})


# --- Plafond d'événements par connexion -------------------------------------------------

def _trop_d_evenements(sid: str) -> bool:
    """Compte l'événement qui vient d'arriver ; vrai si la connexion dépasse son plafond."""
    maintenant = time.monotonic()
    recents = _EVENEMENTS_RECENTS.setdefault(sid, deque())
    while recents and recents[0] < maintenant - Config.SOCKET_FENETRE_DEBIT_SECONDES:
        recents.popleft()
    recents.append(maintenant)
    return len(recents) > Config.SOCKET_EVENEMENTS_MAX


def limite_de_debit(gestionnaire):
    """Coupe la connexion d'un client qui envoie trop d'événements (cours : « doit être coupé »)."""

    @wraps(gestionnaire)
    def enveloppe(*args, **kwargs):
        if request.sid in _COUPEES_POUR_DEBIT:
            return {"ok": False}
        if _trop_d_evenements(request.sid):
            _COUPEES_POUR_DEBIT.add(request.sid)
            metriques.coupure("debit")
            logger.warning(
                "Débit excessif : connexion temps réel coupée",
                extra={"contexte": {"idSocket": request.sid, "plafond": Config.SOCKET_EVENEMENTS_MAX}},
            )
            disconnect()
            return {"ok": False}
        return gestionnaire(*args, **kwargs)

    return enveloppe


# --- Fermeture des connexions dont le jeton a expiré -------------------------------------

def fermer_les_connexions_expirees(maintenant: float | None = None) -> int:
    """Coupe les connexions authentifiées dont le jeton a expiré ; renvoie leur nombre.

    Sans cela, une connexion ouverte avant l'expiration du jeton resterait
    authentifiée indéfiniment. Le client se reconnecte alors en visiteur : à sa
    prochaine lecture, l'API répond 401 et le front le renvoie à la connexion.
    """
    maintenant = time.time() if maintenant is None else maintenant
    expirees = [sid for sid, identite in list(_CONNEXIONS.items()) if maintenant >= identite["exp"]]
    for sid in expirees:
        metriques.coupure("expiration")
        logger.info("Connexion temps réel coupée : jeton expiré", extra={"contexte": {"idSocket": sid}})
        socketio.server.disconnect(sid, namespace="/")
    return len(expirees)


# --- Fermeture des connexions dont le jeton a été révoqué --------------------------------

def fermer_les_connexions_revoquees() -> int:
    """Coupe les connexions authentifiées dont le jeton a été révoqué (déconnexion) ; renvoie leur nombre.

    HTTP refuse un jeton révoqué dès la requête suivante. Une connexion temps réel déjà ouverte,
    elle, ne refait aucun contrôle toute seule : on relit donc la version de jeton de chaque compte
    connecté (une seule requête pour tous) et on coupe ceux qui sont périmés. Le client se reconnecte
    en visiteur, sans cookie valable.
    """
    couples = {(identite["id"], identite["ver"]) for identite in _CONNEXIONS.values()}
    revoques = auth_service.jetons_revoques(couples)
    if not revoques:
        return 0
    concernees = [sid for sid, identite in list(_CONNEXIONS.items()) if (identite["id"], identite["ver"]) in revoques]
    for sid in concernees:
        metriques.coupure("revocation")
        logger.info("Connexion temps réel coupée : jeton révoqué", extra={"contexte": {"idSocket": sid}})
        socketio.server.disconnect(sid, namespace="/")
    return len(concernees)


def _surveiller() -> None:
    """Boucle de fond : ferme les connexions expirées ou révoquées et journalise les métriques."""
    while True:
        socketio.sleep(Config.SOCKET_VERIFICATION_SECONDES)
        try:
            fermer_les_connexions_expirees()
            fermer_les_connexions_revoquees()
            instantane = metriques.instantane()
            if instantane["connexionsActives"]:
                logger.info("Métriques temps réel", extra={"contexte": instantane})
        except Exception:  # noqa: BLE001 — la surveillance ne doit jamais s'arrêter
            logger.exception("Erreur de la surveillance temps réel")


def _demarrer_la_surveillance() -> None:
    """Lance la boucle de fond une seule fois, à la première connexion."""
    global _surveillance_demarree
    with _verrou_surveillance:
        if _surveillance_demarree:
            return
        _surveillance_demarree = True
    socketio.start_background_task(_surveiller)


# --- Abonnements -----------------------------------------------------------------------------

def _identifiant(donnees, cle: str) -> int | None:
    valeur = donnees.get(cle) if isinstance(donnees, dict) else None
    # bool est un int en Python : True ne doit pas désigner le tournoi 1.
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0 else None


@socketio.on("tournoi:suivre")
@limite_de_debit
def suivre_tournoi(donnees):
    """Abonnement au salon d'un tournoi. Ouvert à tous, même sans compte (B-19) :
    l'arbre et les résultats sont publics."""
    id_tournoi = _identifiant(donnees, "idTournoi")
    if id_tournoi is None:
        return {"ok": False}
    join_room(salon_tournoi(id_tournoi))
    return {"ok": True}


@socketio.on("tournoi:quitter")
@limite_de_debit
def quitter_tournoi(donnees):
    """Désabonnement du salon d'un tournoi."""
    id_tournoi = _identifiant(donnees, "idTournoi")
    if id_tournoi is not None:
        leave_room(salon_tournoi(id_tournoi))
    return {"ok": id_tournoi is not None}


@socketio.on("equipe:suivre")
@limite_de_debit
def suivre_equipe(donnees):
    """Abonnement à l'espace d'échange d'une équipe (B-16).

    La réponse ne dit jamais POURQUOI l'accès est refusé : équipe inexistante,
    non-membre et espace fermé se ressemblent, comme pour les routes HTTP (404).
    """
    id_equipe = _identifiant(donnees, "idEquipe")
    identite = _CONNEXIONS.get(request.sid)
    if (
        id_equipe is None
        or identite is None
        or time.time() >= identite["exp"]
        or not espace_service.autoriser_abonnement(id_equipe, identite["id"], identite["ver"])
    ):
        metriques.abonnement_refuse()
        return {"ok": False}
    join_room(salon_equipe(id_equipe))
    return {"ok": True}


@socketio.on("equipe:quitter")
@limite_de_debit
def quitter_equipe(donnees):
    """Désabonnement de l'espace d'échange d'une équipe."""
    id_equipe = _identifiant(donnees, "idEquipe")
    if id_equipe is not None:
        leave_room(salon_equipe(id_equipe))
    return {"ok": id_equipe is not None}
