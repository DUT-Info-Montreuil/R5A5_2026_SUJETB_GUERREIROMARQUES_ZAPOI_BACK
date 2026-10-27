"""
Cycle de vie d'un tournoi (contrat §3 et §5) : création, transitions d'état,
arbre, saisie des résultats — et surtout qui a le droit de faire quoi.
"""

import pytest
from sqlalchemy import text

from project_organizer.utils import database

from .conftest import MOT_DE_PASSE_TEST, PREFIXE_PSEUDO_TEST

JEU_DE_TEST = "test_Jeu à 1 joueur"


# --- Préparation -------------------------------------------------------------

@pytest.fixture
def id_jeu(inscrire):
    """Un jeu à un joueur par équipe : une équipe est complète dès son premier membre.

    Dépend de `inscrire` pour que ce nettoyage passe AVANT celui des comptes :
    un tournoi référence le compte qui l'a créé.
    """
    with database.session() as session:
        identifiant = session.execute(
            text("INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES (:nom, 1) RETURNING id_jeu"),
            {"nom": JEU_DE_TEST},
        ).scalar_one()
        # Une équipe n'est complète que si chaque joueur a un poste (B-08).
        session.execute(
            text("INSERT INTO role_jeu (id_jeu, libelle_role) VALUES (:jeu, 'test_Poste unique')"),
            {"jeu": identifiant},
        )
    yield identifiant
    with database.session() as session:
        session.execute(text("DELETE FROM tournoi WHERE id_jeu = :jeu"), {"jeu": identifiant})
        session.execute(text("DELETE FROM jeu WHERE id_jeu = :jeu"), {"jeu": identifiant})
        session.execute(text("DELETE FROM utilisateur WHERE pseudo LIKE 'test\\_joueur%'"))


@pytest.fixture
def admin(client, inscrire):
    """Le client de test, connecté en administrateur."""
    inscrire("admin")
    with database.session() as session:
        session.execute(
            text("UPDATE utilisateur SET est_administrateur = TRUE WHERE pseudo = :p"),
            {"p": PREFIXE_PSEUDO_TEST + "admin"},
        )
    return client


@pytest.fixture
def joueur(app, inscrire):
    """Un second client, connecté en simple joueur."""
    autre = app.test_client()
    pseudo = PREFIXE_PSEUDO_TEST + "joueur"
    reponse = autre.post(
        "/api/auth/inscription",
        json={"pseudo": pseudo, "email": f"{pseudo}@iut.fr", "motDePasse": MOT_DE_PASSE_TEST},
    )
    assert reponse.status_code == 201
    return autre


def _creer(admin, id_jeu, nombre_equipes=4, nom="test_Coupe"):
    reponse = admin.post("/api/tournois", json={"nomTournoi": nom, "idJeu": id_jeu, "nombreEquipes": nombre_equipes})
    assert reponse.status_code == 201, reponse.get_json()
    return reponse.get_json()["idTournoi"]


def _inscrire_equipes(id_tournoi, completes: int, incompletes: int = 0, sans_poste: int = 0) -> None:
    """Équipes posées directement en base, pour fabriquer vite un état précis.

    completes     un joueur, avec son poste
    incompletes   aucun joueur
    sans_poste    un joueur, mais sans poste attribué : incomplète au sens de B-08
    """
    with database.session() as session:
        id_role = session.execute(
            text("SELECT id_role FROM role_jeu WHERE id_jeu = (SELECT id_jeu FROM tournoi WHERE id_tournoi = :t)"),
            {"t": id_tournoi},
        ).scalar_one()
        for numero in range(completes + incompletes + sans_poste):
            id_equipe = session.execute(
                text("INSERT INTO equipe (id_tournoi, nom_equipe) VALUES (:t, :n) RETURNING id_equipe"),
                {"t": id_tournoi, "n": f"Equipe {numero + 1}"},
            ).scalar_one()
            if completes <= numero < completes + incompletes:
                continue
            id_joueur = session.execute(
                text("INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash) "
                     "VALUES (:p, :e, 'x') RETURNING id_utilisateur"),
                {"p": f"test_joueur{id_equipe}", "e": f"test_joueur{id_equipe}@iut.fr"},
            ).scalar_one()
            session.execute(
                text("INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, est_capitaine, id_role) "
                     "VALUES (:e, :t, :u, TRUE, :r)"),
                {"e": id_equipe, "t": id_tournoi, "u": id_joueur, "r": None if numero >= completes + incompletes else id_role},
            )


