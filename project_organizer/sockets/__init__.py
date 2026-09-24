"""
Canal temps réel (Flask-SocketIO).

Les gestionnaires d'événements vivent ici. Comme un contrôleur, un gestionnaire
ne porte aucune règle métier : il appelle un service, qui décide.

Salons prévus (contrat §7) :
    tournoi:{idTournoi}   ouvert à tous (B-19)
    equipe:{idEquipe}     membres de l'équipe uniquement (B-16, B-18)

Pour l'instant, seuls la connexion et la déconnexion sont gérées : c'est ce qui
permet au front de vérifier que le canal fonctionne.
"""

import logging

from flask import request
from flask_socketio import emit

from ..extensions import socketio

logger = logging.getLogger(__name__)


@socketio.on("connect")
def connexion():
    logger.info("Client temps réel connecté", extra={"contexte": {"idSocket": request.sid}})
    emit("bienvenue", {"message": "Canal temps réel opérationnel"})


@socketio.on("disconnect")
def deconnexion(*_):
    logger.info("Client temps réel déconnecté", extra={"contexte": {"idSocket": request.sid}})
