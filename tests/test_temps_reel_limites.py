"""
Temps réel — ce que le cours demande en plus des droits d'accès :
heartbeat réglé, messages entrants limités, connexions expirées fermées,
métriques de supervision (« Valider les messages entrants », « Superviser les
connexions »).
"""

import time

import pytest

from project_organizer import sockets
from project_organizer.config import Config
from project_organizer.extensions import socketio
from project_organizer.utils.metriques import MetriquesTempsReel, metriques

from .outils_equipes import ajouter_membre, monter_decor, poster

PROXY_READ_TIMEOUT_NGINX = 60


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


def _suivre(connexion, id_tournoi=1):
    return connexion.emit("tournoi:suivre", {"idTournoi": id_tournoi}, callback=True)


# --- Heartbeat et taille maximale -----------------------------------------------------------

def test_le_heartbeat_est_regle_sous_le_delai_du_proxy(app):
    moteur = socketio.server.eio

    assert moteur.ping_interval == Config.SOCKET_PING_INTERVALLE_SECONDES
    assert moteur.ping_timeout == Config.SOCKET_PING_DELAI_SECONDES
    # Réglé par nous, pas laissé aux valeurs par défaut de la bibliothèque (25 s et 20 s).
    assert (moteur.ping_interval, moteur.ping_timeout) == (20, 15)
    # Un proxy coupe une connexion silencieuse au bout de 60 s : le ping doit passer avant.
    assert moteur.ping_interval < PROXY_READ_TIMEOUT_NGINX


def test_la_taille_des_messages_recus_est_plafonnee(app):
    assert socketio.server.eio.max_http_buffer_size == Config.SOCKET_TAILLE_MAX_OCTETS
    assert Config.SOCKET_TAILLE_MAX_OCTETS <= 4096


# --- Plafond d'événements par connexion ----------------------------------------------------------

def test_un_client_normal_n_est_jamais_coupe(app, decor):
    connexion = _connecter(app, decor.joueur)

    for _ in range(Config.SOCKET_EVENEMENTS_MAX):
        assert _suivre(connexion) == {"ok": True}

    assert connexion.is_connected()


def test_un_client_qui_inonde_le_serveur_est_coupe(app, decor):
    avant = metriques.instantane()["coupuresPourDebit"]
    inondeur = _connecter(app, decor.joueur)
    sage = _connecter(app, decor.autre)

    for _ in range(Config.SOCKET_EVENEMENTS_MAX + 5):
        _suivre(inondeur)
        if not inondeur.is_connected():
            break

    assert not inondeur.is_connected()
    assert metriques.instantane()["coupuresPourDebit"] == avant + 1
    # Un autre client n'est pas touché : le plafond est par connexion.
    assert _suivre(sage) == {"ok": True}
    assert sage.is_connected()


def test_le_plafond_porte_aussi_sur_les_abonnements_d_equipe(app, decor):
    connexion = _connecter(app, decor.joueur)

    for _ in range(Config.SOCKET_EVENEMENTS_MAX + 5):
        connexion.emit("equipe:suivre", {"idEquipe": decor.id_equipe})
        if not connexion.is_connected():
            break

    assert not connexion.is_connected()


def test_le_plafond_se_mesure_sur_une_fenetre_de_temps(app, decor, monkeypatch):
    """Des événements espacés ne s'additionnent pas : seul un débit élevé est puni."""
    monkeypatch.setattr(Config, "SOCKET_FENETRE_DEBIT_SECONDES", 0)
    connexion = _connecter(app, decor.joueur)

    for _ in range(Config.SOCKET_EVENEMENTS_MAX * 3):
        _suivre(connexion)

    assert connexion.is_connected()


# --- Fermeture à l'expiration du jeton -------------------------------------------------------------

def test_une_connexion_dont_le_jeton_a_expire_est_fermee(app, decor):
    authentifiee = _connecter(app, decor.joueur)
    visiteur = _connecter(app, app.test_client())
    avant = metriques.instantane()["coupuresPourExpiration"]

    fermees = sockets.fermer_les_connexions_expirees(maintenant=time.time() + 13 * 3600)

    assert fermees >= 1
    assert not authentifiee.is_connected()
    assert visiteur.is_connected()
    assert metriques.instantane()["coupuresPourExpiration"] >= avant + 1


