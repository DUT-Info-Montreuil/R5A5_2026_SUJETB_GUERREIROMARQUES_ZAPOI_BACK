"""
Canal temps réel (Flask-SocketIO).

Les gestionnaires d'événements vivent ici. Comme un contrôleur, un gestionnaire
ne porte aucune règle métier : il appelle un service, qui décide.

Salons prévus (contrat §7) :
    tournoi:{idTournoi}   ouvert à tous (B-19)
    equipe:{idEquipe}     membres de l'équipe uniquement (B-16, B-18)

Gérés pour l'instant : la connexion et la déconnexion (le front vérifie que le
canal fonctionne), et l'abonnement au salon d'un tournoi.
"""

import logging

from flask import request
from flask_socketio import emit, join_room, leave_room

from ..extensions import socketio
from .diffusion import salon_tournoi

logger = logging.getLogger(__name__)


@socketio.on("connect")
def connexion():
    logger.info("Client temps réel connecté", extra={"contexte": {"idSocket": request.sid}})
    emit("bienvenue", {"message": "Canal temps réel opérationnel"})


@socketio.on("disconnect")
def deconnexion(*_):
    logger.info("Client temps réel déconnecté", extra={"contexte": {"idSocket": request.sid}})


def _id_tournoi(donnees) -> int | None:
    valeur = donnees.get("idTournoi") if isinstance(donnees, dict) else None
    # bool est un int en Python : True ne doit pas désigner le tournoi 1.
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0 else None


@socketio.on("tournoi:suivre")
def suivre_tournoi(donnees):
    """Abonnement au salon d'un tournoi. Ouvert à tous, même sans compte (B-19) :
    l'arbre et les résultats sont publics."""
    id_tournoi = _id_tournoi(donnees)
    if id_tournoi is None:
        return {"ok": False}
    join_room(salon_tournoi(id_tournoi))
    return {"ok": True}


@socketio.on("tournoi:quitter")
def quitter_tournoi(donnees):
    id_tournoi = _id_tournoi(donnees)
    if id_tournoi is not None:
        leave_room(salon_tournoi(id_tournoi))
    return {"ok": id_tournoi is not None}
