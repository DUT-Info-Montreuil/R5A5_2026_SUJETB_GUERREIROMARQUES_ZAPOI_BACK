"""
Un administrateur organise les tournois, il n'y joue pas (contrat §4) : il ne peut
ni créer d'équipe ni demander à en rejoindre. Pour participer, il utilise un compte joueur.

Pour chaque règle d'accès : un test « refusé » et un test « autorisé ».
"""

import pytest

from .outils_equipes import creer_equipe, demander, monter_decor


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    return monter_decor(fabrique_clients, jeu_a_postes)


def test_un_administrateur_ne_cree_pas_d_equipe(decor):
    reponse = creer_equipe(decor.admin, decor.id_tournoi, "Les Juges", decor.postes[0])

    assert reponse.status_code == 403
    assert decor.admin.get("/api/moi/equipes").get_json() == []


def test_un_administrateur_ne_demande_pas_a_rejoindre_une_equipe(decor):
    reponse = demander(decor.admin, decor.id_equipe)

    assert reponse.status_code == 403
    assert decor.admin.get("/api/moi/demandes").get_json() == []


def test_le_refus_d_un_administrateur_laisse_une_trace(decor, caplog):
    with caplog.at_level("WARNING"):
        creer_equipe(decor.admin, decor.id_tournoi, "Les Juges", decor.postes[0])

    assert any("administrateur a tenté de participer" in r.getMessage() for r in caplog.records)


def test_un_joueur_garde_le_droit_de_creer_et_de_demander(decor):
    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[0]).status_code == 201
    assert demander(decor.autre, decor.id_equipe).status_code == 201
