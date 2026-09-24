"""
Fabrique de l'application.

On utilise une fabrique (`create_app`) plutôt qu'une instance globale : les
tests créent leur propre application, configurée à part, sans dupliquer le
montage.
"""

import logging

from flask import Flask
from flask_cors import CORS

from .config import Config
from .controllers.sante_controller import sante_bp
from .extensions import socketio
from .utils import database, erreurs, journalisation, requetes

logger = logging.getLogger(__name__)

LONGUEUR_MIN_CLE_SECRETE = 32


def create_app(config: type[Config] = Config) -> Flask:
    journalisation.configurer(config.LOG_LEVEL)

    app = Flask(__name__)
    app.config.from_object(config)

    if len(config.SECRET_KEY) < LONGUEUR_MIN_CLE_SECRETE:
        logger.warning(
            "FLASK_SECRET_KEY trop courte (32 caractères minimum) — voir .env.example",
            extra={"contexte": {"longueur": len(config.SECRET_KEY)}},
        )

    database.initialiser(config.DATABASE_URL)

    # CORS : liste d'origines explicite, jamais « * » sur une API authentifiée.
    CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS}})
    socketio.init_app(app, cors_allowed_origins=config.CORS_ORIGINS)

    # Enregistre les gestionnaires d'événements temps réel.
    from . import sockets  # noqa: F401

    requetes.installer(app)
    erreurs.enregistrer_gestionnaires(app)

    # --- Routes : un Blueprint par ressource ---------------------------------
    app.register_blueprint(sante_bp)

    logger.info("Application démarrée", extra={"contexte": {"originesCors": config.CORS_ORIGINS}})
    return app
