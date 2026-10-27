"""
Arbre à élimination directe (B-12, B-14) — logique pure, sans base ni HTTP.

Le service des tournois s'en sert pour générer l'arbre à la clôture des
inscriptions, puis pour recalculer quelles rencontres sont jouables après
chaque résultat. Séparée du service, elle se teste sans base de données.

Vocabulaire :
    emplacement   un côté d'une rencontre, « A » ou « B »
    emplacement mort
                  un côté qui ne recevra jamais d'équipe : vide au premier
                  tour, ou alimenté par une rencontre elle-même morte
    rencontre morte
                  une rencontre non terminée dont les deux côtés sont morts :
                  aucun vainqueur n'en sortira

Un tournoi incomplet (5 équipes sur 8) produit des emplacements morts. La
rencontre devient quand même jouable, avec une seule équipe : l'administrateur
la résout en QUALIFICATION_DIRECTE.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import log2

EMPLACEMENT_A = "A"
EMPLACEMENT_B = "B"


@dataclass(frozen=True)
class PlaceArbre:
    """Une rencontre à créer : sa place dans l'arbre et ses équipes de départ."""

    tour: int
    position: int
    id_equipe_a: int | None = None
    id_equipe_b: int | None = None


def nombre_de_tours(nombre_equipes: int) -> int:
    """Nombre de tours d'un arbre de `nombre_equipes` places (une puissance de 2) : 8 équipes, 3 tours."""
    return int(log2(nombre_equipes))


def suite_de(tour: int, position: int) -> tuple[int, int, str]:
    """Rencontre alimentée par le vainqueur de (tour, position), et le côté occupé.

    Les rencontres 1 et 2 d'un tour alimentent la rencontre 1 du tour suivant,
    côtés A et B ; les rencontres 3 et 4, la rencontre 2 ; etc.
    """
    return tour + 1, (position + 1) // 2, EMPLACEMENT_A if position % 2 else EMPLACEMENT_B


def places(nombre_equipes: int, equipes: Sequence[int]) -> list[PlaceArbre]:
    """Toutes les rencontres de l'arbre, de la finale au premier tour.

    Ordre de création : la finale d'abord, pour que chaque rencontre puisse
    référencer sa suivante déjà insérée.

    Les équipes remplissent d'abord tous les côtés A du premier tour, puis les
    côtés B : avec 5 équipes sur 8, on obtient une vraie rencontre et trois
    qualifications directes, plutôt que deux rencontres et deux premiers tours
    vides.
    """
    if len(equipes) > nombre_equipes:
        raise ValueError("Plus d'équipes que de places dans l'arbre.")

    tours = nombre_de_tours(nombre_equipes)
    rencontres_premier_tour = nombre_equipes // 2
    cotes_a = list(equipes[:rencontres_premier_tour])
    cotes_b = list(equipes[rencontres_premier_tour:])
    cotes_a += [None] * (rencontres_premier_tour - len(cotes_a))
    cotes_b += [None] * (rencontres_premier_tour - len(cotes_b))

    resultat = []
    for tour in range(tours, 0, -1):
        for position in range(1, 2 ** (tours - tour) + 1):
            if tour == 1:
                resultat.append(PlaceArbre(tour, position, cotes_a[position - 1], cotes_b[position - 1]))
            else:
                resultat.append(PlaceArbre(tour, position))
    return resultat


def equipe_de(rencontre, emplacement: str) -> int | None:
    """L'équipe qui occupe le côté A ou B de la rencontre, ou None si ce côté est vide."""
    return rencontre.id_equipe_a if emplacement == EMPLACEMENT_A else rencontre.id_equipe_b


def adversaire(rencontre, id_equipe: int) -> int | None:
    """L'autre équipe de la rencontre, ou None s'il n'y en a pas."""
    return rencontre.id_equipe_b if id_equipe == rencontre.id_equipe_a else rencontre.id_equipe_a


def placer(rencontre, emplacement: str, id_equipe: int) -> None:
    """Place une équipe sur le côté A ou B de la rencontre."""
    if emplacement == EMPLACEMENT_A:
        rencontre.id_equipe_a = id_equipe
    else:
        rencontre.id_equipe_b = id_equipe


