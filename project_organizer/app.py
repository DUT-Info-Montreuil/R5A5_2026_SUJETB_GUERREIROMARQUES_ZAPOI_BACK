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
from .controllers.auth_controller import auth_bp
from .controllers.sante_controller import sante_bp
from .controllers.tournoi_controller import tournoi_bp
from .extensions import limiter, socketio, spec
from .utils import authentification, database, entetes_securite, erreurs, journalisation, requetes

logger = logging.getLogger(__name__)

LONGUEUR_MIN_CLE_SECRETE = 32
TAILLE_MAX_CORPS_OCTETS = 1024 * 1024


def create_app(config: type[Config] = Config) -> Flask:
    journalisation.configurer(config.LOG_LEVEL)

    app = Flask(__name__)
    app.config.from_object(config)
    # Au-delà, 413 : un envoi de plusieurs gigaoctets ne sature pas la mémoire.
    app.config["MAX_CONTENT_LENGTH"] = TAILLE_MAX_CORPS_OCTETS

    if len(config.SECRET_KEY) < LONGUEUR_MIN_CLE_SECRETE:
        logger.warning(
            "FLASK_SECRET_KEY trop courte (32 caractères minimum) — voir .env.example",
            extra={"contexte": {"longueur": len(config.SECRET_KEY)}},
        )

    database.initialiser(config.DATABASE_URL)

    # CORS : liste d'origines explicite, jamais « * » sur une API authentifiée.
    # supports_credentials : le navigateur joint le cookie de session aux appels du front.
    CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS}}, supports_credentials=True)
    socketio.init_app(app, cors_allowed_origins=config.CORS_ORIGINS)

    # Enregistre les gestionnaires d'événements temps réel.
    from . import sockets  # noqa: F401

    # L'ordre compte : la journalisation d'abord, pour que les requêtes refusées
    # par l'authentification soient journalisées elles aussi.
    requetes.installer(app)
    authentification.configurer(app, config)
    limiter.init_app(app)
    entetes_securite.installer(app)
    erreurs.enregistrer_gestionnaires(app)

    # --- Routes : un Blueprint par ressource ---------------------------------
    app.register_blueprint(sante_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tournoi_bp)

    # Après les Blueprints : la documentation décrit les routes enregistrées.
    spec.register(app)

    logger.info("Application démarrée", extra={"contexte": {"originesCors": config.CORS_ORIGINS}})
    return app
