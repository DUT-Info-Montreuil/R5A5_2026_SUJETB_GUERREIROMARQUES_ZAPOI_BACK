"""
Temps réel (contrat §7, B-16 à B-19) : qui peut s'abonner à quoi, ce qui est
poussé, et surtout la perte d'accès immédiate d'un joueur exclu (B-17).

On teste avec le client Socket.IO de Flask-SocketIO : il porte le cookie de
session comme le ferait le navigateur, et reçoit les événements émis par les
routes HTTP.
"""

import pytest
from sqlalchemy import text

from project_organizer.extensions import socketio
from project_organizer.utils import database

from .outils_equipes import (
    ajouter_membre,
    ajouter_membre_avec_poste,
    changer_statut,
    clore,
    creer_tournoi,
    equipe_creee,
    gagner_la_finale,
    monter_decor,
    monter_duel,
    poster,
)


def _connecter(app, client):
    """Une connexion temps réel qui porte les cookies de ce client HTTP."""
    connexion = socketio.test_client(app, flask_test_client=client)
    assert connexion.is_connected()
    connexion.get_received()  # écarte « bienvenue »
    return connexion


def _suivre_equipe(connexion, id_equipe):
    return connexion.emit("equipe:suivre", {"idEquipe": id_equipe}, callback=True)


def _evenements(connexion, nom=None):
    recus = connexion.get_received()
    return [e for e in recus if nom is None or e["name"] == nom]


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    """« Les Rouges » : le capitaine et `joueur`, membre."""
    decor = monter_decor(fabrique_clients, jeu_a_postes)
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    return decor


@pytest.fixture
def duel(fabrique_clients, jeu_a_postes):
    return monter_duel(fabrique_clients, jeu_a_postes)


# --- Abonnement à l'espace d'une équipe -------------------------------------------------

def test_un_membre_s_abonne_a_son_equipe(app, decor):
    connexion = _connecter(app, decor.joueur)

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": True}


def test_un_visiteur_ne_peut_pas_s_abonner_a_une_equipe(app, decor):
    connexion = _connecter(app, app.test_client())

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}


def test_un_joueur_exterieur_ne_peut_pas_s_abonner(app, decor):
    connexion = _connecter(app, decor.autre)

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}


def test_une_equipe_inconnue_donne_le_meme_refus(app, decor):
    connexion = _connecter(app, decor.joueur)

    assert _suivre_equipe(connexion, 999999999) == {"ok": False}


def test_un_identifiant_invalide_est_refuse(app, decor):
    connexion = _connecter(app, decor.joueur)

    for invalide in (None, "1", -1, 0, True, [1], {"x": 1}):
        assert connexion.emit("equipe:suivre", {"idEquipe": invalide}, callback=True) == {"ok": False}
    assert connexion.emit("equipe:suivre", "pas un objet", callback=True) == {"ok": False}


def test_le_visiteur_peut_toujours_suivre_un_tournoi(app, decor):
    connexion = _connecter(app, app.test_client())

    assert connexion.emit("tournoi:suivre", {"idTournoi": decor.id_tournoi}, callback=True) == {"ok": True}


def test_l_administrateur_peut_s_abonner_a_n_importe_quelle_equipe(app, decor):
    connexion = _connecter(app, decor.admin)

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": True}


# --- Messages poussés (B-16) --------------------------------------------------------------

def test_un_message_est_pousse_aux_membres_abonnes_et_a_eux_seuls(app, decor):
    equipe_voisine = equipe_creee(decor.autre, decor.id_tournoi, "Les Bleus", decor.postes[0])
    membre = _connecter(app, decor.joueur)
    voisin = _connecter(app, decor.autre)
    visiteur = _connecter(app, app.test_client())
    _suivre_equipe(membre, decor.id_equipe)
    _suivre_equipe(voisin, equipe_voisine)
    visiteur.emit("tournoi:suivre", {"idTournoi": decor.id_tournoi})
    visiteur.get_received()

    poster(decor.capitaine, decor.id_equipe, "stratégie secrète")

    recus = _evenements(membre, "message:nouveau")
    assert [e["args"][0]["contenu"] for e in recus] == ["stratégie secrète"]
    assert recus[0]["args"][0]["pseudo"] == "test_capitaine"
    assert _evenements(voisin) == []
    assert _evenements(visiteur) == []


