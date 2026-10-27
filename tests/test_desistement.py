"""
Désistement du capitaine (contrat §4) : il dissout son équipe tant que les
inscriptions sont ouvertes. Les membres partent avec elle, la place est libérée.

Pour chaque règle d'accès : un test « refusé » et un test « autorisé ».
"""

import pytest

from project_organizer.sockets import diffusion

from .outils_equipes import (
    ajouter_membre,
    clore,
    creer_equipe,
    demander,
    lire_equipe,
    monter_decor,
    poster,
)


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    return monter_decor(fabrique_clients, jeu_a_postes)


def _dissoudre(client, id_equipe: int):
    return client.delete(f"/api/equipes/{id_equipe}")


def test_le_capitaine_dissout_son_equipe(decor):
    reponse = _dissoudre(decor.capitaine, decor.id_equipe)

    assert reponse.status_code == 204
    assert decor.capitaine.get(f"/api/equipes/{decor.id_equipe}").status_code == 404
    assert decor.capitaine.get("/api/moi/equipes").get_json() == []


def test_un_membre_ne_dissout_pas_l_equipe(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _dissoudre(decor.joueur, decor.id_equipe)

    assert reponse.status_code == 403
    assert lire_equipe(decor.capitaine, decor.id_equipe)["nomEquipe"] == "Les Rouges"


def test_un_joueur_exterieur_ne_dissout_pas_l_equipe(decor):
    assert _dissoudre(decor.autre, decor.id_equipe).status_code == 403


def test_un_visiteur_ne_dissout_pas_l_equipe(app, decor):
    assert _dissoudre(app.test_client(), decor.id_equipe).status_code == 401


def test_l_administrateur_n_est_pas_le_capitaine_donc_ne_dissout_pas(decor):
    """L'administrateur dispose de la disqualification, pas du désistement d'un autre."""
    assert _dissoudre(decor.admin, decor.id_equipe).status_code == 403


def test_une_equipe_inconnue_donne_404(decor):
    assert _dissoudre(decor.capitaine, 999999).status_code == 404


def test_apres_la_cloture_l_equipe_ne_peut_plus_se_desister(decor):
    # Il faut deux équipes pour clore les inscriptions.
    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[0]).status_code == 201
    clore(decor.admin, decor.id_tournoi)

    reponse = _dissoudre(decor.capitaine, decor.id_equipe)

    assert reponse.status_code == 409
    assert decor.capitaine.get(f"/api/equipes/{decor.id_equipe}").status_code == 200


def test_les_demandes_en_attente_partent_avec_l_equipe(decor):
    reponse = demander(decor.autre, decor.id_equipe)
    assert reponse.status_code == 201, reponse.get_json()

    assert _dissoudre(decor.capitaine, decor.id_equipe).status_code == 204

    assert decor.autre.get("/api/moi/demandes").get_json() == []


def test_les_membres_partent_avec_l_equipe(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    assert _dissoudre(decor.capitaine, decor.id_equipe).status_code == 204

    assert decor.joueur.get("/api/moi/equipes").get_json() == []


def test_les_membres_peuvent_refaire_une_equipe_apres_la_dissolution(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    _dissoudre(decor.capitaine, decor.id_equipe)

    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Verts", decor.postes[0]).status_code == 201
    # Le nom « Les Rouges » est de nouveau libre.
    assert creer_equipe(decor.capitaine, decor.id_tournoi, "Les Rouges", decor.postes[1]).status_code == 201


def test_les_messages_disparaissent_avec_l_equipe(decor):
    assert poster(decor.capitaine, decor.id_equipe, "On se retrouve ce soir ?").status_code == 201

    _dissoudre(decor.capitaine, decor.id_equipe)

    assert decor.capitaine.get(f"/api/equipes/{decor.id_equipe}/messages").status_code == 404


def test_chaque_membre_est_prevenu_que_son_espace_se_ferme(decor, monkeypatch):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    appels = []
    monkeypatch.setattr(diffusion, "acces_revoque", lambda id_equipe, motif, ids: appels.append((id_equipe, motif, sorted(ids))))

    _dissoudre(decor.capitaine, decor.id_equipe)

    attendus = sorted([decor.capitaine.id_utilisateur, decor.joueur.id_utilisateur])
    assert appels == [(decor.id_equipe, "dissolution", attendus)]


def test_la_dissolution_est_journalisee(decor, caplog):
    with caplog.at_level("INFO"):
        _dissoudre(decor.capitaine, decor.id_equipe)

    assert any(r.getMessage() == "Équipe dissoute par son capitaine" for r in caplog.records)
