"""
Équipes (contrat §4, B-05 à B-11, B-15) : création, lecture, renommage,
disqualification, postes, capitanat, exclusion.

Pour chaque règle d'accès : un test « refusé » et un test « autorisé ».
"""

import pytest

from .outils_equipes import (
    ajouter_membre,
    ajouter_membre_avec_poste,
    changer_statut,
    clore,
    creer_equipe,
    creer_tournoi,
    equipe_creee,
    lire_equipe,
    monter_decor,
)


@pytest.fixture
def decor(fabrique_clients, jeu_a_postes):
    return monter_decor(fabrique_clients, jeu_a_postes)


# --- Création (B-05, B-07) -----------------------------------------------------

def test_un_joueur_cree_une_equipe_et_devient_capitaine(decor):
    reponse = creer_equipe(decor.joueur, decor.id_tournoi, "  Les Bleus  ", decor.postes[1])

    assert reponse.status_code == 201
    equipe = reponse.get_json()
    assert equipe["nomEquipe"] == "Les Bleus"
    assert equipe["statutEquipe"] == "EN_LICE"
    assert len(equipe["membres"]) == 1
    createur = equipe["membres"][0]
    assert createur["idUtilisateur"] == decor.joueur.id_utilisateur
    assert createur["estCapitaine"] is True
    assert createur["role"]["idRole"] == decor.postes[1]


def test_un_visiteur_ne_peut_pas_creer_d_equipe(app, decor):
    reponse = creer_equipe(app.test_client(), decor.id_tournoi, "Pirates", decor.postes[1])

    assert reponse.status_code == 401


def test_un_joueur_n_a_qu_une_equipe_par_tournoi(decor):
    reponse = creer_equipe(decor.capitaine, decor.id_tournoi, "Doublon", decor.postes[1])

    assert reponse.status_code == 422


def test_un_joueur_peut_avoir_une_equipe_dans_chaque_tournoi(decor):
    autre_tournoi = creer_tournoi(decor.admin, decor.id_jeu, nom="test_Autre coupe")

    assert creer_equipe(decor.capitaine, autre_tournoi, "Les Rouges bis", decor.postes[0]).status_code == 201


def test_le_poste_doit_appartenir_au_jeu_du_tournoi(decor):
    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Bleus", decor.poste_etranger).status_code == 422
    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Bleus", 999999999).status_code == 422


def test_un_nom_deja_pris_donne_409_sans_tenir_compte_de_la_casse(decor):
    reponse = creer_equipe(decor.joueur, decor.id_tournoi, "LES ROUGES", decor.postes[1])

    assert reponse.status_code == 409


def test_pas_de_creation_une_fois_les_inscriptions_closes(decor):
    equipe_creee(decor.autre, decor.id_tournoi, "Les Verts", decor.postes[0])
    clore(decor.admin, decor.id_tournoi)

    assert creer_equipe(decor.joueur, decor.id_tournoi, "Trop tard", decor.postes[1]).status_code == 409


def test_un_tournoi_complet_refuse_une_equipe_de_plus(fabrique_clients, jeu_a_postes):
    admin = fabrique_clients("admin", administrateur=True)
    id_tournoi = creer_tournoi(admin, jeu_a_postes["idJeu"], nombre_equipes=2)
    poste = jeu_a_postes["postes"][0]
    equipe_creee(fabrique_clients("un"), id_tournoi, "Une", poste)
    equipe_creee(fabrique_clients("deux"), id_tournoi, "Deux", poste)

    assert creer_equipe(fabrique_clients("trois"), id_tournoi, "Trois", poste).status_code == 409


def test_un_tournoi_inconnu_donne_404(decor):
    assert creer_equipe(decor.joueur, 999999999, "Fantôme", decor.postes[0]).status_code == 404


# --- Lecture (B-02) ------------------------------------------------------------

def test_une_equipe_est_publique(app, decor):
    reponse = app.test_client().get(f"/api/equipes/{decor.id_equipe}")

    assert reponse.status_code == 200
    equipe = reponse.get_json()
    assert equipe["nomEquipe"] == "Les Rouges"
    assert equipe["idTournoi"] == decor.id_tournoi
    # Un pseudo est public, jamais une adresse e-mail.
    assert "email" not in equipe["membres"][0]


def test_une_equipe_inconnue_donne_404(client):
    assert client.get("/api/equipes/999999999").status_code == 404


def test_les_postes_d_un_jeu_sont_publics(app, decor):
    reponse = app.test_client().get(f"/api/jeux/{decor.id_jeu}/roles")

    assert reponse.status_code == 200
    assert [poste["idRole"] for poste in reponse.get_json()] == decor.postes
    assert app.test_client().get("/api/jeux/999999999/roles").status_code == 404