def _statut(client, id_tournoi, statut):
    return client.patch(f"/api/tournois/{id_tournoi}", json={"statutTournoi": statut})


def _arbre(client, id_tournoi):
    return client.get(f"/api/tournois/{id_tournoi}/arbre").get_json()


def _jouables(client, id_tournoi):
    return [r for r in _arbre(client, id_tournoi) if r["statutRencontre"] == "JOUABLE"]


def _gagner(client, rencontre, cote="equipeA", **champs):
    corps = {"idVainqueur": rencontre[cote]["idEquipe"], "typeResultat": "NORMAL", **champs}
    return client.patch(f"/api/rencontres/{rencontre['idRencontre']}", json=corps)


def _tournoi_lance(admin, id_jeu, equipes=4):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, equipes)
    assert _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES").status_code == 200
    assert _statut(admin, id_tournoi, "EN_COURS").status_code == 200
    return id_tournoi


# --- Création (B-01) ---------------------------------------------------------

def test_l_administrateur_cree_un_tournoi_inscriptions_ouvertes(admin, id_jeu):
    reponse = admin.post("/api/tournois", json={"nomTournoi": "  test_Coupe  ", "idJeu": id_jeu})

    assert reponse.status_code == 201
    tournoi = reponse.get_json()
    assert tournoi["nomTournoi"] == "test_Coupe"
    assert tournoi["statutTournoi"] == "INSCRIPTIONS_OUVERTES"
    assert tournoi["nombreEquipes"] == 8
    assert tournoi["jeu"]["nomJeu"] == JEU_DE_TEST


def test_un_joueur_ne_peut_pas_creer_de_tournoi(joueur, id_jeu):
    reponse = joueur.post("/api/tournois", json={"nomTournoi": "test_Pirate", "idJeu": id_jeu})

    assert reponse.status_code == 403


def test_un_visiteur_ne_peut_pas_creer_de_tournoi(app, id_jeu):
    reponse = app.test_client().post("/api/tournois", json={"nomTournoi": "test_Pirate", "idJeu": id_jeu})

    assert reponse.status_code == 401


def test_un_jeu_inconnu_donne_422(admin, id_jeu):
    reponse = admin.post("/api/tournois", json={"nomTournoi": "test_Coupe", "idJeu": 999999999})

    assert reponse.status_code == 422


@pytest.mark.parametrize("corps", [
    {"nomTournoi": "   ", "idJeu": 1},
    {"nomTournoi": "test_Coupe", "idJeu": 1, "nombreEquipes": 6},
    {"nomTournoi": "test_Coupe", "idJeu": 1, "statutTournoi": "TERMINE"},
])
def test_une_charge_invalide_donne_400(admin, id_jeu, corps):
    assert admin.post("/api/tournois", json=corps).status_code == 400


# --- Lecture (B-02) ----------------------------------------------------------

def test_le_detail_est_public(app, admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)

    reponse = app.test_client().get(f"/api/tournois/{id_tournoi}")

    assert reponse.status_code == 200
    assert reponse.get_json()["idTournoi"] == id_tournoi


def test_un_tournoi_inexistant_donne_404(client):
    assert client.get("/api/tournois/999999999").status_code == 404
    assert client.get("/api/tournois/999999999/arbre").status_code == 404