def test_une_connexion_dont_le_jeton_est_valide_n_est_pas_fermee(app, decor):
    connexion = _connecter(app, decor.joueur)

    sockets.fermer_les_connexions_expirees(maintenant=time.time())

    assert connexion.is_connected()


def test_la_surveillance_ne_demarre_qu_une_fois(monkeypatch):
    demarrages = []
    monkeypatch.setattr(sockets, "_surveillance_demarree", False)
    monkeypatch.setattr(socketio, "start_background_task", lambda *a, **k: demarrages.append(a))

    sockets._demarrer_la_surveillance()
    sockets._demarrer_la_surveillance()

    assert len(demarrages) == 1


# --- Métriques --------------------------------------------------------------------------------------------

def test_les_connexions_sont_comptees_a_l_ouverture_et_a_la_fermeture(app, decor):
    avant = metriques.instantane()

    connexion = _connecter(app, decor.joueur)
    pendant = metriques.instantane()
    connexion.disconnect()
    apres = metriques.instantane()

    assert pendant["connexionsActives"] == avant["connexionsActives"] + 1
    assert pendant["connexionsAuthentifiees"] == avant["connexionsAuthentifiees"] + 1
    assert pendant["ouverturesDerniereMinute"] == avant["ouverturesDerniereMinute"] + 1
    assert apres["connexionsActives"] == avant["connexionsActives"]
    assert apres["fermeturesTotal"] == avant["fermeturesTotal"] + 1


def test_un_visiteur_n_est_pas_compte_comme_authentifie(app):
    avant = metriques.instantane()

    _connecter(app, app.test_client())

    apres = metriques.instantane()
    assert apres["connexionsActives"] == avant["connexionsActives"] + 1
    assert apres["connexionsAuthentifiees"] == avant["connexionsAuthentifiees"]


def test_les_messages_et_les_refus_d_abonnement_sont_comptes(app, decor):
    avant = metriques.instantane()
    intrus = _connecter(app, decor.autre)

    poster(decor.capitaine, decor.id_equipe, "bonjour")
    intrus.emit("equipe:suivre", {"idEquipe": decor.id_equipe}, callback=True)

    apres = metriques.instantane()
    assert apres["messagesTotal"] == avant["messagesTotal"] + 1
    assert apres["messagesDerniereMinute"] == avant["messagesDerniereMinute"] + 1
    assert apres["abonnementsRefuses"] == avant["abonnementsRefuses"] + 1


def test_la_fenetre_d_une_minute_oublie_les_vieux_evenements():
    horloge = [1000.0]
    mesures = MetriquesTempsReel(horloge=lambda: horloge[0])
    mesures.ouverture(authentifiee=False)
    mesures.message_envoye()

    horloge[0] += 61

    instantane = mesures.instantane()
    assert instantane["ouverturesDerniereMinute"] == 0
    assert instantane["messagesDerniereMinute"] == 0
    # Les totaux, eux, n'oublient rien.
    assert instantane["ouverturesTotal"] == 1
    assert instantane["messagesTotal"] == 1


def test_le_nombre_de_connexions_actives_ne_devient_jamais_negatif():
    mesures = MetriquesTempsReel()

    mesures.fermeture(authentifiee=True)

    assert mesures.instantane()["connexionsActives"] == 0
    assert mesures.instantane()["connexionsAuthentifiees"] == 0


# --- La route de supervision : administrateur seulement ----------------------------------------------------

def test_l_administrateur_consulte_les_metriques(decor):
    reponse = decor.admin.get("/api/metriques/temps-reel")

    assert reponse.status_code == 200
    corps = reponse.get_json()
    for champ in ("connexionsActives", "connexionsAuthentifiees", "ouverturesDerniereMinute", "messagesDerniereMinute",
                  "abonnementsRefuses", "coupuresPourDebit", "coupuresPourExpiration", "demarreLe"):
        assert champ in corps


def test_un_joueur_ne_consulte_pas_les_metriques(decor):
    assert decor.capitaine.get("/api/metriques/temps-reel").status_code == 403


def test_un_visiteur_ne_consulte_pas_les_metriques(app):
    assert app.test_client().get("/api/metriques/temps-reel").status_code == 401