# --- Renommage (B-09, B-10) ----------------------------------------------------

def test_le_capitaine_renomme_son_equipe(decor):
    reponse = decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Les Pourpres"})

    assert reponse.status_code == 200
    assert reponse.get_json()["nomEquipe"] == "Les Pourpres"


def test_un_membre_qui_n_est_pas_capitaine_ne_renomme_pas(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = decor.joueur.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Coup d'état"})

    assert reponse.status_code == 403
    assert lire_equipe(decor.capitaine, decor.id_equipe)["nomEquipe"] == "Les Rouges"


def test_un_joueur_exterieur_ne_renomme_pas(decor):
    assert decor.autre.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Volée"}).status_code == 403


def test_un_visiteur_ne_renomme_pas(app, decor):
    assert app.test_client().patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Volée"}).status_code == 401


def test_renommer_vers_un_nom_pris_donne_409(decor):
    equipe_creee(decor.joueur, decor.id_tournoi, "Les Bleus", decor.postes[0])

    reponse = decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Les Bleus"})

    assert reponse.status_code == 409


def test_une_requete_vide_ou_au_champ_inconnu_donne_400(decor):
    assert decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={}).status_code == 400
    assert decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"scoreTotal": 99}).status_code == 400
    assert decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "   "}).status_code == 400


# --- Liste blanche de champs par rôle (contrat §1.4, B-10) ------------------------

def test_le_capitaine_ne_peut_pas_modifier_le_statut_de_son_equipe(decor):
    """Sans la liste blanche, un capitaine gagnerait le tournoi tout seul."""
    reponse = decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"statutEquipe": "VAINQUEUR"})
    assert reponse.status_code == 400

    reponse = decor.capitaine.patch(
        f"/api/equipes/{decor.id_equipe}", json={"statutEquipe": "DISQUALIFIEE", "motifSortie": "Auto-sabordage"}
    )
    assert reponse.status_code == 400
    assert lire_equipe(decor.capitaine, decor.id_equipe)["statutEquipe"] == "EN_LICE"


def test_une_requete_refusee_ne_s_applique_pas_a_moitie(decor):
    reponse = decor.capitaine.patch(
        f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Renommée", "statutEquipe": "DISQUALIFIEE"}
    )

    assert reponse.status_code == 400
    assert lire_equipe(decor.capitaine, decor.id_equipe)["nomEquipe"] == "Les Rouges"


def test_l_administrateur_ne_renomme_pas_une_equipe(decor):
    reponse = decor.admin.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Imposée"})

    assert reponse.status_code == 400


# --- Disqualification (B-15) ---------------------------------------------------

@pytest.fixture
def duel(fabrique_clients, jeu_a_postes):
    """Un tournoi à 2 équipes complètes, lancé : une finale jouable entre « Alpha » et « Beta »."""
    admin = fabrique_clients("admin", administrateur=True)
    poste = jeu_a_postes["postes"]
    id_tournoi = creer_tournoi(admin, jeu_a_postes["idJeu"], nombre_equipes=2)
    capitaine_alpha, capitaine_beta = fabrique_clients("cap_alpha"), fabrique_clients("cap_beta")
    id_alpha = equipe_creee(capitaine_alpha, id_tournoi, "Alpha", poste[0])
    id_beta = equipe_creee(capitaine_beta, id_tournoi, "Beta", poste[0])
    ajouter_membre_avec_poste(capitaine_alpha, fabrique_clients("mem_alpha"), id_alpha, poste[1])
    ajouter_membre_avec_poste(capitaine_beta, fabrique_clients("mem_beta"), id_beta, poste[1])
    clore(admin, id_tournoi)
    assert changer_statut(admin, id_tournoi, "EN_COURS").status_code == 200
    return type("Duel", (), {
        "admin": admin, "capitaine_alpha": capitaine_alpha, "capitaine_beta": capitaine_beta,
        "id_tournoi": id_tournoi, "id_alpha": id_alpha, "id_beta": id_beta,
    })


