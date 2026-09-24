"""
Configuration commune des tests.

Les variables d'environnement sont posées AVANT d'importer l'application :
config.py les lit au chargement. Les tests utilisent la base décrite par
DATABASE_URL — celle du docker-compose par défaut, qui doit être démarrée.
"""

import os

import pytest
from flask import Blueprint

os.environ.setdefault("DATABASE_URL", "postgresql+pg8000://r5a5:r5a5@localhost:5432/tournois")
os.environ.setdefault("FLASK_SECRET_KEY", "cle-de-test-suffisamment-longue-pour-hs256-0123456789")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("LOG_FORMAT", "texte")

from project_organizer.app import create_app  # noqa: E402
from project_organizer.utils.erreurs import Conflict  # noqa: E402


def _routes_de_test() -> Blueprint:
    """Routes qui n'existent que pendant les tests, pour vérifier la plomberie."""
    bp = Blueprint("tests", __name__, url_prefix="/_tests")

    @bp.get("/erreur-metier")
    def erreur_metier():
        raise Conflict("Les inscriptions sont closes.")

    @bp.get("/erreur-inattendue")
    def erreur_inattendue():
        raise RuntimeError("détail interne qui ne doit jamais sortir")

    return bp


@pytest.fixture(scope="session")
def app():
    application = create_app()
    application.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    application.register_blueprint(_routes_de_test())
    return application


@pytest.fixture
def client(app):
    return app.test_client()
