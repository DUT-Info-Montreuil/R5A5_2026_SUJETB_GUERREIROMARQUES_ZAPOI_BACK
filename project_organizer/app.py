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
from .controllers.demande_controller import demande_bp
from .controllers.equipe_controller import equipe_bp
from .controllers.jeu_controller import jeu_bp
from .controllers.message_controller import message_bp
from .controllers.metriques_controller import metriques_bp
from .controllers.moi_controller import moi_bp
from .controllers.rencontre_controller import rencontre_bp
from .controllers.sante_controller import sante_bp
from .controllers.tournoi_controller import tournoi_bp
from .extensions import limiter, socketio, spec
from .utils import authentification, cache_http, database, entetes_securite, erreurs, journalisation, origine, proxy, requetes

logger = logging.getLogger(__name__)

TAILLE_MAX_CORPS_OCTETS = 1024 * 1024


def create_app(config: type[Config] = Config) -> Flask:
    """Fabrique de l'application : journalisation, base, CORS, temps réel, authentification, limiteur, en-têtes puis routes. L'ordre d'installation compte (voir les commentaires).
    """
    journalisation.configurer(config.LOG_LEVEL)

    app = Flask(__name__)
    app.config.from_object(config)
    # Au-delà, 413 : un envoi de plusieurs gigaoctets ne sature pas la mémoire.
    app.config["MAX_CONTENT_LENGTH"] = TAILLE_MAX_CORPS_OCTETS

    database.initialiser(config.DATABASE_URL)

    # CORS : liste d'origines explicite, jamais « * » sur une API authentifiée.
    # supports_credentials : le navigateur joint le cookie de session aux appels du front.
    CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS}}, supports_credentials=True)
    socketio.init_app(
        app,
        cors_allowed_origins=config.CORS_ORIGINS,
        ping_interval=config.SOCKET_PING_INTERVALLE_SECONDES,
        ping_timeout=config.SOCKET_PING_DELAI_SECONDES,
        max_http_buffer_size=config.SOCKET_TAILLE_MAX_OCTETS,
    )

    # Enregistre les gestionnaires d'événements temps réel.
    from . import sockets  # noqa: F401

    # L'ordre compte : la journalisation d'abord, pour que les requêtes refusées
    # par l'authentification soient journalisées elles aussi.
    proxy.installer(app, config.PROXIES_DE_CONFIANCE)
    requetes.installer(app)
    # Avant l'authentification : une écriture d'une origine étrangère est refusée, session ou pas.
    origine.installer(app, config.CORS_ORIGINS)
    authentification.configurer(app, config)
    limiter.init_app(app)
    entetes_securite.installer(app)
    cache_http.installer(app)
    erreurs.enregistrer_gestionnaires(app)

    # --- Routes : un Blueprint par ressource ---------------------------------
    app.register_blueprint(sante_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tournoi_bp)
    app.register_blueprint(equipe_bp)
    app.register_blueprint(demande_bp)
    app.register_blueprint(message_bp)
    app.register_blueprint(moi_bp)
    app.register_blueprint(metriques_bp)
    app.register_blueprint(rencontre_bp)
    app.register_blueprint(jeu_bp)

    # Après les Blueprints : la documentation décrit les routes enregistrées.
    spec.register(app)

    logger.info("Application démarrée", extra={"contexte": {"originesCors": config.CORS_ORIGINS}})
    return app
