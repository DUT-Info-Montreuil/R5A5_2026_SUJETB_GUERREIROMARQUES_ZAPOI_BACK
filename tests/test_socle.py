"""
Tests du socle : ils vérifient que l'architecture tient ses promesses avant
même la première fonctionnalité.

Les tests notés — droits d'accès — viendront avec chaque fonctionnalité : pour
chaque règle du sujet, un test qui prouve qu'un utilisateur non autorisé est
refusé. Ils se rangent dans ce dossier, un fichier par ressource.
"""

from project_organizer.services import sante_service
from project_organizer.services.sante_service import BaseInjoignable


# ---------------------------------------------------------------------------
#  La chaîne complète fonctionne
# ---------------------------------------------------------------------------

def test_health_traverse_toutes_les_couches_jusqu_a_la_base(client):
    reponse = client.get("/health")

    assert reponse.status_code == 200
    corps = reponse.get_json()
    assert corps["statut"] == "ok"
    assert corps["baseDeDonnees"]["tables"] == 9
    assert corps["baseDeDonnees"]["schemaComplet"] is True


def test_health_bascule_en_503_sans_divulguer_le_detail_technique(client, monkeypatch):
    def base_eteinte():
        raise BaseInjoignable

    monkeypatch.setattr(sante_service, "etat_de_la_base", base_eteinte)
    reponse = client.get("/health")

    assert reponse.status_code == 503
    assert reponse.get_json()["baseDeDonnees"] == {"joignable": False}


# ---------------------------------------------------------------------------
#  Les conventions du contrat d'API sont tenues
# ---------------------------------------------------------------------------

def test_une_erreur_metier_devient_une_reponse_au_format_du_contrat(client):
    reponse = client.get("/_tests/erreur-metier")

    assert reponse.status_code == 409
    assert reponse.get_json() == {"erreur": "Conflict", "detail": "Les inscriptions sont closes."}


def test_une_erreur_inattendue_ne_divulgue_rien(client):
    reponse = client.get("/_tests/erreur-inattendue")

    assert reponse.status_code == 500
    assert "détail interne" not in reponse.get_data(as_text=True)


def test_une_route_inconnue_repond_au_format_du_contrat(client):
    reponse = client.get("/route-inexistante")

    assert reponse.status_code == 404
    assert set(reponse.get_json()) == {"erreur", "detail"}


def test_chaque_reponse_porte_un_identifiant_de_requete(client):
    assert len(client.get("/health").headers.get("X-Request-Id", "")) == 12


def test_cors_n_autorise_que_le_front(client):
    autorise = client.get("/health", headers={"Origin": "http://localhost:5173"})
    refuse = client.get("/health", headers={"Origin": "http://site-malveillant.example"})

    assert autorise.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in refuse.headers
