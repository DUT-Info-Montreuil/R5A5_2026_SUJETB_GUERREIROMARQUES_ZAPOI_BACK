"""
Refuser par défaut (cours, « Où placer la vérification ») : toute route exige
un jeton, sauf celles déclarées publiques. Ce test attrape l'oubli d'un
décorateur : une nouvelle route non publique qui répondrait sans jeton le fait
échouer.
"""

import re

ROUTES_PUBLIQUES = {
    ("GET", "/health"),
    ("POST", "/api/auth/inscription"),
    ("POST", "/api/auth/connexion"),
    ("POST", "/api/auth/deconnexion"),
    ("GET", "/api/tournois"),
}


def _routes_de_l_api(app):
    for regle in app.url_map.iter_rules():
        if not regle.rule.startswith("/api/"):
            continue
        chemin = re.sub(r"<(?:\w+:)?\w+>", "1", regle.rule)
        for methode in regle.methods - {"HEAD", "OPTIONS"}:
            yield methode, regle.rule, chemin


def test_toute_route_non_publique_exige_un_jeton(app, client):
    client.delete_cookie("jeton")

    for methode, regle, chemin in _routes_de_l_api(app):
        if (methode, regle) in ROUTES_PUBLIQUES:
            continue
        reponse = client.open(chemin, method=methode, json={})
        assert reponse.status_code == 401, f"{methode} {regle} répond {reponse.status_code} sans jeton"


def test_les_reponses_portent_les_en_tetes_de_securite(client):
    entetes = client.get("/health").headers

    assert entetes["X-Content-Type-Options"] == "nosniff"
    assert entetes["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in entetes["Content-Security-Policy"]
