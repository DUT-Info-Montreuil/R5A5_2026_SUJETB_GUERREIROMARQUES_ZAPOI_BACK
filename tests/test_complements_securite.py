"""
Compléments de sécurité : durée du cookie de session, traçabilité des refus
d'accès (404 compris), adresse réelle du client derrière un proxy.
"""

import inspect
import logging

import pytest
from flask import Flask, request

from project_organizer import __main__ as lancement
from project_organizer.config import Config, ConfigurationInvalide, ConfigurationManquante, _cle_secrete
from project_organizer.utils import proxy

from .conftest import MOT_DE_PASSE_TEST, PREFIXE_PSEUDO_TEST
from .outils_equipes import ajouter_membre, demander, lire_messages, monter_decor, poster

JOURNAL_ESPACE = "Accès refusé à l'espace d'échange"
JOURNAL_DEMANDES = "Accès refusé aux demandes d'adhésion"


@pytest.fixture
def decor_sans_membre(fabrique_clients, jeu_a_postes):
    """« Les Rouges » avec son seul capitaine : il reste une place pour une demande."""
    return monter_decor(fabrique_clients, jeu_a_postes)


@pytest.fixture
def decor(decor_sans_membre):
    """« Les Rouges » complète : le capitaine et `joueur`."""
    ajouter_membre(decor_sans_membre.capitaine, decor_sans_membre.joueur, decor_sans_membre.id_equipe)
    return decor_sans_membre


def _refus(caplog, message):
    return [r for r in caplog.records if r.getMessage() == message and r.levelno == logging.WARNING]


# --- Durée du cookie de session (contrat §2.1 : 12 h) ----------------------------------------------

def test_le_cookie_de_session_dure_autant_que_le_jeton(inscrire):
    reponse = inscrire("cookie")

    cookie = next(c for c in reponse.headers.getlist("Set-Cookie") if c.startswith("jeton="))
    assert f"Max-Age={Config.JWT_DUREE_MINUTES * 60}" in cookie
    assert "Max-Age=31540000" not in cookie  # la valeur par défaut de la bibliothèque : un an
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_la_connexion_pose_le_meme_cookie(client, inscrire):
    inscrire("cookie2")

    reponse = client.post(
        "/api/auth/connexion",
        json={"email": f"{PREFIXE_PSEUDO_TEST}cookie2@iut.fr", "motDePasse": MOT_DE_PASSE_TEST},
    )

    cookie = next(c for c in reponse.headers.getlist("Set-Cookie") if c.startswith("jeton="))
    assert f"Max-Age={Config.JWT_DUREE_MINUTES * 60}" in cookie


# --- Les refus d'accès laissent une trace WARNING ---------------------------------------------------

def test_un_intrus_qui_lit_l_espace_d_une_equipe_laisse_une_trace(decor, caplog):
    with caplog.at_level(logging.WARNING):
        assert lire_messages(decor.autre, decor.id_equipe).status_code == 404

    traces = _refus(caplog, JOURNAL_ESPACE)
    assert len(traces) == 1
    contexte = traces[0].contexte
    assert contexte["idUtilisateur"] == decor.autre.id_utilisateur
    assert contexte["idEquipe"] == decor.id_equipe
    assert contexte["action"] == "lecture"
    assert contexte["etaitMembre"] is False


def test_une_ecriture_refusee_est_tracee_comme_telle(decor, caplog):
    with caplog.at_level(logging.WARNING):
        poster(decor.autre, decor.id_equipe, "intrus")

    assert _refus(caplog, JOURNAL_ESPACE)[0].contexte["action"] == "écriture"


def test_une_equipe_inconnue_laisse_la_meme_trace(decor, caplog):
    with caplog.at_level(logging.WARNING):
        assert lire_messages(decor.autre, 999999999).status_code == 404

    assert len(_refus(caplog, JOURNAL_ESPACE)) == 1


def test_un_ancien_membre_est_reconnu_dans_la_trace(decor, caplog):
    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")
    with caplog.at_level(logging.WARNING):
        lire_messages(decor.joueur, decor.id_equipe)

    # Il n'est plus membre au moment du refus.
    assert _refus(caplog, JOURNAL_ESPACE)[0].contexte["etaitMembre"] is False


def test_un_acces_autorise_ne_laisse_pas_de_trace_de_refus(decor, caplog):
    with caplog.at_level(logging.WARNING):
        assert lire_messages(decor.capitaine, decor.id_equipe).status_code == 200
        assert lire_messages(decor.admin, decor.id_equipe).status_code == 200

    assert _refus(caplog, JOURNAL_ESPACE) == []


