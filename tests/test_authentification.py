"""
Authentification (contrat §2) : chaque test énonce une règle de sécurité
issue du cours ou du contrat.
"""

from sqlalchemy import text

from project_organizer.utils import database

from .conftest import MOT_DE_PASSE_TEST, PREFIXE_PSEUDO_TEST


def _cookie_de_session(reponse) -> str:
    return next(c for c in reponse.headers.getlist("Set-Cookie") if c.startswith("jeton="))


# --- Inscription -------------------------------------------------------------

def test_l_inscription_ouvre_la_session_dans_un_cookie_httponly(inscrire):
    reponse = inscrire()

    cookie = _cookie_de_session(reponse)
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "jeton" not in reponse.get_json()
    assert reponse.get_json()["utilisateur"]["pseudo"] == PREFIXE_PSEUDO_TEST + "alice"


def test_le_mot_de_passe_est_stocke_hache_avec_argon2(inscrire):
    inscrire()

    with database.session() as session:
        empreinte = session.execute(
            text("SELECT mot_de_passe_hash FROM utilisateur WHERE pseudo = :p"),
            {"p": PREFIXE_PSEUDO_TEST + "alice"},
        ).scalar_one()
    assert empreinte.startswith("$argon2id$")
    assert MOT_DE_PASSE_TEST not in empreinte


def test_un_pseudo_deja_pris_donne_409(client, inscrire):
    inscrire()
    reponse = client.post(
        "/api/auth/inscription",
        json={"pseudo": PREFIXE_PSEUDO_TEST + "alice", "email": "autre@iut.fr", "motDePasse": MOT_DE_PASSE_TEST},
    )

    assert reponse.status_code == 409


def test_un_mot_de_passe_trop_court_donne_400(client):
    reponse = client.post(
        "/api/auth/inscription",
        json={"pseudo": PREFIXE_PSEUDO_TEST + "bob", "email": "bob@iut.fr", "motDePasse": "court"},
    )

    assert reponse.status_code == 400
    assert reponse.get_json()["detail"]["champs"][0]["champ"] == "motDePasse"


def test_on_ne_peut_pas_s_inscrire_administrateur(client):
    reponse = client.post(
        "/api/auth/inscription",
        json={
            "pseudo": PREFIXE_PSEUDO_TEST + "mallory",
            "email": "mallory@iut.fr",
            "motDePasse": MOT_DE_PASSE_TEST,
            "estAdministrateur": True,
        },
    )

    assert reponse.status_code == 400


# --- Connexion ---------------------------------------------------------------

def test_la_connexion_ouvre_la_session(client, inscrire):
    inscrire()
    client.post("/api/auth/deconnexion")

    reponse = client.post(
        "/api/auth/connexion",
        json={"email": f"{PREFIXE_PSEUDO_TEST}alice@iut.fr", "motDePasse": MOT_DE_PASSE_TEST},
    )

    assert reponse.status_code == 200
    assert _cookie_de_session(reponse)


def test_email_inconnu_et_mot_de_passe_faux_donnent_le_meme_message(client, inscrire):
    inscrire()
    mauvais_mot_de_passe = client.post(
        "/api/auth/connexion", json={"email": f"{PREFIXE_PSEUDO_TEST}alice@iut.fr", "motDePasse": "faux"}
    )
    email_inconnu = client.post("/api/auth/connexion", json={"email": "personne@iut.fr", "motDePasse": "faux"})

    assert mauvais_mot_de_passe.status_code == email_inconnu.status_code == 401
    assert mauvais_mot_de_passe.get_json() == email_inconnu.get_json()


def test_la_connexion_est_limitee_a_5_tentatives_par_minute(client):
    identifiants = {"email": "personne@iut.fr", "motDePasse": "faux"}
    statuts = [client.post("/api/auth/connexion", json=identifiants).status_code for _ in range(6)]

    assert statuts == [401] * 5 + [429]


# --- Session -----------------------------------------------------------------

def test_moi_renvoie_l_utilisateur_de_la_session(client, inscrire):
    inscrire()

    reponse = client.get("/api/auth/moi")

    assert reponse.status_code == 200
    assert reponse.get_json()["pseudo"] == PREFIXE_PSEUDO_TEST + "alice"


def test_sans_cookie_moi_renvoie_401_au_format_du_contrat(client):
    client.delete_cookie("jeton")

    reponse = client.get("/api/auth/moi")

    assert reponse.status_code == 401
    assert set(reponse.get_json()) == {"erreur", "detail"}


def test_un_jeton_falsifie_donne_401_et_non_422(client):
    client.set_cookie("jeton", "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIn0.")

    assert client.get("/api/auth/moi").status_code == 401


def test_incrementer_version_jeton_revoque_la_session(client, inscrire):
    inscrire()
    with database.session() as session:
        session.execute(
            text("UPDATE utilisateur SET version_jeton = version_jeton + 1 WHERE pseudo = :p"),
            {"p": PREFIXE_PSEUDO_TEST + "alice"},
        )

    assert client.get("/api/auth/moi").status_code == 401


def test_la_deconnexion_efface_le_cookie(client, inscrire):
    inscrire()

    reponse = client.post("/api/auth/deconnexion")

    assert reponse.status_code == 204
    assert "Max-Age=0" in _cookie_de_session(reponse) or "Expires=Thu, 01 Jan 1970" in _cookie_de_session(reponse)
    assert client.get("/api/auth/moi").status_code == 401


# --- Rôles -------------------------------------------------------------------

def test_une_route_d_administration_refuse_un_joueur_avec_403(client, inscrire):
    inscrire()

    assert client.get("/_tests/reservee-admin").status_code == 403


def test_une_route_d_administration_accepte_un_administrateur(client, inscrire):
    inscrire()
    with database.session() as session:
        session.execute(
            text("UPDATE utilisateur SET est_administrateur = TRUE WHERE pseudo = :p"),
            {"p": PREFIXE_PSEUDO_TEST + "alice"},
        )

    assert client.get("/_tests/reservee-admin").status_code == 204
