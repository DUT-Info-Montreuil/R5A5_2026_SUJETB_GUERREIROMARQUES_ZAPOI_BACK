"""Logique de l'arbre (B-12, B-14), sans base de données."""

from dataclasses import dataclass

from project_organizer.services import arbre
from project_organizer.services.arbre import Arbre


@dataclass
class R:
    """Rencontre minimale : les attributs dont l'arbre a besoin."""

    id_rencontre: int
    tour: int
    position: int
    id_equipe_a: int | None = None
    id_equipe_b: int | None = None
    id_vainqueur: int | None = None
    statut_rencontre: str = "EN_ATTENTE"
    type_resultat: str | None = None
    score_a: int | None = None
    score_b: int | None = None
    valide_le: object = None
    id_rencontre_suivante: int | None = None
    emplacement_suivant: str | None = None


def _arbre_de_8(equipes: list[int]) -> Arbre:
    """Reproduit ce que fait le service : ids attribués dans l'ordre de création."""
    ids: dict[tuple[int, int], int] = {}
    rencontres = []
    for numero, place in enumerate(arbre.places(8, equipes), start=1):
        r = R(numero, place.tour, place.position, place.id_equipe_a, place.id_equipe_b)
        if place.tour < 3:
            tour, position, cote = arbre.suite_de(place.tour, place.position)
            r.id_rencontre_suivante, r.emplacement_suivant = ids[(tour, position)], cote
        ids[(place.tour, place.position)] = numero
        rencontres.append(r)
    resultat = Arbre(rencontres, {e: "EN_LICE" for e in equipes})
    resultat.actualiser_statuts()
    return resultat


def _rencontre(a: Arbre, tour: int, position: int) -> R:
    return next(r for r in a.rencontres if (r.tour, r.position) == (tour, position))


def test_huit_equipes_donnent_sept_rencontres():
    places = arbre.places(8, list(range(1, 9)))

    assert [p.tour for p in places] == [3, 2, 2, 1, 1, 1, 1]
    assert places[0].tour == 3, "la finale est créée en premier"


def test_chaque_rencontre_alimente_la_bonne_place():
    assert arbre.suite_de(1, 1) == (2, 1, "A")
    assert arbre.suite_de(1, 2) == (2, 1, "B")
    assert arbre.suite_de(1, 3) == (2, 2, "A")
    assert arbre.suite_de(2, 2) == (3, 1, "B")


def test_les_equipes_remplissent_les_cotes_a_avant_les_cotes_b():
    premier_tour = [p for p in arbre.places(8, [1, 2, 3, 4, 5]) if p.tour == 1]

    assert [(p.id_equipe_a, p.id_equipe_b) for p in premier_tour] == [(1, 5), (2, None), (3, None), (4, None)]


def test_un_arbre_complet_ouvre_seulement_le_premier_tour():
    a = _arbre_de_8(list(range(1, 9)))

    assert [r.statut_rencontre for r in a.rencontres if r.tour == 1] == ["JOUABLE"] * 4
    assert [r.statut_rencontre for r in a.rencontres if r.tour > 1] == ["EN_ATTENTE"] * 3


def test_une_equipe_sans_adversaire_est_jouable_pour_une_qualification_directe():
    a = _arbre_de_8([1, 2, 3, 4, 5])

    assert _rencontre(a, 1, 2).statut_rencontre == "JOUABLE"


def test_une_rencontre_sans_aucune_equipe_reste_en_attente_et_rend_son_cote_mort():
    a = _arbre_de_8([1, 2, 3])
    vide = _rencontre(a, 1, 4)

    assert vide.statut_rencontre == "EN_ATTENTE"
    assert a.est_morte(vide)
    assert a.emplacement_mort(_rencontre(a, 2, 2), "B")


def test_le_vainqueur_monte_et_le_perdant_est_elimine():
    a = _arbre_de_8(list(range(1, 9)))
    quart = _rencontre(a, 1, 2)

    perdant = a.enregistrer_resultat(quart, quart.id_equipe_b, "NORMAL", "maintenant", 1, 2)
    a.actualiser_statuts()

    assert perdant == quart.id_equipe_a
    assert a.statuts_equipes[perdant] == "ELIMINEE"
    assert _rencontre(a, 2, 1).id_equipe_b == quart.id_equipe_b
    assert _rencontre(a, 2, 1).statut_rencontre == "EN_ATTENTE", "l'autre quart n'est pas joué"


def test_la_demi_devient_jouable_quand_ses_deux_quarts_sont_joues():
    a = _arbre_de_8(list(range(1, 9)))
    for position in (1, 2):
        quart = _rencontre(a, 1, position)
        a.enregistrer_resultat(quart, quart.id_equipe_a, "FORFAIT", "maintenant")
    a.actualiser_statuts()

    assert _rencontre(a, 2, 1).statut_rencontre == "JOUABLE"


def test_la_demi_face_a_un_cote_mort_devient_jouable_des_que_son_equipe_arrive():
    a = _arbre_de_8([1, 2, 3])
    seul = _rencontre(a, 1, 3)

    a.enregistrer_resultat(seul, seul.id_equipe_a, "QUALIFICATION_DIRECTE", "maintenant")
    a.actualiser_statuts()

    assert _rencontre(a, 2, 2).statut_rencontre == "JOUABLE"
    assert _rencontre(a, 2, 2).id_equipe_a == 3
