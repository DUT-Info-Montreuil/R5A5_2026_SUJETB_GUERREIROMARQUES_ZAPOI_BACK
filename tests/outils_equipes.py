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


def attribuer_poste(capitaine, id_equipe: int, id_utilisateur: int, id_role: int) -> None:
    reponse = capitaine.patch(f"/api/equipes/{id_equipe}/membres/{id_utilisateur}", json={"idRole": id_role})
    assert reponse.status_code == 200, reponse.get_json()


def ajouter_membre_avec_poste(capitaine, joueur, id_equipe: int, id_role: int) -> None:
    """Un membre « prêt à jouer » : dans l'équipe, et avec son poste (B-08)."""
    ajouter_membre(capitaine, joueur, id_equipe)
    attribuer_poste(capitaine, id_equipe, joueur.id_utilisateur, id_role)


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

def monter_duel(fabrique_clients, jeu) -> SimpleNamespace:
    """Un tournoi à 2 équipes complètes, lancé : une finale jouable entre « Alpha » et « Beta ».

    Chaque équipe a son capitaine (`capitaine_alpha`) et un membre (`membre_alpha`).
    """
    admin = fabrique_clients("admin", administrateur=True)
    postes = jeu["postes"]
    id_tournoi = creer_tournoi(admin, jeu["idJeu"], nombre_equipes=2)
    capitaine_alpha, capitaine_beta = fabrique_clients("cap_alpha"), fabrique_clients("cap_beta")
    membre_alpha, membre_beta = fabrique_clients("mem_alpha"), fabrique_clients("mem_beta")
    id_alpha = equipe_creee(capitaine_alpha, id_tournoi, "Alpha", postes[0])
    id_beta = equipe_creee(capitaine_beta, id_tournoi, "Beta", postes[0])
    ajouter_membre_avec_poste(capitaine_alpha, membre_alpha, id_alpha, postes[1])
    ajouter_membre_avec_poste(capitaine_beta, membre_beta, id_beta, postes[1])
    clore(admin, id_tournoi)
    assert changer_statut(admin, id_tournoi, "EN_COURS").status_code == 200
    return SimpleNamespace(
        admin=admin,
        capitaine_alpha=capitaine_alpha, membre_alpha=membre_alpha, id_alpha=id_alpha,
        capitaine_beta=capitaine_beta, membre_beta=membre_beta, id_beta=id_beta,
        id_tournoi=id_tournoi,
    )


def finale(client, id_tournoi: int) -> dict:
    return client.get(f"/api/tournois/{id_tournoi}/arbre").get_json()[0]


def gagner_la_finale(admin, id_tournoi: int, id_vainqueur: int):
    """L'administrateur désigne le vainqueur : le perdant est éliminé."""
    return admin.patch(
        f"/api/rencontres/{finale(admin, id_tournoi)['idRencontre']}",
        json={"idVainqueur": id_vainqueur, "typeResultat": "NORMAL"},
    )


def poster(client, id_equipe: int, contenu: str = "Bonjour l'équipe"):
    return client.post(f"/api/equipes/{id_equipe}/messages", json={"contenu": contenu})


def lire_messages(client, id_equipe: int):
    return client.get(f"/api/equipes/{id_equipe}/messages")
