"""
Révocation des sessions (contrat §2.3). Avant : se déconnecter n'effaçait que le cookie, et un jeton
volé restait valable jusqu'à son expiration (12 h). Maintenant, la déconnexion invalide les jetons
du compte tout de suite, en HTTP comme sur les connexions temps réel déjà ouvertes.
"""

import logging
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from project_organizer import sockets
from project_organizer.extensions import socketio
from project_organizer.utils.metriques import metriques

from .conftest import MOT_DE_PASSE_TEST, PREFIXE_PSEUDO_TEST
from .outils_equipes import ajouter_membre, monter_decor


def _jeton(reponse) -> str:
    """Le jeton posé par une réponse (inscription ou connexion), tel qu'un voleur pourrait le copier."""
    cookie = next(c for c in reponse.headers.getlist("Set-Cookie") if c.startswith("jeton="))
    return cookie.split(";", 1)[0].removeprefix("jeton=")


def _client_avec(app, jeton: str):
    client = app.test_client()
    client.set_cookie("jeton", jeton)
    return client


def _se_connecter(app, suffixe: str):
    pseudo = PREFIXE_PSEUDO_TEST + suffixe
    client = app.test_client()
    reponse = client.post("/api/auth/connexion", json={"email": f"{pseudo}@iut.fr", "motDePasse": MOT_DE_PASSE_TEST})
    assert reponse.status_code == 200
    return client, _jeton(reponse)


# --- En HTTP -----------------------------------------------------------------------------------------

def test_un_jeton_copie_ne_marche_plus_apres_la_deconnexion(app, client, inscrire):
    jeton = _jeton(inscrire("vol"))
    voleur = _client_avec(app, jeton)
    assert voleur.get("/api/auth/moi").status_code == 200

    assert client.post("/api/auth/deconnexion").status_code == 204

    refus = voleur.get("/api/auth/moi")
    assert refus.status_code == 401
    assert refus.get_json()["detail"] == "Session révoquée. Reconnectez-vous."


def test_se_deconnecter_revoque_aussi_les_autres_appareils(app, client, inscrire):
    inscrire("deuxappareils")
    autre_appareil, _ = _se_connecter(app, "deuxappareils")
    assert autre_appareil.get("/api/auth/moi").status_code == 200

    client.post("/api/auth/deconnexion")

    assert autre_appareil.get("/api/auth/moi").status_code == 401


def test_on_peut_se_reconnecter_apres_la_deconnexion(app, client, inscrire):
    inscrire("retour")
    client.post("/api/auth/deconnexion")

    nouveau, _ = _se_connecter(app, "retour")

    assert nouveau.get("/api/auth/moi").status_code == 200


def test_la_deconnexion_sans_session_reste_un_204(client):
    assert client.post("/api/auth/deconnexion").status_code == 204


def test_la_deconnexion_avec_un_cookie_falsifie_reste_un_204(client):
    client.set_cookie("jeton", "ceci-n-est-pas-un-jeton")

    assert client.post("/api/auth/deconnexion").status_code == 204


def test_la_deconnexion_avec_un_jeton_expire_reste_un_204_et_ne_revoque_rien(app, client, inscrire):
    reponse = inscrire("expire")
    valide = _jeton(reponse)
    with app.app_context():
        # Un vieux jeton du même compte : expiré depuis une heure.
        expire = create_access_token(identity="1", additional_claims={"ver": 1}, expires_delta=timedelta(hours=-1))
    vieux_client = _client_avec(app, expire)

    assert vieux_client.post("/api/auth/deconnexion").status_code == 204
    # Le jeton valide du compte n'a pas été révoqué par un jeton qui n'était plus valable.
    assert _client_avec(app, valide).get("/api/auth/moi").status_code == 200


