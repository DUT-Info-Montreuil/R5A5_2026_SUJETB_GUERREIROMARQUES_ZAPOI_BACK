"""
Demandes d'adhésion (contrat §4, B-06, B-07) : un joueur demande, le capitaine
décide. Les demandes sont invisibles de tout autre que ce capitaine (404).

Pour chaque règle d'accès : un test « refusé » et un test « autorisé ».
"""

import pytest

from .outils_equipes import (
    ajouter_membre,
    clore,
    demander,
    equipe_creee,
    lire_equipe,
    monter_decor,
    traiter,
)


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    return monter_decor(fabrique_clients, jeu_a_postes)


def _demandes(client, id_equipe, filtre=""):
    return client.get(f"/api/equipes/{id_equipe}/demandes{filtre}")


# --- Demander à rejoindre (B-06, B-07) -------------------------------------------

def test_un_joueur_demande_a_rejoindre_une_equipe(decor):
    reponse = demander(decor.joueur, decor.id_equipe)

    assert reponse.status_code == 201
    demande = reponse.get_json()
    assert demande["statutDemande"] == "EN_ATTENTE"
    assert demande["idUtilisateur"] == decor.joueur.id_utilisateur
    assert demande["idEquipe"] == decor.id_equipe


def test_un_visiteur_ne_peut_pas_demander(app, decor):
    assert demander(app.test_client(), decor.id_equipe).status_code == 401


def test_une_equipe_inconnue_donne_404(decor):
    assert demander(decor.joueur, 999999999).status_code == 404


def test_une_seule_demande_en_attente_par_equipe(decor):
    demander(decor.joueur, decor.id_equipe)

    assert demander(decor.joueur, decor.id_equipe).status_code == 409


def test_un_joueur_deja_dans_une_equipe_du_tournoi_ne_peut_pas_demander(decor):
    id_bleus = equipe_creee(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[0])

    assert demander(decor.joueur, decor.id_equipe).status_code == 422
    assert demander(decor.capitaine, id_bleus).status_code == 422


def test_pas_de_demande_vers_une_equipe_complete(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    assert demander(decor.autre, decor.id_equipe).status_code == 422


def test_pas_de_demande_une_fois_les_inscriptions_closes(decor):
    equipe_creee(decor.autre, decor.id_tournoi, "Les Verts", decor.postes[0])
    clore(decor.admin, decor.id_tournoi)

    assert demander(decor.joueur, decor.id_equipe).status_code == 409


# --- Consulter les demandes : le capitaine seul ------------------------------------

def test_le_capitaine_consulte_les_demandes_de_son_equipe(decor):
    demander(decor.joueur, decor.id_equipe)

    reponse = _demandes(decor.capitaine, decor.id_equipe)

    assert reponse.status_code == 200
    assert [d["pseudo"] for d in reponse.get_json()] == ["test_joueur"]


def test_le_filtre_par_statut(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    traiter(decor.capitaine, id_demande, "REFUSEE")
    demander(decor.autre, decor.id_equipe)

    en_attente = _demandes(decor.capitaine, decor.id_equipe, "?statut=EN_ATTENTE").get_json()
    historique = _demandes(decor.capitaine, decor.id_equipe).get_json()

    assert [d["pseudo"] for d in en_attente] == ["test_autre"]
    assert len(historique) == 2
    assert _demandes(decor.capitaine, decor.id_equipe, "?statut=PERDUE").status_code == 400


def test_les_demandes_sont_invisibles_d_un_membre_simple(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    assert _demandes(decor.joueur, decor.id_equipe).status_code == 404


def test_les_demandes_sont_invisibles_d_un_joueur_exterieur(decor):
    demander(decor.joueur, decor.id_equipe)

    assert _demandes(decor.autre, decor.id_equipe).status_code == 404


def test_les_demandes_sont_invisibles_de_l_administrateur(decor):
    demander(decor.joueur, decor.id_equipe)

    assert _demandes(decor.admin, decor.id_equipe).status_code == 404


def test_un_visiteur_ne_consulte_pas_les_demandes(app, decor):
    assert _demandes(app.test_client(), decor.id_equipe).status_code == 401


# --- Accepter ou refuser (B-06) ------------------------------------------------------

def test_le_capitaine_accepte_et_le_joueur_entre_dans_l_equipe(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    reponse = traiter(decor.capitaine, id_demande, "ACCEPTEE")

    assert reponse.status_code == 200
    assert reponse.get_json()["statutDemande"] == "ACCEPTEE"
    assert reponse.get_json()["traiteLe"]
    membres = lire_equipe(decor.capitaine, decor.id_equipe)["membres"]
    nouveau = next(m for m in membres if m["idUtilisateur"] == decor.joueur.id_utilisateur)
    assert nouveau["estCapitaine"] is False
    assert "role" not in nouveau


def test_le_capitaine_refuse_et_le_joueur_peut_redemander(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    assert traiter(decor.capitaine, id_demande, "REFUSEE").status_code == 200
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 1
    assert demander(decor.joueur, decor.id_equipe).status_code == 201


def test_un_joueur_ne_traite_pas_sa_propre_demande(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    assert traiter(decor.joueur, id_demande, "ACCEPTEE").status_code == 404
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 1


def test_le_capitaine_d_une_autre_equipe_ne_traite_pas_la_demande(decor):
    id_bleus = equipe_creee(decor.autre, decor.id_tournoi, "Les Bleus", decor.postes[0])
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    assert traiter(decor.autre, id_demande, "ACCEPTEE").status_code == 404
    assert len(lire_equipe(decor.capitaine, id_bleus)["membres"]) == 1


def test_l_administrateur_ne_traite_pas_une_demande(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    assert traiter(decor.admin, id_demande, "ACCEPTEE").status_code == 404


def test_un_visiteur_ne_traite_pas_une_demande(app, decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    assert traiter(app.test_client(), id_demande, "ACCEPTEE").status_code == 401


def test_une_demande_inconnue_donne_404(decor):
    assert traiter(decor.capitaine, 999999999, "ACCEPTEE").status_code == 404


def test_une_demande_ne_se_traite_qu_une_fois(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    traiter(decor.capitaine, id_demande, "REFUSEE")

    assert traiter(decor.capitaine, id_demande, "ACCEPTEE").status_code == 409
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 1


def test_un_statut_hors_de_la_liste_donne_400(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]

    for statut in ("EN_ATTENTE", "ANNULEE", "VAINQUEUR"):
        assert traiter(decor.capitaine, id_demande, statut).status_code == 400


def test_accepter_un_joueur_entre_temps_pris_ailleurs_donne_422(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    equipe_creee(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[1])

    assert traiter(decor.capitaine, id_demande, "ACCEPTEE").status_code == 422


def test_accepter_dans_une_equipe_devenue_complete_donne_422(decor):
    premiere = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    seconde = demander(decor.autre, decor.id_equipe).get_json()["idDemande"]
    assert traiter(decor.capitaine, premiere, "ACCEPTEE").status_code == 200

    assert traiter(decor.capitaine, seconde, "ACCEPTEE").status_code == 422
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 2


def test_on_ne_traite_plus_de_demande_apres_la_cloture(decor):
    id_demande = demander(decor.joueur, decor.id_equipe).get_json()["idDemande"]
    equipe_creee(decor.autre, decor.id_tournoi, "Les Verts", decor.postes[0])
    clore(decor.admin, decor.id_tournoi)

    assert traiter(decor.capitaine, id_demande, "ACCEPTEE").status_code == 409
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 1