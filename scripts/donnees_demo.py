"""
Jeu de données de démonstration — DÉVELOPPEMENT LOCAL UNIQUEMENT.

    python scripts/donnees_demo.py                 crée les données (rejouable, rien n'est dupliqué)
    python scripts/donnees_demo.py --reinitialiser supprime les tournois de démonstration puis les recrée
    python scripts/donnees_demo.py --forcer        passe outre la présence de vrais comptes (voir plus bas)

Tout passe par l'API réelle (les mêmes services que le site) : l'arbre est
généré à la clôture, les forfaits au lancement, les résultats se propagent.
Les données sont donc cohérentes, ce qu'un script SQL ne garantirait pas.

Comptes créés (mots de passe connus de tous : ne JAMAIS jouer ce script sur une
base partagée ou en production). Il refuse de s'exécuter :
  - si COOKIE_SECURE=true (déploiement HTTPS) ;
  - si la base contient déjà un compte qui n'est pas un compte de démonstration : c'est
    une base utilisée par de vraies personnes. Ce contrôle lit la base elle-même, il
    fonctionne donc aussi dans Docker, où le conteneur du script ne connaît pas la
    configuration de l'API. `--forcer` passe outre, en connaissance de cause.

    admin@agon-cup.fr        administrateur
    joueur01@demo.iut.fr …   40 joueurs (joueur01 à joueur40), capitaines ou membres selon le tournoi

Le visiteur n'est pas un compte : c'est quelqu'un qui n'est pas connecté.
"""

import argparse
import os
import sys
from pathlib import Path

# Silencieux : on veut lire le récapitulatif, pas une ligne de journal par requête.
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "texte")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask_jwt_extended import create_access_token  # noqa: E402
from sqlalchemy import text  # noqa: E402

from project_organizer.app import create_app  # noqa: E402
from project_organizer.config import Config  # noqa: E402
from project_organizer.utils import database, mots_de_passe  # noqa: E402

ADMIN = {"pseudo": "admin", "email": "admin@agon-cup.fr", "mot_de_passe": "admin-demo-2026"}
MOT_DE_PASSE_JOUEURS = "demo-joueurs-2026"
DOMAINE_DES_JOUEURS = "demo.iut.fr"
NOMBRE_DE_JOUEURS = 40
EQUIPES = ["Hiboux", "Nova", "Zenith", "Nébula", "Orage", "Kraken", "Phénix", "Titans"]

JEUX = {
    "League of Legends": ["Top", "Jungle", "Mid", "ADC", "Support"],
    "Overwatch 2": ["Tank 1", "Tank 2", "DPS 1", "DPS 2", "Heal 1", "Heal 2"],
    "Valorant": ["Duelliste", "Initiateur", "Contrôleur", "Sentinelle", "Flex"],
    "Counter-Strike 2": ["Entry", "Support", "Lurker", "AWPer", "IGL"],
    "Dota 2": ["Carry (pos. 1)", "Mid (pos. 2)", "Offlane (pos. 3)", "Soutien (pos. 4)", "Soutien complet (pos. 5)"],
    "Rocket League": ["Attaquant", "Milieu", "Défenseur"],
    "Fortnite": ["Meneur", "Fragger", "Constructeur", "Soutien"],
    "PUBG": ["Meneur", "Fragger", "Sniper", "Soutien"],
    "Minecraft": ["Bâtisseur", "Attaquant", "Collecteur", "Défenseur"],
    "EA Sports FC": ["Joueur"],
    "Pokémon": ["Dresseur"],
    "Échecs": ["Joueur"],
}
NOMS_DE_TOURNOIS = [
    "Coupe Inter-IUT — Automne 2026",
    "Nuit CS2 des IUT",
    "Open Overwatch 2 — Automne",
    "Valorant Clash des IUT",
    "Dota 2 Découverte",
    "Coupe Inter-IUT — Printemps 2026",
]
# Des tournois aux inscriptions ouvertes, sans équipe : ils montrent le catalogue et laissent tout à faire.
TOURNOIS_A_REMPLIR = [
    ("Rocket League Cup — IUT", "Rocket League", 8, 4),
    ("Bed Wars des IUT", "Minecraft", 8, 3),
]
# Des tournois en solo : chaque inscrit est un joueur (son équipe porte son pseudo), numéros des joueurs inscrits.
TOURNOIS_SOLO = [
    ("EA FC — Derby des IUT", "EA Sports FC", 16, 3, [3, 8, 14, 19, 25, 31, 37]),
    ("Blitz d'échecs inter-IUT", "Échecs", 16, 1, [2, 5, 9, 12, 17, 22]),
]
# Des tournois plus anciens ou en cours, pour que le site ait un passé et un présent : (nom, jeu, ancienneté en jours, décalage, matchs joués ou None pour tout jouer).
TOURNOIS_SUPPLEMENTAIRES = [
    ("Valorant Spring Cup", "Valorant", 120, 10, None),
    ("Rentrée CS2 — Open IUT", "Counter-Strike 2", 70, 15, None),
    ("Dota 2 — Ligue du jeudi", "Dota 2", 6, 25, 4),
]
TOUS_LES_TOURNOIS = (
    NOMS_DE_TOURNOIS
    + [nom for nom, *_ in TOURNOIS_A_REMPLIR]
    + [nom for nom, *_ in TOURNOIS_SOLO]
    + [nom for nom, *_ in TOURNOIS_SUPPLEMENTAIRES]
)