def test_un_message_est_pousse_a_l_administrateur_abonne(app, decor):
    admin = _connecter(app, decor.admin)
    _suivre_equipe(admin, decor.id_equipe)

    poster(decor.capitaine, decor.id_equipe, "bonjour")

    assert len(_evenements(admin, "message:nouveau")) == 1


def test_un_message_refuse_n_est_pas_pousse(app, decor):
    membre = _connecter(app, decor.joueur)
    _suivre_equipe(membre, decor.id_equipe)

    poster(decor.autre, decor.id_equipe, "intrus")

    assert _evenements(membre) == []


# --- B-17 : un joueur exclu perd l'accès tout de suite ---------------------------------------

def test_un_joueur_exclu_est_prevenu_puis_ne_recoit_plus_rien(app, decor):
    exclu = _connecter(app, decor.joueur)
    _suivre_equipe(exclu, decor.id_equipe)
    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    evenements = _evenements(exclu, "equipe:acces-revoque")
    assert [e["args"][0] for e in evenements] == [{"idEquipe": decor.id_equipe, "motif": "exclusion"}]

    poster(decor.capitaine, decor.id_equipe, "vous ne devriez pas lire ça")
    assert _evenements(exclu) == []


def test_un_joueur_exclu_ne_peut_plus_se_reabonner(app, decor):
    exclu = _connecter(app, decor.joueur)
    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    assert _suivre_equipe(exclu, decor.id_equipe) == {"ok": False}


def test_une_exclusion_pendant_l_abonnement_ne_laisse_pas_le_joueur_dans_le_salon(app, decor, monkeypatch):
    """Audit V-07 : l'exclusion arrive entre la vérification des droits et l'entrée dans le salon.

    Son « retirer du salon » passe alors AVANT l'entrée : sans revérification, le joueur
    exclu resterait dans le salon et lirait les messages de l'équipe jusqu'à sa reconnexion.
    """
    from project_organizer import sockets
    from project_organizer.services import espace_service

    connexion = _connecter(app, decor.joueur)
    vraie_regle = espace_service.autoriser_abonnement
    appels = []

    def regle_puis_exclusion(*args):
        autorise = vraie_regle(*args)
        if not appels:
            decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")
        appels.append(autorise)
        return autorise

    monkeypatch.setattr(sockets.espace_service, "autoriser_abonnement", regle_puis_exclusion)

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}
    connexion.get_received()
    poster(decor.capitaine, decor.id_equipe, "réservé à l'équipe")
    assert _evenements(connexion, "message:nouveau") == []


def test_l_exclusion_coupe_toutes_les_connexions_du_joueur(app, decor):
    onglet_1, onglet_2 = _connecter(app, decor.joueur), _connecter(app, decor.joueur)
    _suivre_equipe(onglet_1, decor.id_equipe)
    _suivre_equipe(onglet_2, decor.id_equipe)

    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")
    poster(decor.capitaine, decor.id_equipe, "après")

    for onglet in (onglet_1, onglet_2):
        assert [e["name"] for e in _evenements(onglet)] == ["equipe:acces-revoque"]


def test_les_autres_membres_gardent_leur_acces(app, decor):
    capitaine = _connecter(app, decor.capitaine)
    _suivre_equipe(capitaine, decor.id_equipe)
    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    poster(decor.capitaine, decor.id_equipe, "on continue")

    assert [e["name"] for e in _evenements(capitaine)] == ["message:nouveau"]


def test_un_joueur_qui_quitte_lui_meme_perd_aussi_l_acces(app, decor):
    parti = _connecter(app, decor.joueur)
    _suivre_equipe(parti, decor.id_equipe)

    decor.joueur.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")
    poster(decor.capitaine, decor.id_equipe, "après son départ")

    assert [e["name"] for e in _evenements(parti)] == ["equipe:acces-revoque"]


# --- B-18 : espace fermé pour une équipe éliminée ou disqualifiée -----------------------------