def test_les_equipes_du_tournoi_portent_leur_nombre_de_membres(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, completes=1, incompletes=1)

    equipes = admin.get(f"/api/tournois/{id_tournoi}/equipes").get_json()

    assert [e["nombreMembres"] for e in equipes] == [1, 0]


def test_les_jeux_sont_publics(app, id_jeu):
    jeux = app.test_client().get("/api/jeux").get_json()

    assert any(j["idJeu"] == id_jeu for j in jeux)


# --- Modification et transitions (B-03, B-04, B-12) ---------------------------

def test_un_joueur_ne_peut_pas_modifier_un_tournoi(admin, joueur, id_jeu):
    id_tournoi = _creer(admin, id_jeu)

    assert joueur.patch(f"/api/tournois/{id_tournoi}", json={"nomTournoi": "test_Volé"}).status_code == 403
    assert _statut(joueur, id_tournoi, "INSCRIPTIONS_CLOSES").status_code == 403


def test_l_administrateur_renomme_un_tournoi(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)

    reponse = admin.patch(f"/api/tournois/{id_tournoi}", json={"nomTournoi": "test_Nouveau nom"})

    assert reponse.status_code == 200
    assert reponse.get_json()["nomTournoi"] == "test_Nouveau nom"


def test_un_champ_hors_liste_blanche_donne_400(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)

    assert admin.patch(f"/api/tournois/{id_tournoi}", json={"nombreEquipes": 16}).status_code == 400
    assert admin.patch(f"/api/tournois/{id_tournoi}", json={}).status_code == 400


@pytest.mark.parametrize("statut", ["EN_COURS", "TERMINE", "INSCRIPTIONS_OUVERTES"])
def test_une_transition_qui_saute_une_etape_donne_409(admin, id_jeu, statut):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, 4)

    assert _statut(admin, id_tournoi, statut).status_code == 409


def test_on_ne_clot_pas_un_tournoi_de_moins_de_deux_equipes(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, 1)

    assert _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES").status_code == 409


def test_la_cloture_genere_l_arbre_complet(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu, nombre_equipes=8)
    _inscrire_equipes(id_tournoi, 8)

    reponse = _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    assert reponse.status_code == 200
    assert reponse.get_json()["inscriptionsClosesLe"]
    arbre = _arbre(admin, id_tournoi)
    assert [r["tour"] for r in arbre] == [1, 1, 1, 1, 2, 2, 3]
    equipes_placees = {r[c]["idEquipe"] for r in arbre if r["tour"] == 1 for c in ("equipeA", "equipeB")}
    assert len(equipes_placees) == 8
    assert "idRencontreSuivante" not in arbre[-1], "la finale ne mène nulle part"


def test_l_arbre_est_vide_tant_que_les_inscriptions_sont_ouvertes(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)

    assert _arbre(admin, id_tournoi) == []


def test_au_lancement_une_equipe_incomplete_est_forfait(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    # 4 équipes pour 4 places : l'équipe incomplète a forcément un adversaire.
    _inscrire_equipes(id_tournoi, completes=3, incompletes=1)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    assert _statut(admin, id_tournoi, "EN_COURS").status_code == 200

    equipes = {e["nomEquipe"]: e for e in admin.get(f"/api/tournois/{id_tournoi}/equipes").get_json()}
    assert equipes["Equipe 4"]["statutEquipe"] == "ELIMINEE"
    forfait = next(
        r for r in _arbre(admin, id_tournoi)
        if r["tour"] == 1 and "Equipe 4" in (r["equipeA"]["nomEquipe"], r["equipeB"]["nomEquipe"])
    )
    assert forfait["typeResultat"] == "FORFAIT"
    assert forfait["idVainqueur"] != equipes["Equipe 4"]["idEquipe"]


def test_au_lancement_une_equipe_dont_un_joueur_n_a_pas_de_poste_est_forfait(admin, id_jeu):
    """B-08 : cinq joueurs ne suffisent pas, chacun doit avoir un poste."""
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, completes=3, sans_poste=1)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    assert _statut(admin, id_tournoi, "EN_COURS").status_code == 200

    equipes = {e["nomEquipe"]: e for e in admin.get(f"/api/tournois/{id_tournoi}/equipes").get_json()}
    assert equipes["Equipe 4"]["nombreMembres"] == 1
    assert equipes["Equipe 4"]["statutEquipe"] == "ELIMINEE"
    assert all(equipes[f"Equipe {n}"]["statutEquipe"] == "EN_LICE" for n in (1, 2, 3))