class Demo:
    def __init__(self):
        self.app = create_app()
        self.clients: dict[int, object] = {}
        self.ids: dict[str, int] = {}  # pseudo → idUtilisateur

    # --- Appels de l'API, comme le ferait le front --------------------------------------

    def client(self, pseudo: str):
        if pseudo not in self.clients:
            with database.session() as session:
                id_u, version = session.execute(
                    text("SELECT id_utilisateur, version_jeton FROM utilisateur WHERE pseudo = :p"), {"p": pseudo}
                ).one()
            with self.app.app_context():
                jeton = create_access_token(identity=str(id_u), additional_claims={"ver": version})
            client = self.app.test_client()
            client.set_cookie("jeton", jeton)
            self.clients[pseudo] = client
            self.ids[pseudo] = id_u
        return self.clients[pseudo]

    def appeler(self, pseudo: str, methode: str, chemin: str, attendu: int, **charge):
        reponse = getattr(self.client(pseudo), methode)(chemin, **charge)
        if reponse.status_code != attendu:
            raise SystemExit(f"{methode.upper()} {chemin} par {pseudo} : {reponse.status_code} au lieu de {attendu} — {reponse.get_json()}")
        return reponse.get_json() if reponse.status_code != 204 else None

    # --- Préparation -------------------------------------------------------------------------

    def preparer_les_jeux(self) -> dict[str, tuple[int, list[int]]]:
        resultat = {}
        with database.session() as session:
            for nom, postes in JEUX.items():
                session.execute(
                    text("INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES (:n, :k) ON CONFLICT (nom_jeu) DO NOTHING"), {"n": nom, "k": len(postes)}
                )
                id_jeu = session.execute(text("SELECT id_jeu FROM jeu WHERE nom_jeu = :n"), {"n": nom}).scalar_one()
                for poste in postes:
                    session.execute(
                        text("INSERT INTO role_jeu (id_jeu, libelle_role) VALUES (:j, :l) ON CONFLICT (id_jeu, libelle_role) DO NOTHING"),
                        {"j": id_jeu, "l": poste},
                    )
                ids_postes = list(session.scalars(text("SELECT id_role FROM role_jeu WHERE id_jeu = :j ORDER BY id_role"), {"j": id_jeu}))
                resultat[nom] = (id_jeu, ids_postes)
        return resultat

    def preparer_les_comptes(self) -> int:
        crees = 0
        with database.session() as session:
            def creer(pseudo, email, mdp, admin=False):
                nonlocal crees
                if session.execute(text("SELECT 1 FROM utilisateur WHERE pseudo = :p OR email = :e"), {"p": pseudo, "e": email}).first():
                    return
                session.execute(
                    text("INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash, est_administrateur) VALUES (:p, :e, :h, :a)"),
                    {"p": pseudo, "e": email, "h": mots_de_passe.hacher(mdp), "a": admin},
                )
                crees += 1
            creer(ADMIN["pseudo"], ADMIN["email"], ADMIN["mot_de_passe"], admin=True)
            for numero in range(1, NOMBRE_DE_JOUEURS + 1):
                creer(f"joueur{numero:02d}", f"joueur{numero:02d}@{DOMAINE_DES_JOUEURS}", MOT_DE_PASSE_JOUEURS)
        return crees

    # --- Scénarios --------------------------------------------------------------------------------

    def tournoi_existe(self, nom: str) -> bool:
        with database.session() as session:
            return session.execute(text("SELECT 1 FROM tournoi WHERE nom_tournoi = :n"), {"n": nom}).first() is not None

    def creer_tournoi(self, nom: str, jeu: str, jeux, nombre_equipes: int, ancien_de_jours: int) -> int:
        id_jeu, _ = jeux[jeu]
        id_tournoi = self.appeler("admin", "post", "/api/tournois", 201,
                                  json={"nomTournoi": nom, "idJeu": id_jeu, "nombreEquipes": nombre_equipes})["idTournoi"]
        # Antidaté : une liste où tout est « créé aujourd'hui » ne ressemble à rien.
        with database.session() as session:
            session.execute(text("UPDATE tournoi SET cree_le = cree_le - make_interval(days => :j) WHERE id_tournoi = :t"),
                            {"j": ancien_de_jours, "t": id_tournoi})
        return id_tournoi

    def monter_equipe(self, id_tournoi: int, nom: str, joueurs: list[int], postes: list[int]) -> int:
        """joueurs : numéros de joueurs ; le premier est capitaine. Chaque membre reçoit son poste."""
        capitaine = f"joueur{joueurs[0]:02d}"
        id_equipe = self.appeler(capitaine, "post", f"/api/tournois/{id_tournoi}/equipes", 201,
                                 json={"nomEquipe": nom, "idRole": postes[0]})["idEquipe"]
        for rang, numero in enumerate(joueurs[1:], start=1):
            pseudo = f"joueur{numero:02d}"
            demande = self.appeler(pseudo, "post", f"/api/equipes/{id_equipe}/demandes", 201)["idDemande"]
            self.appeler(capitaine, "patch", f"/api/demandes/{demande}", 200, json={"statutDemande": "ACCEPTEE"})
            self.client(pseudo)
            self.appeler(capitaine, "patch", f"/api/equipes/{id_equipe}/membres/{self.ids[pseudo]}", 200, json={"idRole": postes[rang]})
        return id_equipe

    def huit_equipes(self, id_tournoi: int, postes: list[int], decalage: int, noms=EQUIPES) -> list[int]:
        """Huit équipes complètes de cinq joueurs, en décalant les joueurs d'un tournoi à l'autre."""
        ids = []
        for i, nom in enumerate(noms):
            joueurs = [((i * 5 + k + decalage) % NOMBRE_DE_JOUEURS) + 1 for k in range(5)]
            ids.append(self.monter_equipe(id_tournoi, nom, joueurs, postes))
        return ids

    def changer_statut(self, id_tournoi: int, statut: str) -> None:
        self.appeler("admin", "patch", f"/api/tournois/{id_tournoi}", 200, json={"statutTournoi": statut})

    def jouer(self, id_tournoi: int, rencontres_a_jouer: int | None) -> None:
        """Saisit des résultats, du premier tour vers la finale ; None : jusqu'au bout."""
        joues = 0
        while rencontres_a_jouer is None or joues < rencontres_a_jouer:
            arbre = self.appeler("admin", "get", f"/api/tournois/{id_tournoi}/arbre", 200)
            jouables = [r for r in arbre if r["statutRencontre"] == "JOUABLE"]
            if not jouables:
                return
            r = jouables[0]
            gagne_a = (r["idRencontre"] % 2 == 0)
            corps = {"idVainqueur": (r["equipeA"] if gagne_a else r["equipeB"])["idEquipe"], "typeResultat": "NORMAL",
                     "scoreA": 2 if gagne_a else 1, "scoreB": 1 if gagne_a else 2}
            if "equipeA" not in r or "equipeB" not in r:
                seule = r.get("equipeA") or r.get("equipeB")
                corps = {"idVainqueur": seule["idEquipe"], "typeResultat": "QUALIFICATION_DIRECTE"}
            self.appeler("admin", "patch", f"/api/rencontres/{r['idRencontre']}", 200, json=corps)
            joues += 1

    def ecrire(self, pseudo: str, id_equipe: int, messages: list[str]) -> None:
        for contenu in messages:
            self.appeler(pseudo, "post", f"/api/equipes/{id_equipe}/messages", 201, json={"contenu": contenu})

    def equipes_de(self, nom_tournoi: str) -> list[dict]:
        """Les équipes d'un tournoi avec leur statut, leur capitaine et un autre membre, lus en base."""
        with database.session() as session:
            lignes = session.execute(text("""
                SELECT e.id_equipe, e.nom_equipe, e.statut_equipe,
                       (SELECT u.pseudo FROM composer c JOIN utilisateur u USING (id_utilisateur)
                         WHERE c.id_equipe = e.id_equipe AND c.est_capitaine) AS capitaine,
                       (SELECT u.pseudo FROM composer c JOIN utilisateur u USING (id_utilisateur)
                         WHERE c.id_equipe = e.id_equipe AND NOT c.est_capitaine ORDER BY u.pseudo LIMIT 1) AS membre
                FROM equipe e JOIN tournoi t USING (id_tournoi)
                WHERE t.nom_tournoi = :n ORDER BY e.id_equipe"""), {"n": nom_tournoi}).mappings().all()
        return [dict(ligne) for ligne in lignes]

    def scenarios(self, jeux) -> list[str]:
        faits = []
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[0]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[0], "League of Legends", jeux, 8, 21)
            equipes = self.huit_equipes(t, jeux["League of Legends"][1], decalage=0)
            self.changer_statut(t, "INSCRIPTIONS_CLOSES"); self.changer_statut(t, "EN_COURS")
            self.jouer(t, 5)  # les quatre quarts de finale et une demi-finale
            # Le tirage au sort décide qui est encore en lice : on écrit dans une équipe qui l'est.
            vivante = next(e for e in self.equipes_de(NOMS_DE_TOURNOIS[0]) if e["statut_equipe"] == "EN_LICE")
            self.ecrire(vivante["capitaine"], vivante["id_equipe"],
                        ["Salut l'équipe, on se retrouve à 20 h pour la demi ?", "Je prends le mid, ça vous va ?"])
            self.ecrire(vivante["membre"], vivante["id_equipe"], ["Parfait. Je regarde les compos adverses."])
            faits.append(NOMS_DE_TOURNOIS[0])
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[1]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[1], "Counter-Strike 2", jeux, 8, 12)
            self.huit_equipes(t, jeux["Counter-Strike 2"][1], decalage=5)
            self.changer_statut(t, "INSCRIPTIONS_CLOSES")
            faits.append(NOMS_DE_TOURNOIS[1])
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[2]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[2], "Overwatch 2", jeux, 8, 9)
            postes = jeux["Overwatch 2"][1]
            for i, (nom, taille) in enumerate([("Hiboux", 5), ("Nova", 5), ("Zenith", 5), ("Nébula", 3), ("Orage", 1)]):
                self.monter_equipe(t, nom, [i * 5 + k + 1 for k in range(taille)], postes)
            # Une demande en attente, pour que le capitaine de « Nébula » ait quelque chose à traiter.
            with database.session() as session:
                id_nebula = session.execute(text("SELECT id_equipe FROM equipe WHERE id_tournoi = :t AND nom_equipe = 'Nébula'"), {"t": t}).scalar_one()
            self.appeler("joueur38", "post", f"/api/equipes/{id_nebula}/demandes", 201)
            faits.append(NOMS_DE_TOURNOIS[2])
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[3]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[3], "Valorant", jeux, 8, 5)
            postes = jeux["Valorant"][1]
            for i, nom in enumerate(["Kraken", "Phénix", "Titans"]):
                self.monter_equipe(t, nom, [i * 3 + k + 1 for k in range(2 + i)], postes)
            faits.append(NOMS_DE_TOURNOIS[3])
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[4]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[4], "Dota 2", jeux, 8, 2)
            self.monter_equipe(t, "Orage", [10], jeux["Dota 2"][1])
            faits.append(NOMS_DE_TOURNOIS[4])
        if not self.tournoi_existe(NOMS_DE_TOURNOIS[5]):
            t = self.creer_tournoi(NOMS_DE_TOURNOIS[5], "League of Legends", jeux, 8, 200)
            self.huit_equipes(t, jeux["League of Legends"][1], decalage=20)
            self.changer_statut(t, "INSCRIPTIONS_CLOSES"); self.changer_statut(t, "EN_COURS")
            self.jouer(t, None)
            self.changer_statut(t, "TERMINE")
            faits.append(NOMS_DE_TOURNOIS[5])
        for nom, jeu, nombre_equipes, age in TOURNOIS_A_REMPLIR:
            if not self.tournoi_existe(nom):
                self.creer_tournoi(nom, jeu, jeux, nombre_equipes, age)
                faits.append(nom)
        for nom, jeu, nombre_equipes, age, joueurs in TOURNOIS_SOLO:
            if not self.tournoi_existe(nom):
                t = self.creer_tournoi(nom, jeu, jeux, nombre_equipes, age)
                for numero in joueurs:
                    # Un jeu en solo : l'équipe d'un joueur porte son pseudo (comme le fait le site).
                    self.monter_equipe(t, f"joueur{numero:02d}", [numero], jeux[jeu][1])
                faits.append(nom)
        for nom, jeu, age, decalage, matchs in TOURNOIS_SUPPLEMENTAIRES:
            if not self.tournoi_existe(nom):
                t = self.creer_tournoi(nom, jeu, jeux, 8, age)
                self.huit_equipes(t, jeux[jeu][1], decalage=decalage)
                self.changer_statut(t, "INSCRIPTIONS_CLOSES"); self.changer_statut(t, "EN_COURS")
                self.jouer(t, matchs)
                if matchs is None:
                    self.changer_statut(t, "TERMINE")
                faits.append(nom)
        return faits

    def recapitulatif_du_tournoi_en_cours(self) -> str:
        """Qui essayer dans « la Coupe en cours » : calculé depuis la base, car le tirage au sort varie."""
        equipes = self.equipes_de(NOMS_DE_TOURNOIS[0])
        vivante = next((e for e in equipes if e["statut_equipe"] == "EN_LICE"), None)
        eliminee = next((e for e in equipes if e["statut_equipe"] == "ELIMINEE"), None)
        lignes = []
        if vivante:
            lignes.append(f"  Capitaine, chat ouvert, déjà des messages   {vivante['capitaine']} — équipe « {vivante['nom_equipe']} »")
            lignes.append(f"  Membre de cette équipe                      {vivante['membre']}")
        if eliminee:
            lignes.append(f"  Capitaine d'une équipe ÉLIMINÉE (chat fermé) {eliminee['capitaine']} — équipe « {eliminee['nom_equipe']} »")
        return "\n".join(lignes) or "  (tournoi en cours absent : relancer avec --reinitialiser)"

    def reinitialiser(self) -> None:
        with database.session() as session:
            session.execute(text("DELETE FROM tournoi WHERE nom_tournoi = ANY(:noms)"), {"noms": TOUS_LES_TOURNOIS})