def test_un_jeton_deja_revoque_ne_revoque_pas_la_session_suivante(app, client, inscrire):
    """Une déconnexion rejouée avec l'ancien jeton ne doit pas déconnecter la session ouverte depuis."""
    ancien = _jeton(inscrire("rejeu"))
    client.post("/api/auth/deconnexion")
    nouveau, _ = _se_connecter(app, "rejeu")

    rejeu = _client_avec(app, ancien)
    assert rejeu.post("/api/auth/deconnexion").status_code == 204

    assert nouveau.get("/api/auth/moi").status_code == 200


def test_la_deconnexion_est_journalisee(client, inscrire, caplog):
    inscrire("journal")

    with caplog.at_level(logging.INFO):
        client.post("/api/auth/deconnexion")

    assert any(r.getMessage() == "Sessions révoquées à la déconnexion" for r in caplog.records)


# --- Sur les connexions temps réel déjà ouvertes ---------------------------------------------------

@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    decor = monter_decor(fabrique_clients, jeu_a_postes)
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    return decor


def _connecter(app, client):
    connexion = socketio.test_client(app, flask_test_client=client)
    assert connexion.is_connected()
    connexion.get_received()
    return connexion


def test_une_connexion_temps_reel_est_coupee_quand_son_jeton_est_revoque(app, decor):
    connectee = _connecter(app, decor.joueur)
    autre = _connecter(app, decor.capitaine)
    visiteur = _connecter(app, app.test_client())
    avant = metriques.instantane()["coupuresPourRevocation"]

    decor.joueur.post("/api/auth/deconnexion")
    fermees = sockets.fermer_les_connexions_revoquees()

    assert fermees >= 1
    assert not connectee.is_connected()
    assert autre.is_connected() and visiteur.is_connected()
    assert metriques.instantane()["coupuresPourRevocation"] >= avant + 1


def test_la_surveillance_ne_coupe_pas_une_connexion_dont_le_jeton_est_valide(app, decor):
    # Des connexions laissées ouvertes par d'autres tests (leurs comptes sont supprimés) seraient comptées.
    sockets._CONNEXIONS.clear()
    connexion = _connecter(app, decor.joueur)

    assert sockets.fermer_les_connexions_revoquees() == 0
    assert connexion.is_connected()


def test_la_boucle_de_surveillance_ferme_les_connexions_expirees_ET_revoquees(monkeypatch):
    """La fermeture des connexions révoquées n'a d'effet que si la boucle de fond l'appelle."""
    appels = []
    monkeypatch.setattr(sockets, "fermer_les_connexions_expirees", lambda: appels.append("expirees"))
    monkeypatch.setattr(sockets, "fermer_les_connexions_revoquees", lambda: appels.append("revoquees"))

    class ArretDeLaBoucle(Exception):
        pass

    pauses = []

    def pause(secondes):
        pauses.append(secondes)
        if len(pauses) > 1:  # une seule passe : on interrompt à la deuxième pause
            raise ArretDeLaBoucle

    monkeypatch.setattr(socketio, "sleep", pause)

    with pytest.raises(ArretDeLaBoucle):
        sockets._surveiller()

    assert appels == ["expirees", "revoquees"]


# --- La révocation est atomique ---------------------------------------------------------------------------

def test_une_revocation_ne_s_applique_qu_a_la_version_du_jeton_qui_la_demande(fabrique_clients):
    """Deux déconnexions simultanées d'un même jeton : une seule incrémente, l'autre est sans effet."""
    from project_organizer.services import auth_service

    compte = fabrique_clients("atomique")

    assert auth_service.revoquer_les_sessions(compte.id_utilisateur, 99) is False  # version qui n'est pas la sienne
    assert auth_service.revoquer_les_sessions(compte.id_utilisateur, 1) is True    # la version du jeton
    assert auth_service.revoquer_les_sessions(compte.id_utilisateur, 1) is False   # la même, rejouée
    assert auth_service.revoquer_les_sessions(compte.id_utilisateur, 2) is True    # le jeton suivant peut se révoquer
