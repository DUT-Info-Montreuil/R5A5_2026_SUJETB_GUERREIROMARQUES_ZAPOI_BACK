"""« Mes équipes » et « mes demandes » : ce que voit l'utilisateur connecté, et rien de plus."""

import pytest

from .outils_equipes import ajouter_membre, demander, equipe_creee, monter_decor


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    return monter_decor(fabrique_clients, jeu_a_postes)


def test_mes_equipes_listent_mon_equipe_et_mon_role(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    capitaine = decor.capitaine.get("/api/moi/equipes").get_json()
    joueur = decor.joueur.get("/api/moi/equipes").get_json()

    assert [(e["idEquipe"], e["nomEquipe"], e["estCapitaine"]) for e in capitaine] == [(decor.id_equipe, "Les Rouges", True)]
    assert [(e["idEquipe"], e["estCapitaine"]) for e in joueur] == [(decor.id_equipe, False)]
    assert capitaine[0]["idTournoi"] == decor.id_tournoi
    assert capitaine[0]["statutEquipe"] == "EN_LICE"
    assert capitaine[0]["statutTournoi"] == "INSCRIPTIONS_OUVERTES"


def test_mes_equipes_ne_montrent_pas_les_equipes_des_autres(decor):
    equipe_creee(decor.autre, decor.id_tournoi, "Les Bleus", decor.postes[0])

    assert decor.joueur.get("/api/moi/equipes").get_json() == []
    assert [e["nomEquipe"] for e in decor.autre.get("/api/moi/equipes").get_json()] == ["Les Bleus"]


def test_une_equipe_quittee_disparait_de_mes_equipes(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    decor.joueur.delete(f"/api/equipes/{decor.id_equipe}/membres/{decor.joueur.id_utilisateur}")

    assert decor.joueur.get("/api/moi/equipes").get_json() == []


def test_mes_demandes_listent_les_demandes_en_attente_seulement(decor):
    demande = demander(decor.joueur, decor.id_equipe).get_json()
    demander(decor.autre, decor.id_equipe)

    mes_demandes = decor.joueur.get("/api/moi/demandes").get_json()

    assert [(d["idDemande"], d["nomEquipe"], d["statutDemande"]) for d in mes_demandes] == [
        (demande["idDemande"], "Les Rouges", "EN_ATTENTE")
    ]
    assert mes_demandes[0]["idEquipe"] == decor.id_equipe
    assert mes_demandes[0]["idTournoi"] == decor.id_tournoi


def test_une_demande_traitee_n_est_plus_en_attente(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    decor.capitaine.patch(f"/api/demandes/{id_demande}", json={"statutDemande": "REFUSEE"})

    assert decor.joueur.get("/api/moi/demandes").get_json() == []


def test_un_visiteur_n_a_ni_equipes_ni_demandes(app):
    visiteur = app.test_client()

    assert visiteur.get("/api/moi/equipes").status_code == 401
    assert visiteur.get("/api/moi/demandes").status_code == 401
