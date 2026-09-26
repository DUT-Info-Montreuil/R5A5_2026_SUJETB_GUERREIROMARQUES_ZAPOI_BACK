"""
La documentation d'API est générée depuis les DTOs : ces tests vérifient
qu'elle existe, qu'elle décrit les routes, et que la validation qui en découle
respecte le contrat (400, format { erreur, detail }).
"""


def test_la_description_openapi_documente_health_et_ses_deux_reponses(client):
    description = client.get("/apidoc/openapi.json").get_json()

    reponses = description["paths"]["/health"]["get"]["responses"]
    assert {"200", "503"} <= set(reponses)


def test_les_schemas_documentes_sont_en_camel_case(client):
    schemas = client.get("/apidoc/openapi.json").get_json()["components"]["schemas"]

    champs = set().union(*(schema.get("properties", {}) for schema in schemas.values()))
    assert "baseDeDonnees" in champs
    assert "base_de_donnees" not in champs


def test_l_interface_swagger_est_servie(client):
    assert client.get("/apidoc/swagger").status_code == 200


def test_un_champ_manquant_donne_400_au_format_du_contrat(client):
    reponse = client.post("/_tests/validation", json={"pseudo": "fabio"})

    assert reponse.status_code == 400
    assert reponse.get_json() == {
        "erreur": "Bad Request",
        "detail": {"champs": [{"champ": "motDePasse", "message": "Field required"}]},
    }


def test_un_champ_inconnu_est_refuse(client):
    reponse = client.post(
        "/_tests/validation",
        json={"pseudo": "fabio", "motDePasse": "x", "estAdministrateur": True},
    )

    assert reponse.status_code == 400
    assert reponse.get_json()["detail"]["champs"][0]["champ"] == "estAdministrateur"


def test_un_corps_valide_atteint_la_route(client):
    reponse = client.post("/_tests/validation", json={"pseudo": "fabio", "motDePasse": "x"})

    assert reponse.status_code == 204


def test_une_reponse_non_conforme_a_son_dto_devient_une_erreur_500(client):
    reponse = client.get("/_tests/reponse-non-conforme")

    assert reponse.status_code == 500
    assert reponse.get_json() == {"erreur": "Internal Server Error", "detail": "Erreur interne."}