def comptes_hors_demonstration() -> int:
    """Nombre de comptes qui ne sont pas des comptes de démonstration : s'il y en a, la base sert à de vraies personnes."""
    with database.session() as session:
        return session.execute(
            text("SELECT count(*) FROM utilisateur WHERE email <> :admin AND email NOT LIKE :joueurs"),
            {"admin": ADMIN["email"], "joueurs": f"%@{DOMAINE_DES_JOUEURS}"},
        ).scalar_one()


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Jeu de données de démonstration (développement local uniquement).")
    analyseur.add_argument("--reinitialiser", action="store_true", help="supprime d'abord les tournois de démonstration")
    analyseur.add_argument("--forcer", action="store_true", help="tourne même si la base contient de vrais comptes")
    arguments = analyseur.parse_args()

    if Config.COOKIE_SECURE:
        raise SystemExit("Refus : COOKIE_SECURE=true indique un déploiement. Ce script crée des comptes aux mots de passe connus de tous.")

    demo = Demo()
    # Après Demo() : c'est lui qui crée l'application et ouvre la base.
    autres = comptes_hors_demonstration()
    if autres and not arguments.forcer:
        raise SystemExit(
            f"Refus : la base contient {autres} compte(s) qui ne sont pas des comptes de démonstration. "
            "Ce script crée un administrateur au mot de passe connu de tous : sur une base utilisée par de vraies "
            "personnes, n'importe qui pourrait s'y connecter. Relancer avec --forcer seulement sur une base locale."
        )
    if arguments.reinitialiser:
        demo.reinitialiser()
    jeux = demo.preparer_les_jeux()
    comptes = demo.preparer_les_comptes()
    faits = demo.scenarios(jeux)

    print(f"\n{comptes} compte(s) créé(s), {len(faits)} tournoi(s) créé(s)" + (" : " + ", ".join(faits) if faits else " (déjà présents)"))
    print(f"""
COMPTES (connexion par e-mail)
  Administrateur  {ADMIN['email']}   mot de passe : {ADMIN['mot_de_passe']}
  Joueurs         joueur01@demo.iut.fr … joueur40@demo.iut.fr   mot de passe : {MOT_DE_PASSE_JOUEURS}
  Visiteur        aucun compte : ouvrir le site sans se connecter

OÙ ESSAYER QUOI — « {NOMS_DE_TOURNOIS[0]} » (en cours ; le tirage au sort varie, d'où ces noms calculés)
{demo.recapitulatif_du_tournoi_en_cours()}

OÙ ESSAYER QUOI — les autres tournois
  Capitaine avec une demande à traiter    joueur16 — équipe « Nébula », « {NOMS_DE_TOURNOIS[2]} »
  Joueur qui a une demande en attente     joueur38 (visible dans « Mes équipes »)
  Joueur libre dans ce tournoi, qui peut créer une équipe ou postuler   joueur39, joueur40
  Inscriptions ouvertes (créer / rejoindre)   « {NOMS_DE_TOURNOIS[2]} », « {NOMS_DE_TOURNOIS[3]} », « {NOMS_DE_TOURNOIS[4]} »
  Inscriptions closes (l'administrateur peut le lancer)   « {NOMS_DE_TOURNOIS[1]} »
  Tournoi terminé                          « {NOMS_DE_TOURNOIS[5]} »
  Inscriptions ouvertes, sans équipe       {", ".join(f"« {nom} »" for nom, *_ in TOURNOIS_A_REMPLIR)}
  Tournois en solo (inscrits = joueurs)    {", ".join(f"« {nom} »" for nom, *_ in TOURNOIS_SOLO)}
  Palmarès et tournoi en cours en plus     {", ".join(f"« {nom} »" for nom, *_ in TOURNOIS_SUPPLEMENTAIRES)}

Pour tester deux profils en même temps : deux fenêtres de navigation privée (sinon elles partagent le même cookie).
""")


if __name__ == "__main__":
    main()