def test_on_ne_lance_pas_quand_les_postes_manquent_partout(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, completes=1, sans_poste=2)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    reponse = _statut(admin, id_tournoi, "EN_COURS")

    assert reponse.status_code == 422
    assert "poste" in reponse.get_json()["detail"]


def test_on_ne_lance_pas_sans_deux_equipes_completes(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, completes=1, incompletes=2)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    assert _statut(admin, id_tournoi, "EN_COURS").status_code == 422


# --- Résultats (B-13, B-14, B-15) --------------------------------------------

def test_un_joueur_ne_peut_pas_saisir_un_resultat(admin, joueur, id_jeu):
    id_tournoi = _tournoi_lance(admin, id_jeu)
    rencontre = _jouables(admin, id_tournoi)[0]

    assert _gagner(joueur, rencontre).status_code == 403
    assert _jouables(admin, id_tournoi)[0] == rencontre, "rien n'a été écrit"


def test_pas_de_resultat_avant_le_lancement(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, 4)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")

    assert _gagner(admin, _jouables(admin, id_tournoi)[0]).status_code == 409


def test_le_vainqueur_doit_jouer_la_rencontre(admin, id_jeu):
    id_tournoi = _tournoi_lance(admin, id_jeu)
    premiere, seconde = _jouables(admin, id_tournoi)

    reponse = admin.patch(
        f"/api/rencontres/{premiere['idRencontre']}",
        json={"idVainqueur": seconde["equipeA"]["idEquipe"], "typeResultat": "NORMAL"},
    )

    assert reponse.status_code == 422


def test_une_rencontre_deja_jouee_donne_409(admin, id_jeu):
    id_tournoi = _tournoi_lance(admin, id_jeu)
    rencontre = _jouables(admin, id_tournoi)[0]
    _gagner(admin, rencontre)

    assert _gagner(admin, rencontre, "equipeB").status_code == 409


def test_une_rencontre_en_attente_donne_409(admin, id_jeu):
    id_tournoi = _tournoi_lance(admin, id_jeu)
    finale = _arbre(admin, id_tournoi)[-1]

    reponse = admin.patch(
        f"/api/rencontres/{finale['idRencontre']}", json={"idVainqueur": 1, "typeResultat": "NORMAL"}
    )

    assert reponse.status_code == 409


@pytest.mark.parametrize("champs, code", [
    ({"scoreA": 2}, 400),
    ({"typeResultat": "FORFAIT", "scoreA": 2, "scoreB": 0}, 400),
    ({"scoreA": 0, "scoreB": 3}, 422),
    ({"typeResultat": "QUALIFICATION_DIRECTE"}, 422),
])
def test_un_resultat_incoherent_est_refuse(admin, id_jeu, champs, code):
    id_tournoi = _tournoi_lance(admin, id_jeu)

    assert _gagner(admin, _jouables(admin, id_tournoi)[0], **champs).status_code == code


def test_une_equipe_seule_passe_en_qualification_directe(admin, id_jeu):
    id_tournoi = _creer(admin, id_jeu)
    _inscrire_equipes(id_tournoi, 3)
    _statut(admin, id_tournoi, "INSCRIPTIONS_CLOSES")
    _statut(admin, id_tournoi, "EN_COURS")
    seule = next(r for r in _jouables(admin, id_tournoi) if "equipeB" not in r)

    assert _gagner(admin, seule).status_code == 422, "NORMAL sans adversaire"
    assert _gagner(admin, seule, typeResultat="QUALIFICATION_DIRECTE").status_code == 200


