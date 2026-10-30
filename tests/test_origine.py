"""
Origine des écritures (contrat §2, v14 — audit V-06).

SameSite=Lax ne protège pas d'une page servie par une autre origine du MÊME site
(autre port de la machine, sous-domaine voisin) : son POST emporte le cookie. Les
routes sans corps JSON n'ont alors aucune autre protection. Le serveur refuse donc
toute écriture dont l'en-tête Origin n'est pas autorisé.
"""

ORIGINE_DU_FRONT = "http://localhost:5173"
ORIGINE_DU_MEME_SITE = "http://localhost:8081"


def test_une_ecriture_d_une_origine_etrangere_est_refusee_sans_rien_faire(client, inscrire):
    """Le scénario CSRF : une page sur un autre port déconnecterait la victime (révocation partout)."""
    inscrire()

    reponse = client.post("/api/auth/deconnexion", headers={"Origin": ORIGINE_DU_MEME_SITE})

    assert reponse.status_code == 403
    assert reponse.get_json() == {"erreur": "Forbidden", "detail": "Origine non autorisée."}
    # La session n'a pas été révoquée.
    assert client.get("/api/auth/moi").status_code == 200


def test_une_ecriture_d_une_origine_etrangere_est_refusee_meme_sans_session(client):
    reponse = client.post("/api/equipes/1/demandes", headers={"Origin": ORIGINE_DU_MEME_SITE})

    assert reponse.status_code == 403


def test_une_origine_null_est_refusee(client):
    """Une iframe sandboxée ou une redirection envoie « Origin: null » : rien ne la rend légitime."""
    assert client.post("/api/auth/deconnexion", headers={"Origin": "null"}).status_code == 403


def test_une_ecriture_du_front_autorise_passe(client, inscrire):
    inscrire()

    assert client.post("/api/auth/deconnexion", headers={"Origin": ORIGINE_DU_FRONT}).status_code == 204


def test_une_ecriture_de_l_api_elle_meme_passe(client, inscrire):
    """La page Swagger est servie par l'API : une requête de même origine n'est pas une CSRF."""
    inscrire()

    assert client.post("/api/auth/deconnexion", headers={"Origin": "http://localhost"}).status_code == 204


def test_une_ecriture_sans_origine_passe(client, inscrire):
    """curl et les autres outils n'envoient pas d'Origin : ce ne sont pas des navigateurs piégés."""
    inscrire()

    assert client.post("/api/auth/deconnexion").status_code == 204


def test_une_lecture_d_une_origine_etrangere_n_est_pas_bloquee(client):
    """Une lecture ne change rien ; c'est CORS qui empêche la page étrangère d'en lire la réponse."""
    assert client.get("/api/tournois", headers={"Origin": ORIGINE_DU_MEME_SITE}).status_code == 200
