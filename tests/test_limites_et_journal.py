"""
Plafond global de requêtes, niveaux de la journalisation des requêtes, et
algorithme du jeton : trois garde-fous qui n'ont pas de fonctionnalité propre.
"""

import logging

import jwt as pyjwt
import pytest

from project_organizer.config import Config


# ---------------------------------------------------------------------------
#  Plafond global par adresse
# ---------------------------------------------------------------------------

def test_au_dela_du_plafond_global_la_requete_est_refusee_en_429(client):
    plafond = int(Config.LIMITE_GLOBALE.split()[0])

    statuts = [client.get("/_tests/erreur-metier").status_code for _ in range(plafond + 1)]

    assert set(statuts[:plafond]) == {409}
    assert statuts[plafond] == 429


def test_la_reponse_429_suit_le_format_d_erreur_du_contrat(client):
    plafond = int(Config.LIMITE_GLOBALE.split()[0])
    for _ in range(plafond):
        client.get("/_tests/erreur-metier")

    reponse = client.get("/_tests/erreur-metier")

    assert reponse.status_code == 429
    assert set(reponse.get_json()) == {"erreur", "detail"}


def test_la_sonde_de_sante_n_est_jamais_freinee(client):
    plafond = int(Config.LIMITE_GLOBALE.split()[0])
    for _ in range(plafond + 1):
        client.get("/_tests/erreur-metier")

    assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
#  Journalisation des requêtes : le niveau suit le statut
# ---------------------------------------------------------------------------

def _trace_de_requete(caplog, statut):
    return [
        r for r in caplog.records
        if r.name == "requetes" and getattr(r, "contexte", {}).get("statut") == statut
    ]


@pytest.mark.parametrize(
    ("chemin", "statut", "niveau"),
    [
        ("/health", 200, logging.INFO),
        ("/api/introuvable", 404, logging.WARNING),
        ("/_tests/erreur-metier", 409, logging.WARNING),
        ("/_tests/reservee-admin", 401, logging.WARNING),
        ("/_tests/erreur-inattendue", 500, logging.ERROR),
    ],
)
def test_le_niveau_de_la_trace_suit_le_statut(client, caplog, chemin, statut, niveau):
    with caplog.at_level(logging.INFO, logger="requetes"):
        client.get(chemin)

    traces = _trace_de_requete(caplog, statut)
    assert len(traces) == 1
    assert traces[0].levelno == niveau


def test_la_trace_donne_le_motif_de_la_route_et_la_taille_de_la_reponse(client, caplog):
    with caplog.at_level(logging.INFO, logger="requetes"):
        reponse = client.get("/api/equipes/987654/messages")

    contexte = _trace_de_requete(caplog, reponse.status_code)[0].contexte
    assert contexte["route"] == "/api/equipes/<int:id_equipe>/messages"
    assert contexte["chemin"] == "/api/equipes/987654/messages"
    assert contexte["tailleOctets"] == len(reponse.data)


def test_une_route_inconnue_n_a_pas_de_motif(client, caplog):
    with caplog.at_level(logging.INFO, logger="requetes"):
        client.get("/api/introuvable")

    assert _trace_de_requete(caplog, 404)[0].contexte["route"] is None


# ---------------------------------------------------------------------------
#  Jeton : seul l'algorithme configuré est accepté
# ---------------------------------------------------------------------------

def test_un_jeton_signe_avec_un_autre_algorithme_est_refuse(app, client, inscrire):
    # Un vrai jeton, avec toutes ses revendications, mais re-signé en HS512 avec la bonne clé :
    # seul l'algorithme change. Il serait accepté si l'API acceptait plusieurs algorithmes.
    reponse = inscrire()
    vrai = next(c for c in reponse.headers.getlist("Set-Cookie") if c.startswith("jeton=")).split(";")[0][6:]
    cle = app.config["JWT_SECRET_KEY"]
    charge = pyjwt.decode(vrai, options={"verify_signature": False})
    assert client.get("/api/auth/moi").status_code == 200

    client.set_cookie("jeton", pyjwt.encode(charge, cle, algorithm="HS512"))

    assert client.get("/api/auth/moi").status_code == 401


def test_l_algorithme_du_jeton_est_fixe_par_la_configuration(app):
    assert app.config["JWT_ALGORITHM"] == "HS256"
    assert app.config["JWT_DECODE_ALGORITHMS"] == ["HS256"]
