"""
Espace d'échange d'une équipe (contrat §6, B-16 à B-18), côté HTTP.

Une seule règle d'accès gouverne les deux routes (et le socket) : ces tests la
couvrent par ses deux faces, ce qui est autorisé et ce qui est refusé.

    Lecture   membre d'une équipe EN_LICE, ou administrateur
    Écriture  membre d'une équipe EN_LICE ; l'administrateur lit, n'écrit pas
    Refus     404 identique que l'équipe existe ou non ; 403 pour l'administrateur qui écrit
"""

import pytest

from .outils_equipes import (
    ajouter_membre,
    gagner_la_finale,
    lire_messages,
    monter_decor,
    monter_duel,
    poster,
)


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    """« Les Rouges » : le capitaine et `joueur`, membre."""
    decor = monter_decor(fabrique_clients, jeu_a_postes)
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    return decor


@pytest.fixture
def duel(fabrique_clients, jeu_a_postes):
    return monter_duel(fabrique_clients, jeu_a_postes)


# --- Écrire et lire (B-16) ---------------------------------------------------------

def test_un_membre_ecrit_et_toute_l_equipe_lit(decor):
    reponse = poster(decor.joueur, decor.id_equipe, "  On se retrouve à 20 h ?  ")

    assert reponse.status_code == 201
    message = reponse.get_json()
    assert message["contenu"] == "On se retrouve à 20 h ?"
    assert message["idAuteur"] == decor.joueur.id_utilisateur
    assert message["pseudo"] == "test_joueur"
    assert message["idEquipe"] == decor.id_equipe
    for lecteur in (decor.capitaine, decor.joueur):
        assert [m["contenu"] for m in lire_messages(lecteur, decor.id_equipe).get_json()] == ["On se retrouve à 20 h ?"]


def test_les_messages_arrivent_du_plus_ancien_au_plus_recent(decor):
    for numero in (1, 2, 3):
        poster(decor.capitaine, decor.id_equipe, f"message {numero}")

    contenus = [m["contenu"] for m in lire_messages(decor.joueur, decor.id_equipe).get_json()]

    assert contenus == ["message 1", "message 2", "message 3"]


def test_le_texte_est_conserve_tel_quel_sans_html_interprete(decor):
    """L'API ne nettoie rien : c'est le front qui affiche du texte, jamais du HTML."""
    poster(decor.capitaine, decor.id_equipe, "<img src=x onerror=alert(1)>")

    assert lire_messages(decor.joueur, decor.id_equipe).get_json()[0]["contenu"] == "<img src=x onerror=alert(1)>"


# --- Refus : l'espace n'existe pas pour qui n'y a pas accès -------------------------

def test_un_visiteur_ne_lit_ni_n_ecrit(app, decor):
    visiteur = app.test_client()

    assert lire_messages(visiteur, decor.id_equipe).status_code == 401
    assert poster(visiteur, decor.id_equipe).status_code == 401


def test_un_joueur_exterieur_a_l_equipe_ne_lit_ni_n_ecrit(decor):
    poster(decor.capitaine, decor.id_equipe, "secret de l'équipe")

    assert lire_messages(decor.autre, decor.id_equipe).status_code == 404
    assert poster(decor.autre, decor.id_equipe, "intrus").status_code == 404
    assert [m["contenu"] for m in lire_messages(decor.capitaine, decor.id_equipe).get_json()] == ["secret de l'équipe"]


def test_le_refus_ne_revele_pas_l_existence_de_l_equipe(decor):
    """Même code, même message : un intrus ne peut pas deviner quelles équipes existent."""
    existante = lire_messages(decor.autre, decor.id_equipe)
    inexistante = lire_messages(decor.autre, 999999999)

    assert existante.status_code == inexistante.status_code == 404
    assert existante.get_json() == inexistante.get_json()


def test_le_capitaine_d_une_autre_equipe_n_entre_pas(decor):
    from .outils_equipes import equipe_creee

    equipe_creee(decor.autre, decor.id_tournoi, "Les Bleus", decor.postes[0])

    assert lire_messages(decor.autre, decor.id_equipe).status_code == 404


# --- L'administrateur lit, n'écrit pas (B-18) ----------------------------------------

def test_l_administrateur_lit_tout_mais_n_ecrit_pas(decor):
    poster(decor.capitaine, decor.id_equipe, "bonjour")

    assert lire_messages(decor.admin, decor.id_equipe).status_code == 200
    assert poster(decor.admin, decor.id_equipe, "message de l'administration").status_code == 403
    assert len(lire_messages(decor.capitaine, decor.id_equipe).get_json()) == 1


