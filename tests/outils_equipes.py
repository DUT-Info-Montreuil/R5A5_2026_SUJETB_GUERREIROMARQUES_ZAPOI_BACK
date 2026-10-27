"""
Outils partagés par les tests d'équipes et de demandes d'adhésion.

Chaque fonction passe par l'API, comme le ferait le front : un scénario de
test reste ainsi une suite d'appels qu'on peut rejouer à la main.
"""

from types import SimpleNamespace


def creer_tournoi(admin, id_jeu: int, nombre_equipes: int = 4, nom: str = "test_Coupe") -> int:
    reponse = admin.post("/api/tournois", json={"nomTournoi": nom, "idJeu": id_jeu, "nombreEquipes": nombre_equipes})
    assert reponse.status_code == 201, reponse.get_json()
    return reponse.get_json()["idTournoi"]


def creer_equipe(client, id_tournoi: int, nom: str, id_role: int):
    return client.post(f"/api/tournois/{id_tournoi}/equipes", json={"nomEquipe": nom, "idRole": id_role})


def equipe_creee(client, id_tournoi: int, nom: str, id_role: int) -> int:
    reponse = creer_equipe(client, id_tournoi, nom, id_role)
    assert reponse.status_code == 201, reponse.get_json()
    return reponse.get_json()["idEquipe"]


def demander(joueur, id_equipe: int):
    return joueur.post(f"/api/equipes/{id_equipe}/demandes")


def traiter(capitaine, id_demande: int, statut: str):
    return capitaine.patch(f"/api/demandes/{id_demande}", json={"statutDemande": statut})


def ajouter_membre(capitaine, joueur, id_equipe: int) -> None:
    """Le joueur demande, le capitaine accepte : le joueur est dans l'équipe, sans poste."""
    demande = demander(joueur, id_equipe)
    assert demande.status_code == 201, demande.get_json()
    acceptation = traiter(capitaine, demande.get_json()["idDemande"], "ACCEPTEE")
    assert acceptation.status_code == 200, acceptation.get_json()


def changer_statut(admin, id_tournoi: int, statut: str):
    return admin.patch(f"/api/tournois/{id_tournoi}", json={"statutTournoi": statut})


def clore(admin, id_tournoi: int) -> None:
    reponse = changer_statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")
    assert reponse.status_code == 200, reponse.get_json()


def lire_equipe(client, id_equipe: int) -> dict:
    reponse = client.get(f"/api/equipes/{id_equipe}")
    assert reponse.status_code == 200
    return reponse.get_json()


def monter_decor(fabrique_clients, jeu) -> SimpleNamespace:
    """Un tournoi ouvert à 4 équipes, et une équipe « Les Rouges ».

    admin       administrateur
    capitaine   capitaine de « Les Rouges », seul membre, poste 1
    joueur      simple joueur, sans équipe
    autre       second simple joueur, sans équipe
    """
    admin = fabrique_clients("admin", administrateur=True)
    capitaine = fabrique_clients("capitaine")
    id_tournoi = creer_tournoi(admin, jeu["idJeu"])
    return SimpleNamespace(
        admin=admin,
        capitaine=capitaine,
        joueur=fabrique_clients("joueur"),
        autre=fabrique_clients("autre"),
        postes=jeu["postes"],
        poste_etranger=jeu["posteEtranger"],
        id_jeu=jeu["idJeu"],
        id_tournoi=id_tournoi,
        id_equipe=equipe_creee(capitaine, id_tournoi, "Les Rouges", jeu["postes"][0]),
    )