def test_un_tournoi_complet_jusqu_au_vainqueur(admin, id_jeu):
    id_tournoi = _tournoi_lance(admin, id_jeu)
    assert _statut(admin, id_tournoi, "TERMINE").status_code == 409, "la finale n'est pas jouée"

    for demi in _jouables(admin, id_tournoi):
        reponse = _gagner(admin, demi, scoreA=2, scoreB=1)
        assert reponse.status_code == 200
        assert reponse.get_json()["statutRencontre"] == "TERMINE"

    finale = _jouables(admin, id_tournoi)[0]
    assert finale["tour"] == 2
    assert _gagner(admin, finale, "equipeB", typeResultat="FORFAIT").status_code == 200

    reponse = _statut(admin, id_tournoi, "TERMINE")
    assert reponse.status_code == 200
    assert reponse.get_json()["termineLe"]
    statuts = sorted(e["statutEquipe"] for e in admin.get(f"/api/tournois/{id_tournoi}/equipes").get_json())
    assert statuts == ["ELIMINEE", "ELIMINEE", "ELIMINEE", "VAINQUEUR"]


# --- Temps réel (B-19) -------------------------------------------------------

def test_les_abonnes_du_tournoi_recoivent_les_mises_a_jour(app, admin, id_jeu):
    from project_organizer.extensions import socketio

    id_tournoi = _tournoi_lance(admin, id_jeu)
    spectateur = socketio.test_client(app)
    assert spectateur.emit("tournoi:suivre", {"idTournoi": id_tournoi}, callback=True) == {"ok": True}
    spectateur.get_received()

    _gagner(admin, _jouables(admin, id_tournoi)[0])

    recus = spectateur.get_received()
    rencontres = [e["args"][0] for e in recus if e["name"] == "rencontre:maj"]
    assert {r["statutRencontre"] for r in rencontres} >= {"TERMINE"}
    assert len(rencontres) == 2, "la rencontre jouée et la finale qui reçoit le vainqueur"
    spectateur.disconnect()


def test_un_abonnement_sans_identifiant_valide_est_refuse(app):
    from project_organizer.extensions import socketio

    spectateur = socketio.test_client(app)

    assert spectateur.emit("tournoi:suivre", {"idTournoi": True}, callback=True) == {"ok": False}
    spectateur.disconnect()


def test_terminer_un_tournoi_sans_arbre_donne_409_et_non_500(admin, id_jeu):
    """Un tournoi passé EN_COURS directement en base (données de démonstration) n'a pas d'arbre."""
    id_tournoi = _creer(admin, id_jeu)
    with database.session() as session:
        session.execute(
            text("UPDATE tournoi SET statut_tournoi = 'EN_COURS', inscriptions_closes_le = now(), "
                 "demarre_le = now() WHERE id_tournoi = :t"),
            {"t": id_tournoi},
        )

    assert _statut(admin, id_tournoi, "TERMINE").status_code == 409


def test_une_horloge_qui_recule_ne_casse_pas_la_chronologie(fabrique_clients, jeu_a_postes):
    """Machine virtuelle resynchronisée : la base voit `now()` avant `cree_le`. La clôture réussit quand même."""
    from sqlalchemy import text

    from project_organizer.utils import database

    from .outils_equipes import creer_equipe, monter_decor

    decor = monter_decor(fabrique_clients, jeu_a_postes)
    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[0]).status_code == 201
    with database.session() as session:
        session.execute(
            text("UPDATE tournoi SET cree_le = now() + interval '1 hour' WHERE id_tournoi = :t"), {"t": decor.id_tournoi}
        )

    reponse = decor.admin.patch(f"/api/tournois/{decor.id_tournoi}", json={"statutTournoi": "INSCRIPTIONS_CLOSES"})

    assert reponse.status_code == 200, reponse.get_json()