def test_les_demandes_consultees_par_un_non_capitaine_laissent_une_trace(decor_sans_membre, caplog):
    decor = decor_sans_membre
    assert demander(decor.autre, decor.id_equipe).status_code == 201
    with caplog.at_level(logging.WARNING):
        assert decor.joueur.get(f"/api/equipes/{decor.id_equipe}/demandes").status_code == 404

    traces = _refus(caplog, JOURNAL_DEMANDES)
    assert len(traces) == 1 and traces[0].contexte["action"] == "lister"


def test_traiter_une_demande_sans_etre_capitaine_laisse_une_trace(decor_sans_membre, caplog):
    decor = decor_sans_membre
    id_demande = demander(decor.autre, decor.id_equipe).get_json()["idDemande"]
    with caplog.at_level(logging.WARNING):
        decor.joueur.patch(f"/api/demandes/{id_demande}", json={"statutDemande": "ACCEPTEE"})

    assert _refus(caplog, JOURNAL_DEMANDES)[0].contexte["action"] == "traiter"


def test_les_traces_de_refus_ne_contiennent_ni_adresse_e_mail_ni_message(decor, caplog):
    with caplog.at_level(logging.WARNING):
        poster(decor.autre, decor.id_equipe, "contenu secret du message")

    trace = str(_refus(caplog, JOURNAL_ESPACE)[0].contexte) + _refus(caplog, JOURNAL_ESPACE)[0].getMessage()
    assert "@iut.fr" not in trace
    assert "contenu secret" not in trace


# --- Adresse réelle du client derrière un proxy ---------------------------------------------------------

def _application_de_test(nombre_de_proxys: int) -> Flask:
    application = Flask(__name__)
    application.add_url_rule("/adresse", "adresse", lambda: request.remote_addr)
    proxy.installer(application, nombre_de_proxys)
    return application


def test_derriere_un_proxy_de_confiance_l_adresse_est_celle_du_client():
    client = _application_de_test(1).test_client()

    reponse = client.get("/adresse", headers={"X-Forwarded-For": "203.0.113.7"})

    assert reponse.get_data(as_text=True) == "203.0.113.7"


def test_sans_proxy_de_confiance_l_en_tete_est_ignore():
    """Sinon n'importe quel client contournerait le limiteur de débit en changeant d'adresse à chaque requête."""
    client = _application_de_test(0).test_client()

    reponse = client.get("/adresse", headers={"X-Forwarded-For": "203.0.113.7"})

    assert reponse.get_data(as_text=True) != "203.0.113.7"


def test_un_en_tete_falsifie_par_le_client_est_neutralise_par_notre_proxy():
    """Nginx ajoute l'adresse qu'il voit EN FIN de liste : on ne retient que la dernière entrée de confiance."""
    client = _application_de_test(1).test_client()

    reponse = client.get("/adresse", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})

    assert reponse.get_data(as_text=True) == "203.0.113.7"


def test_par_defaut_aucun_proxy_n_est_suppose():
    assert Config.PROXIES_DE_CONFIANCE == 0


# --- Clé secrète : refusée si elle est faible --------------------------------------------------------

def test_une_cle_secrete_assez_longue_est_acceptee(monkeypatch):
    monkeypatch.setenv("CLE_DE_TEST", "x" * 32)

    assert _cle_secrete("CLE_DE_TEST") == "x" * 32


@pytest.mark.parametrize("cle", ["court", "x" * 31, "a-remplacer-par-une-cle-generee", "A-REMPLACER-" + "x" * 40])
def test_une_cle_secrete_faible_ou_celle_du_modele_empeche_de_demarrer(monkeypatch, cle):
    monkeypatch.setenv("CLE_DE_TEST", cle)

    with pytest.raises(ConfigurationInvalide) as erreur:
        _cle_secrete("CLE_DE_TEST")
    assert "secrets.token_urlsafe" in str(erreur.value), "le message doit dire comment en générer une"


def test_une_cle_secrete_absente_empeche_de_demarrer(monkeypatch):
    monkeypatch.delenv("CLE_DE_TEST", raising=False)

    with pytest.raises(ConfigurationManquante):
        _cle_secrete("CLE_DE_TEST")


# --- Lancement de développement : il suit la configuration -------------------------------------------

def test_le_lancement_de_developpement_suit_la_configuration():
    """Le mode debug de Flask ouvre un débogueur interactif : il ne doit jamais être forcé en dur."""
    source = inspect.getsource(lancement)

    assert "debug=Config.DEBUG" in source
    assert "host=Config.HOTE" in source
    assert "debug=True" not in source


def test_l_adresse_d_ecoute_par_defaut_est_la_machine_seule():
    assert Config.HOTE == "127.0.0.1"
