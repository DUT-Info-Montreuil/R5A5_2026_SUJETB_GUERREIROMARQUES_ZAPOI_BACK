"""
Configuration commune des tests.

Les variables d'environnement sont posées AVANT d'importer l'application :
config.py les lit au chargement. Les tests utilisent la base décrite par
DATABASE_URL — celle du docker-compose par défaut, qui doit être démarrée.
"""

import os

import pytest
from sqlalchemy import text
from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

os.environ.setdefault("DATABASE_URL", "postgresql+pg8000://r5a5:r5a5@localhost:5432/tournois")
os.environ.setdefault("FLASK_SECRET_KEY", "cle-de-test-suffisamment-longue-pour-hs256-0123456789")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("LOG_FORMAT", "texte")

from project_organizer.app import create_app  # noqa: E402
from project_organizer.dtos.base import ModeleEntree  # noqa: E402
from project_organizer.extensions import limiter, spec  # noqa: E402
from project_organizer.utils import database  # noqa: E402
from project_organizer.utils.authentification import administrateur_requis, publique  # noqa: E402
from project_organizer.utils.erreurs import Conflict  # noqa: E402

PREFIXE_PSEUDO_TEST = "test_"
MOT_DE_PASSE_TEST = "une phrase de passe assez longue"


class CorpsDeTest(ModeleEntree):
    pseudo: str
    mot_de_passe: str


def _routes_de_test() -> Blueprint:
    """Routes qui n'existent que pendant les tests, pour vérifier la plomberie."""
    bp = Blueprint("tests", __name__, url_prefix="/_tests")

    @bp.get("/erreur-metier")
    @publique
    def erreur_metier():
        raise Conflict("Les inscriptions sont closes.")

    @bp.post("/validation")
    @publique
    @spec.validate(body=CorpsDeTest, resp=Response(HTTP_204=None))
    def validation():
        return "", 204

    @bp.get("/reponse-non-conforme")
    @publique
    @spec.validate(resp=Response(HTTP_200=CorpsDeTest))
    def reponse_non_conforme():
        return jsonify({"pseudo": "sans mot de passe"}), 200

    @bp.get("/erreur-inattendue")
    @publique
    def erreur_inattendue():
        raise RuntimeError("détail interne qui ne doit jamais sortir")

    @bp.get("/reservee-admin")
    @administrateur_requis
    def reservee_admin():
        return "", 204

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


@pytest.fixture(autouse=True)
def compteurs_de_debit_remis_a_zero():
    """Chaque test repart avec ses 5 tentatives de connexion."""
    limiter.reset()


@pytest.fixture
def nettoyer_comptes_de_test():
    yield
    with database.session() as session:
        session.execute(
            text("DELETE FROM utilisateur WHERE pseudo LIKE :prefixe"),
            {"prefixe": PREFIXE_PSEUDO_TEST + "%"},
        )


@pytest.fixture
def inscrire(client, nettoyer_comptes_de_test):
    """Crée un compte de test ; le client garde le cookie de session."""

    def _inscrire(suffixe: str = "alice"):
        pseudo = PREFIXE_PSEUDO_TEST + suffixe
        reponse = client.post(
            "/api/auth/inscription",
            json={"pseudo": pseudo, "email": f"{pseudo}@iut.fr", "motDePasse": MOT_DE_PASSE_TEST},
        )
        assert reponse.status_code == 201, reponse.get_json()
        return reponse

    return _inscrire
