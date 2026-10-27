"""GET /api/tournois (contrat §3, B-02) : public, filtrable, ordonné."""

import pytest
from sqlalchemy import text

from project_organizer.utils import database

PREFIXE = "test_"


@pytest.fixture
def tournois_de_test():
    """Deux tournois isolés du reste de la base, supprimés après le test."""
    with database.session() as session:
        id_createur = session.execute(
            text("INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash) "
                 "VALUES ('test_createur', 'test_createur@iut.fr', 'x') RETURNING id_utilisateur")
        ).scalar_one()
        id_jeu = session.execute(
            text("INSERT INTO jeu (nom_jeu) VALUES ('test_Jeu') RETURNING id_jeu")
        ).scalar_one()
        session.execute(
            text("INSERT INTO tournoi (nom_tournoi, id_jeu, statut_tournoi, cree_par) VALUES "
                 "('test_Coupe ouverte', :jeu, 'INSCRIPTIONS_OUVERTES', :createur), "
                 "('test_Coupe finie', :jeu, 'TERMINE', :createur)"),
            {"jeu": id_jeu, "createur": id_createur},
        )
        session.execute(
            text("INSERT INTO equipe (id_tournoi, nom_equipe) "
                 "SELECT id_tournoi, 'Hiboux' FROM tournoi WHERE nom_tournoi = 'test_Coupe ouverte'")
        )
    yield
    with database.session() as session:
        session.execute(text("DELETE FROM tournoi WHERE nom_tournoi LIKE 'test\\_%'"))
        session.execute(text("DELETE FROM jeu WHERE nom_jeu = 'test_Jeu'"))
        session.execute(text("DELETE FROM utilisateur WHERE pseudo = 'test_createur'"))


def _nos_tournois(reponse):
    return [t for t in reponse.get_json() if t["nomTournoi"].startswith(PREFIXE)]


def test_la_liste_est_publique(client, tournois_de_test):
    client.delete_cookie("jeton")

    reponse = client.get("/api/tournois")

    assert reponse.status_code == 200
    assert len(_nos_tournois(reponse)) == 2


def test_chaque_tournoi_porte_son_jeu_et_son_nombre_d_equipes(client, tournois_de_test):
    ouvert = next(t for t in _nos_tournois(client.get("/api/tournois")) if t["statutTournoi"] == "INSCRIPTIONS_OUVERTES")

    assert ouvert["jeu"]["nomJeu"] == "test_Jeu"
    assert ouvert["nombreEquipesInscrites"] == 1
    assert ouvert["nombreEquipes"] == 8


def test_le_filtre_par_statut(client, tournois_de_test):
    reponse = client.get("/api/tournois?statut=TERMINE")

    assert [t["nomTournoi"] for t in _nos_tournois(reponse)] == ["test_Coupe finie"]


def test_la_recherche_ignore_la_casse(client, tournois_de_test):
    reponse = client.get("/api/tournois?recherche=COUPE OUVERTE")

    assert [t["nomTournoi"] for t in _nos_tournois(reponse)] == ["test_Coupe ouverte"]


def test_un_statut_inconnu_donne_400(client):
    assert client.get("/api/tournois?statut=PERDU").status_code == 400