def test_une_equipe_eliminee_est_prevenue_et_l_administrateur_garde_l_acces(app, duel):
    perdants = [_connecter(app, duel.capitaine_beta), _connecter(app, duel.membre_beta)]
    admin = _connecter(app, duel.admin)
    for connexion in (*perdants, admin):
        _suivre_equipe(connexion, duel.id_beta)

    gagner_la_finale(duel.admin, duel.id_tournoi, duel.id_alpha)

    for connexion in perdants:
        recus = _evenements(connexion, "equipe:acces-revoque")
        assert [e["args"][0] for e in recus] == [{"idEquipe": duel.id_beta, "motif": "elimination"}]
    assert _evenements(admin, "equipe:acces-revoque") == []
    assert _suivre_equipe(admin, duel.id_beta) == {"ok": True}
    assert _suivre_equipe(perdants[0], duel.id_beta) == {"ok": False}


def test_une_equipe_disqualifiee_est_prevenue(app, duel):
    membre = _connecter(app, duel.membre_alpha)
    _suivre_equipe(membre, duel.id_alpha)

    duel.admin.patch(f"/api/equipes/{duel.id_alpha}", json={"statutEquipe": "DISQUALIFIEE"})

    assert [e["args"][0]["motif"] for e in _evenements(membre, "equipe:acces-revoque")] == ["disqualification"]


def test_une_equipe_incomplete_eliminee_au_lancement_est_prevenue(app, fabrique_clients, jeu_a_postes):
    admin = fabrique_clients("admin", administrateur=True)
    postes = jeu_a_postes["postes"]
    id_tournoi = creer_tournoi(admin, jeu_a_postes["idJeu"], nombre_equipes=4)
    complete_1, complete_2, seule = fabrique_clients("c1"), fabrique_clients("c2"), fabrique_clients("seule")
    id_1 = equipe_creee(complete_1, id_tournoi, "Complète 1", postes[0])
    id_2 = equipe_creee(complete_2, id_tournoi, "Complète 2", postes[0])
    id_seule = equipe_creee(seule, id_tournoi, "Incomplète", postes[0])
    ajouter_membre_avec_poste(complete_1, fabrique_clients("m1"), id_1, postes[1])
    ajouter_membre_avec_poste(complete_2, fabrique_clients("m2"), id_2, postes[1])
    clore(admin, id_tournoi)
    connexion = _connecter(app, seule)
    _suivre_equipe(connexion, id_seule)

    assert changer_statut(admin, id_tournoi, "EN_COURS").status_code == 200

    recus = _evenements(connexion, "equipe:acces-revoque")
    assert [e["args"][0] for e in recus] == [{"idEquipe": id_seule, "motif": "elimination"}]


# --- Authentification du socket : le jeton est revérifié à chaque abonnement ------------------

def test_un_jeton_revoque_apres_la_connexion_ne_permet_plus_de_s_abonner(app, decor):
    connexion = _connecter(app, decor.joueur)
    with database.session() as session:
        session.execute(
            text("UPDATE utilisateur SET version_jeton = version_jeton + 1 WHERE id_utilisateur = :u"),
            {"u": decor.joueur.id_utilisateur},
        )

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}


def test_un_compte_supprime_apres_la_connexion_ne_permet_plus_de_s_abonner(app, fabrique_clients, jeu_a_postes):
    decor = monter_decor(fabrique_clients, jeu_a_postes)
    connexion = _connecter(app, decor.capitaine)
    with database.session() as session:
        session.execute(text("DELETE FROM utilisateur WHERE id_utilisateur = :u"), {"u": decor.capitaine.id_utilisateur})

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}


def test_un_cookie_falsifie_fait_de_la_connexion_celle_d_un_visiteur(app, decor):
    pirate = app.test_client()
    pirate.set_cookie("jeton", "pas.un.vrai.jeton")
    connexion = _connecter(app, pirate)

    assert _suivre_equipe(connexion, decor.id_equipe) == {"ok": False}
    assert connexion.emit("tournoi:suivre", {"idTournoi": decor.id_tournoi}, callback=True) == {"ok": True}


def test_l_identite_ne_se_declare_pas_dans_le_message(app, decor):
    """Un client ne peut pas se dire « joueur » : l'identité vient du cookie de la connexion."""
    connexion = _connecter(app, decor.autre)

    reponse = connexion.emit(
        "equipe:suivre", {"idEquipe": decor.id_equipe, "idUtilisateur": decor.joueur.id_utilisateur}, callback=True
    )

    assert reponse == {"ok": False}