def test_l_administrateur_disqualifie_une_equipe_et_qualifie_son_adversaire(duel):
    reponse = duel.admin.patch(
        f"/api/equipes/{duel.id_alpha}", json={"statutEquipe": "DISQUALIFIEE", "motifSortie": "Comportement inapproprié"}
    )

    assert reponse.status_code == 200
    assert reponse.get_json()["statutEquipe"] == "DISQUALIFIEE"
    assert reponse.get_json()["motifSortie"] == "Comportement inapproprié"
    finale = duel.admin.get(f"/api/tournois/{duel.id_tournoi}/arbre").get_json()[0]
    assert finale["statutRencontre"] == "TERMINE"
    assert finale["typeResultat"] == "FORFAIT"
    assert finale["idVainqueur"] == duel.id_beta
    # Le tournoi peut alors se terminer, et Beta en est le vainqueur.
    assert changer_statut(duel.admin, duel.id_tournoi, "TERMINE").status_code == 200
    assert lire_equipe(duel.admin, duel.id_beta)["statutEquipe"] == "VAINQUEUR"
    assert lire_equipe(duel.admin, duel.id_alpha)["statutEquipe"] == "DISQUALIFIEE"


def test_un_capitaine_ne_disqualifie_pas_l_equipe_adverse(duel):
    reponse = duel.capitaine_alpha.patch(f"/api/equipes/{duel.id_beta}", json={"statutEquipe": "DISQUALIFIEE"})

    assert reponse.status_code == 403
    assert lire_equipe(duel.admin, duel.id_beta)["statutEquipe"] == "EN_LICE"


def test_un_visiteur_ne_disqualifie_pas(app, duel):
    reponse = app.test_client().patch(f"/api/equipes/{duel.id_beta}", json={"statutEquipe": "DISQUALIFIEE"})

    assert reponse.status_code == 401


def test_on_ne_disqualifie_qu_un_tournoi_en_cours(decor):
    reponse = decor.admin.patch(f"/api/equipes/{decor.id_equipe}", json={"statutEquipe": "DISQUALIFIEE"})

    assert reponse.status_code == 409


def test_une_equipe_deja_disqualifiee_donne_409(duel):
    duel.admin.patch(f"/api/equipes/{duel.id_alpha}", json={"statutEquipe": "DISQUALIFIEE"})

    assert duel.admin.patch(f"/api/equipes/{duel.id_alpha}", json={"statutEquipe": "DISQUALIFIEE"}).status_code == 409


def test_un_motif_sans_statut_donne_400(duel):
    assert duel.admin.patch(f"/api/equipes/{duel.id_alpha}", json={"motifSortie": "Sans suite"}).status_code == 400


# --- Postes (B-08) -------------------------------------------------------------

def _poste(client, id_equipe, id_membre, id_role):
    return client.patch(f"/api/equipes/{id_equipe}/membres/{id_membre}", json={"idRole": id_role})