def test_un_membre_devenu_administrateur_ecrit_toujours_en_tant_que_membre(fabrique_clients, jeu_a_postes):
    """Un administrateur ne peut plus rejoindre une équipe, mais un joueur déjà membre puis promu garde sa place."""
    from sqlalchemy import text

    from project_organizer.utils import database

    decor = monter_decor(fabrique_clients, jeu_a_postes)
    with database.session() as session:
        session.execute(
            text("UPDATE utilisateur SET est_administrateur = TRUE WHERE id_utilisateur = :u"), {"u": decor.capitaine.id_utilisateur}
        )

    assert poster(decor.capitaine, decor.id_equipe, "je joue aussi").status_code == 201


# --- Perte d'accès immédiate (B-17) -------------------------------------------------

def test_un_joueur_exclu_perd_l_acces_tout_de_suite(decor):
    poster(decor.joueur, decor.id_equipe, "avant l'exclusion")
    assert lire_messages(decor.joueur, decor.id_equipe).status_code == 200

    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    assert lire_messages(decor.joueur, decor.id_equipe).status_code == 404
    assert poster(decor.joueur, decor.id_equipe, "après l'exclusion").status_code == 404


def test_les_messages_d_un_joueur_exclu_restent_pour_l_equipe(decor):
    poster(decor.joueur, decor.id_equipe, "j'étais là")
    decor.capitaine.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    messages = lire_messages(decor.capitaine, decor.id_equipe).get_json()

    assert [(m["pseudo"], m["contenu"]) for m in messages] == [("test_joueur", "j'étais là")]


# --- Espace fermé : équipe éliminée ou disqualifiée (B-18) ----------------------------

def test_l_espace_d_une_equipe_eliminee_se_ferme_pour_ses_membres_pas_pour_l_administrateur(duel):
    poster(duel.membre_beta, duel.id_beta, "on a perdu ?")

    assert gagner_la_finale(duel.admin, duel.id_tournoi, duel.id_alpha).status_code == 200

    for membre in (duel.capitaine_beta, duel.membre_beta):
        assert lire_messages(membre, duel.id_beta).status_code == 404
        assert poster(membre, duel.id_beta, "encore là").status_code == 404
    assert [m["contenu"] for m in lire_messages(duel.admin, duel.id_beta).get_json()] == ["on a perdu ?"]


def test_l_equipe_qui_continue_garde_son_espace(duel):
    gagner_la_finale(duel.admin, duel.id_tournoi, duel.id_alpha)

    assert poster(duel.membre_alpha, duel.id_alpha, "on a gagné").status_code == 201


def test_l_espace_d_une_equipe_disqualifiee_se_ferme(duel):
    duel.admin.patch(f"/api/equipes/{duel.id_alpha}", json={"statutEquipe": "DISQUALIFIEE"})

    assert lire_messages(duel.membre_alpha, duel.id_alpha).status_code == 404
    assert poster(duel.capitaine_alpha, duel.id_alpha, "injuste").status_code == 404
    assert lire_messages(duel.admin, duel.id_alpha).status_code == 200


# --- Validation et limite de débit ------------------------------------------------------

def test_un_message_invalide_donne_400(decor):
    chemin = f"/api/equipes/{decor.id_equipe}/messages"

    assert decor.capitaine.post(chemin, json={"contenu": ""}).status_code == 400
    assert decor.capitaine.post(chemin, json={"contenu": "    "}).status_code == 400
    assert decor.capitaine.post(chemin, json={"contenu": "x" * 2001}).status_code == 400
    assert decor.capitaine.post(chemin, json={}).status_code == 400
    assert decor.capitaine.post(chemin, json={"contenu": "ok", "idAuteur": 1}).status_code == 400
    assert decor.capitaine.post(chemin, json={"contenu": "x" * 2000}).status_code == 201


def test_un_message_ne_peut_pas_usurper_un_auteur(decor):
    """L'auteur vient de la session, jamais du corps de la requête (refusé en 400, voir ci-dessus)."""
    poster(decor.joueur, decor.id_equipe, "c'est bien moi")

    assert lire_messages(decor.capitaine, decor.id_equipe).get_json()[0]["idAuteur"] == decor.joueur.id_utilisateur


def test_le_debit_des_messages_est_plafonne_par_utilisateur(decor):
    for _ in range(30):
        assert poster(decor.capitaine, decor.id_equipe).status_code == 201

    assert poster(decor.capitaine, decor.id_equipe).status_code == 429
    # Un autre membre, même adresse, n'est pas pénalisé.
    assert poster(decor.joueur, decor.id_equipe).status_code == 201
