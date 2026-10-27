"""
Mise en cache HTTP (cours, « CORS & Caching ») : une lecture publique se revalide (ETag, 304), tout ce
qui est privé ou qui écrit n'est jamais gardé (no-store).
"""

from .outils_equipes import creer_tournoi


# --- Lectures publiques : revalidation ---------------------------------------------------------------

def test_une_lecture_publique_porte_un_etag_et_se_revalide(client):
    premiere = client.get("/api/tournois")

    assert premiere.status_code == 200
    assert premiere.headers["Cache-Control"] == "no-cache"
    etag = premiere.headers["ETag"]
    assert etag

    revalidation = client.get("/api/tournois", headers={"If-None-Match": etag})
    assert revalidation.status_code == 304
    assert revalidation.get_data() == b""
    assert revalidation.headers["ETag"] == etag


def test_une_donnee_modifiee_change_d_etag_et_n_est_jamais_perimee(client, fabrique_clients, jeu_a_postes):
    admin = fabrique_clients("admin_cache", administrateur=True)
    avant = client.get("/api/tournois")

    creer_tournoi(admin, jeu_a_postes["idJeu"], nom="test_Coupe du cache")

    apres = client.get("/api/tournois", headers={"If-None-Match": avant.headers["ETag"]})
    assert apres.status_code == 200, "l'ancien ETag ne doit plus valider une liste qui a changé"
    assert apres.headers["ETag"] != avant.headers["ETag"]
    assert any(t["nomTournoi"] == "test_Coupe du cache" for t in apres.get_json())


def test_un_etag_d_une_autre_ressource_ne_valide_rien(client):
    reponse = client.get("/api/jeux", headers={"If-None-Match": '"etag-qui-ne-correspond-a-rien"'})

    assert reponse.status_code == 200


def test_les_lectures_publiques_ne_fixent_aucune_duree_de_fraicheur(client):
    """Un tournoi change en direct : aucun max-age, sinon l'arbre afficherait un état périmé."""
    for chemin in ("/api/tournois", "/api/jeux"):
        assert "max-age" not in client.get(chemin).headers["Cache-Control"]


# --- Tout le reste : jamais gardé --------------------------------------------------------------------

def test_les_reponses_privees_ne_sont_jamais_gardees(client, inscrire):
    inscrire("cacheprive")

    for chemin in ("/api/auth/moi", "/api/moi/equipes", "/api/moi/demandes"):
        reponse = client.get(chemin)
        assert reponse.status_code == 200
        assert reponse.headers["Cache-Control"] == "no-store", chemin
        assert "ETag" not in reponse.headers, chemin


def test_les_ecritures_ne_sont_jamais_gardees(client):
    reponse = client.post("/api/auth/deconnexion")

    assert reponse.headers["Cache-Control"] == "no-store"


def test_les_erreurs_ne_sont_jamais_gardees(client):
    introuvable = client.get("/api/tournois/999999")
    refus = client.get("/api/auth/moi")

    assert introuvable.status_code == 404 and introuvable.headers["Cache-Control"] == "no-store"
    assert refus.status_code == 401 and refus.headers["Cache-Control"] == "no-store"


def test_l_etat_de_sante_n_est_jamais_garde(client):
    reponse = client.get("/health")

    assert reponse.headers["Cache-Control"] == "no-store"
    assert "ETag" not in reponse.headers