class Arbre:
    """Vue d'ensemble des rencontres d'un tournoi, pour raisonner sur leurs liens.

    Travaille sur tout objet qui porte les attributs d'une rencontre (le modèle
    ORM en pratique), et sur le statut courant de chaque équipe.
    """

    def __init__(self, rencontres: Iterable, statuts_equipes: dict[int, str]):
        self.rencontres = list(rencontres)
        self.statuts_equipes = statuts_equipes
        self._par_id = {r.id_rencontre: r for r in self.rencontres}
        self._source = {
            (r.id_rencontre_suivante, r.emplacement_suivant): r
            for r in self.rencontres
            if r.id_rencontre_suivante is not None
        }

    def suivante(self, rencontre):
        """La rencontre alimentée par le vainqueur de celle-ci, ou None pour la finale."""
        return self._par_id.get(rencontre.id_rencontre_suivante)

    def finale(self):
        """None si l'arbre n'existe pas (tournoi jamais clos par l'API)."""
        return next((r for r in self.rencontres if r.id_rencontre_suivante is None), None)

    def est_en_lice(self, id_equipe: int | None) -> bool:
        """Vrai si l'équipe existe et n'est ni éliminée, ni disqualifiée, ni sortie par forfait."""
        return id_equipe is not None and self.statuts_equipes.get(id_equipe) == "EN_LICE"

    def emplacement_mort(self, rencontre, emplacement: str) -> bool:
        """Vrai si ce côté ne recevra jamais d'équipe : vide, tenu par une équipe sortie, ou alimenté par une rencontre elle-même morte.
        """
        id_equipe = equipe_de(rencontre, emplacement)
        if id_equipe is not None:
            # Une équipe sortie (forfait au lancement) ne jouera pas ce match.
            return not self.est_en_lice(id_equipe)
        source = self._source.get((rencontre.id_rencontre, emplacement))
        return source is None or self.est_morte(source)

    def est_morte(self, rencontre) -> bool:
        """Vrai si la rencontre n'est pas terminée et que ses deux côtés sont morts : aucun vainqueur n'en sortira."""
        if rencontre.statut_rencontre == "TERMINE":
            return False
        return self.emplacement_mort(rencontre, EMPLACEMENT_A) and self.emplacement_mort(rencontre, EMPLACEMENT_B)

    def enregistrer_resultat(
        self, rencontre, id_vainqueur: int, type_resultat: str, valide_le,
        score_a: int | None = None, score_b: int | None = None,
    ) -> int | None:
        """Clôt la rencontre et fait monter le vainqueur (B-14).

        Renvoie l'équipe éliminée, ou None pour une qualification directe.
        Les rencontres devenues jouables sont à recalculer ensuite avec
        actualiser_statuts().
        """
        rencontre.id_vainqueur = id_vainqueur
        rencontre.type_resultat = type_resultat
        rencontre.score_a = score_a
        rencontre.score_b = score_b
        rencontre.valide_le = valide_le
        rencontre.statut_rencontre = "TERMINE"

        perdant = adversaire(rencontre, id_vainqueur)
        if perdant is not None:
            self.statuts_equipes[perdant] = "ELIMINEE"

        suivante = self.suivante(rencontre)
        if suivante is not None:
            placer(suivante, rencontre.emplacement_suivant, id_vainqueur)
        return perdant

    def actualiser_statuts(self) -> None:
        """Passe en JOUABLE chaque rencontre dont les deux côtés sont connus.

        « Connu » : une équipe en lice est là, ou l'emplacement est mort. Une
        rencontre sans aucune équipe en lice reste EN_ATTENTE.
        """
        for rencontre in self.rencontres:
            if rencontre.statut_rencontre == "TERMINE":
                continue
            presentes = [
                e for e in (rencontre.id_equipe_a, rencontre.id_equipe_b) if self.est_en_lice(e)
            ]
            cotes_connus = all(
                self.est_en_lice(equipe_de(rencontre, cote)) or self.emplacement_mort(rencontre, cote)
                for cote in (EMPLACEMENT_A, EMPLACEMENT_B)
            )
            rencontre.statut_rencontre = "JOUABLE" if presentes and cotes_connus else "EN_ATTENTE"
