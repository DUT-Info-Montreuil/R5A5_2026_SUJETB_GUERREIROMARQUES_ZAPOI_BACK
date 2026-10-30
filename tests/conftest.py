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
from flask_jwt_extended import create_access_token
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
def compteurs_de_debit_remis_a_zero(app):
    """Chaque test repart avec ses 5 tentatives de connexion, et ses 20 places de connexion temps réel.

    Dépend de `app` : le limiteur n'a de stockage qu'une fois attaché à
    l'application, y compris pour un test qui n'en a pas besoin lui-même.
    Les tests ouvrent des clients socket sans les fermer : sans cette remise à zéro,
    le plafond par adresse serait atteint au bout de quelques tests.
    """
    limiter.reset()
    from project_organizer import sockets

    sockets._CONNEXIONS_PAR_ADRESSE.clear()
    sockets._ADRESSE_DE_LA_CONNEXION.clear()


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


# --- Joueurs de test, sans passer par l'inscription ----------------------------
# L'inscription est limitée à 5 par minute et par adresse : un scénario
# d'équipe a besoin de bien plus de comptes. On les crée donc en base et on
# pose directement le cookie de session, comme le ferait la connexion.

@pytest.fixture
def fabrique_clients(app, nettoyer_comptes_de_test):
    """Fabrique : `fabrique_clients("capitaine")` renvoie un client connecté.

    Le client porte `id_utilisateur`. Dépend de `nettoyer_comptes_de_test`
    pour que les comptes soient supprimés après les données qui les
    référencent (tournois, équipes).
    """

    def _fabriquer(suffixe: str, administrateur: bool = False):
        pseudo = PREFIXE_PSEUDO_TEST + suffixe
        with database.session() as session:
            id_utilisateur = session.execute(
                text(
                    "INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash, est_administrateur) "
                    "VALUES (:p, :e, 'x', :a) RETURNING id_utilisateur"
                ),
                {"p": pseudo, "e": f"{pseudo}@iut.fr", "a": administrateur},
            ).scalar_one()
        with app.app_context():
            jeton = create_access_token(identity=str(id_utilisateur), additional_claims={"ver": 1})
        client = app.test_client()
        client.set_cookie("jeton", jeton)
        client.id_utilisateur = id_utilisateur
        return client

    return _fabriquer


@pytest.fixture
def jeu_a_postes(nettoyer_comptes_de_test):
    """Un jeu à 2 joueurs par équipe avec 3 postes, et un second jeu avec un poste.

    Deux joueurs suffisent à rendre une équipe complète : les scénarios
    restent courts. Dépend de `nettoyer_comptes_de_test` : les tournois créés
    sur ces jeux sont supprimés AVANT les comptes qui les ont créés.
    """
    with database.session() as session:
        id_jeu = session.execute(
            text("INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES ('test_Jeu à postes', 2) RETURNING id_jeu")
        ).scalar_one()
        id_autre_jeu = session.execute(
            text("INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES ('test_Autre jeu', 2) RETURNING id_jeu")
        ).scalar_one()
        postes = [
            session.execute(
                text("INSERT INTO role_jeu (id_jeu, libelle_role) VALUES (:j, :l) RETURNING id_role"),
                {"j": id_jeu, "l": f"Poste {numero}"},
            ).scalar_one()
            for numero in (1, 2, 3)
        ]
        poste_etranger = session.execute(
            text("INSERT INTO role_jeu (id_jeu, libelle_role) VALUES (:j, 'Poste étranger') RETURNING id_role"),
            {"j": id_autre_jeu},
        ).scalar_one()
    yield {"idJeu": id_jeu, "postes": postes, "posteEtranger": poste_etranger}
    with database.session() as session:
        session.execute(
            text("DELETE FROM tournoi WHERE id_jeu IN (:a, :b)"), {"a": id_jeu, "b": id_autre_jeu}
        )
        session.execute(text("DELETE FROM jeu WHERE id_jeu IN (:a, :b)"), {"a": id_jeu, "b": id_autre_jeu})