def test_le_capitaine_attribue_un_poste_a_un_membre(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _poste(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur, decor.postes[1])

    assert reponse.status_code == 200
    membre = next(m for m in reponse.get_json()["membres"] if m["idUtilisateur"] == decor.joueur.id_utilisateur)
    assert membre["role"]["idRole"] == decor.postes[1]


def test_un_poste_deja_tenu_donne_422(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _poste(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur, decor.postes[0])

    assert reponse.status_code == 422


def test_un_poste_d_un_autre_jeu_donne_422(decor):
    reponse = _poste(decor.capitaine, decor.id_equipe, decor.capitaine.id_utilisateur, decor.poste_etranger)

    assert reponse.status_code == 422


def test_un_membre_ne_s_attribue_pas_de_poste_lui_meme(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _poste(decor.joueur, decor.id_equipe, decor.joueur.id_utilisateur, decor.postes[2])

    assert reponse.status_code == 403


def test_un_joueur_exterieur_ne_touche_pas_aux_postes(decor):
    reponse = _poste(decor.autre, decor.id_equipe, decor.capitaine.id_utilisateur, decor.postes[2])

    assert reponse.status_code == 403


def test_un_visiteur_ne_touche_pas_aux_postes(app, decor):
    reponse = _poste(app.test_client(), decor.id_equipe, decor.capitaine.id_utilisateur, decor.postes[2])

    assert reponse.status_code == 401


def test_l_administrateur_ne_touche_pas_a_la_composition(decor):
    """B-10 : seul le capitaine touche à la composition, personne d'autre."""
    reponse = _poste(decor.admin, decor.id_equipe, decor.capitaine.id_utilisateur, decor.postes[2])

    assert reponse.status_code == 403


def test_un_poste_pour_un_joueur_qui_n_est_pas_membre_donne_404(decor):
    assert _poste(decor.capitaine, decor.id_equipe, decor.autre.id_utilisateur, decor.postes[1]).status_code == 404


def test_les_postes_sont_figes_apres_la_cloture(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    equipe_creee(decor.autre, decor.id_tournoi, "Les Verts", decor.postes[0])
    clore(decor.admin, decor.id_tournoi)

    reponse = _poste(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur, decor.postes[1])

    assert reponse.status_code == 409


def test_une_requete_vide_ou_au_champ_inconnu_sur_un_membre_donne_400(decor):
    chemin = f"/api/equipes/{decor.id_equipe}/membres/{decor.capitaine.id_utilisateur}"

    assert decor.capitaine.patch(chemin, json={}).status_code == 400
    assert decor.capitaine.patch(chemin, json={"estAdministrateur": True}).status_code == 400


# --- Passation du capitanat (B-09) ---------------------------------------------

def _passer_la_main(client, id_equipe, id_membre):
    return client.patch(f"/api/equipes/{id_equipe}/membres/{id_membre}", json={"estCapitaine": True})


def test_le_capitaine_passe_la_main(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _passer_la_main(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur)

    assert reponse.status_code == 200
    capitaines = [m["idUtilisateur"] for m in reponse.get_json()["membres"] if m["estCapitaine"]]
    assert capitaines == [decor.joueur.id_utilisateur]


def test_l_ancien_capitaine_perd_ses_droits_le_nouveau_les_recoit(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    _passer_la_main(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur)

    ancien = decor.capitaine.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Reprise de volée"})
    nouveau = decor.joueur.patch(f"/api/equipes/{decor.id_equipe}", json={"nomEquipe": "Nouvelle ère"})

    assert ancien.status_code == 403
    assert nouveau.status_code == 200


def test_un_membre_ne_prend_pas_le_capitanat(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _passer_la_main(decor.joueur, decor.id_equipe, decor.joueur.id_utilisateur)

    assert reponse.status_code == 403
    assert lire_equipe(decor.capitaine, decor.id_equipe)["membres"][0]["estCapitaine"] is True


def test_le_capitanat_se_transmet_il_ne_se_retire_pas(decor):
    chemin = f"/api/equipes/{decor.id_equipe}/membres/{decor.capitaine.id_utilisateur}"

    assert decor.capitaine.patch(chemin, json={"estCapitaine": False}).status_code == 400
    assert _passer_la_main(decor.capitaine, decor.id_equipe, decor.capitaine.id_utilisateur).status_code == 422


# --- Exclusion et départ (B-06, B-09, B-11) ----------------------------------------

def _retirer(client, id_equipe, id_membre):
    return client.delete(f"/api/equipes/{id_equipe}/membres/{id_membre}")


def test_le_capitaine_exclut_un_membre(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    reponse = _retirer(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur)

    assert reponse.status_code == 204
    assert [m["idUtilisateur"] for m in lire_equipe(decor.capitaine, decor.id_equipe)["membres"]] == [
        decor.capitaine.id_utilisateur
    ]


def test_un_membre_quitte_son_equipe(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    assert _retirer(decor.joueur, decor.id_equipe, decor.joueur.id_utilisateur).status_code == 204
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 1


def test_un_membre_n_exclut_pas_un_autre_membre(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)

    assert _retirer(decor.joueur, decor.id_equipe, decor.capitaine.id_utilisateur).status_code == 403
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 2


def test_un_joueur_exterieur_n_exclut_personne(decor):
    assert _retirer(decor.autre, decor.id_equipe, decor.capitaine.id_utilisateur).status_code == 403


def test_un_visiteur_n_exclut_personne(app, decor):
    assert _retirer(app.test_client(), decor.id_equipe, decor.capitaine.id_utilisateur).status_code == 401


def test_le_capitaine_ne_peut_pas_partir_sans_passer_la_main(decor):
    assert _retirer(decor.capitaine, decor.id_equipe, decor.capitaine.id_utilisateur).status_code == 422


def test_exclure_un_joueur_qui_n_est_pas_membre_donne_404(decor):
    assert _retirer(decor.capitaine, decor.id_equipe, decor.autre.id_utilisateur).status_code == 404


def test_la_composition_est_figee_apres_la_cloture(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    equipe_creee(decor.autre, decor.id_tournoi, "Les Verts", decor.postes[0])
    clore(decor.admin, decor.id_tournoi)

    assert _retirer(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur).status_code == 409
    assert _retirer(decor.joueur, decor.id_equipe, decor.joueur.id_utilisateur).status_code == 409
    assert len(lire_equipe(decor.capitaine, decor.id_equipe)["membres"]) == 2


def test_un_joueur_exclu_peut_creer_une_autre_equipe(decor):
    ajouter_membre(decor.capitaine, decor.joueur, decor.id_equipe)
    _retirer(decor.capitaine, decor.id_equipe, decor.joueur.id_utilisateur)

    assert creer_equipe(decor.joueur, decor.id_tournoi, "Les Exilés", decor.postes[1]).status_code == 201