# Fiches de décision

Une page par décision : **le problème, les options, ce qu'on a choisi, ce que
ça coûte.** Trois sont obligatoires, deux supplémentaires sont possibles.

> **À rédiger avec vos propres mots.** L'enseignant annonce 0/3 sur cette partie
> en cas de style généré par une IA. Ce dossier ne contient donc volontairement
> **pas** de fiches rédigées : seulement un modèle, et la matière factuelle de
> chaque décision sous forme de notes. Le raisonnement, les hésitations et les
> retours en arrière, c'est à vous de les raconter.

---

## Index

| # | Sujet | Statut | Fichier |
|---|---|---|---|
| 01 | Base de données | Obligatoire — décidée | `01-base-de-donnees.md` |
| 02 | Mécanisme de temps réel | Obligatoire — décidée | `02-temps-reel.md` |
| 03 | Format et destination de la journalisation | Obligatoire — décidée | `03-journalisation.md` |
| 04 | *Au choix* | Facultative | |
| 05 | *Au choix* | Facultative | |

Candidates pour les deux facultatives, parmi les choix déjà faits :
authentification (JWT sans droits dans le jeton + `version_jeton`),
dénormalisation de `id_tournoi` pour la règle B-07, pilote `pg8000`,
Bootstrap plutôt que Tailwind, documentation d'API générée depuis le code.

---

## Modèle

```markdown
# NN — Titre de la décision

**Date :** AAAA-MM-JJ
**Décidée par :** …

## Le problème
Quel besoin du sujet nous a obligés à choisir ? Citer l'exigence (B-xx).

## Les options
Deux ou trois options réellement envisagées, avec pour chacune
ce qu'elle apporte et ce qu'elle coûte.

## Ce qu'on a choisi
L'option retenue, et la raison principale — celle qui a fait pencher.

## Ce que ça coûte
Ce qu'on accepte de perdre ou de devoir compenser ailleurs.
Une décision sans coût n'est pas une décision.
```

---

## Matière des fiches obligatoires

Notes factuelles, à transformer en texte.

### 01 — Base de données

- Retenue : PostgreSQL 16, lancé par Docker.
- Envisagée : MySQL. MongoDB écarté d'emblée — modèle fortement relationnel.
- Besoins qui ont tranché :
  - index uniques partiels : un seul capitaine par équipe, une seule demande
    d'adhésion en attente — inexistants en MySQL ;
  - `TIMESTAMPTZ` : dates avec fuseau, MySQL n'a que `DATETIME` sans fuseau ;
  - `CHECK` fiables (ignorés par MySQL avant la 8.0.16).
- Frontière base / code : la base garantit l'intégrité structurelle, Flask
  porte les règles qui dépendent du cycle de vie (transitions d'état, décompte
  des 5 joueurs).
- Vérification : 10 tests d'intégrité rejoués à chaque création du conteneur,
  dont 2 qui vérifient qu'une contrainte n'est **pas** trop stricte.
- Coût : aucun hébergeur n'est prévu, mais Docker devient un prérequis
  d'installation.

### 02 — Mécanisme de temps réel

- Besoins : B-16 (chat d'équipe sans rechargement), B-17 (perte d'accès
  immédiate), B-18 (espace fermé après élimination), B-19 (suivi du tournoi).
- Options : WebSocket (Flask-SocketIO), Server-Sent Events, rafraîchissement
  périodique.
- Retenue : Flask-SocketIO.
- Raison : bidirectionnel (le chat envoie et reçoit), et **salons natifs** —
  un par équipe, un par tournoi — ce qui donne l'isolation et l'expulsion
  d'un joueur exclu sans les réimplémenter.
- SSE : unidirectionnel, il aurait fallu gérer soi-même les abonnements.
  Rafraîchissement : charge inutile, latence, et B-17 non garanti.
- Coût : une seconde voie d'accès à sécuriser en plus des routes HTTP ; d'où
  une règle d'accès unique partagée entre les deux. Et l'expulsion du socket
  lors d'une exclusion, qu'on oublierait facilement.

### 03 — Format et destination de la journalisation

- Destination retenue : sortie standard. Envisagé : fichier.
  - Un fichier doit être créé, tourné, purgé, et disparaît avec le conteneur.
  - La sortie standard est lue par Docker, l'IDE, et n'importe quel hébergeur.
- Format retenu : JSON, une ligne par événement. Envisagé : texte libre.
  - Le texte se lit bien mais ne se filtre pas.
  - Les tests portent sur les droits d'accès : pouvoir retrouver tous les
    refus d'un utilisateur a une vraie valeur.
- Coût : illisible dans un terminal → mode `LOG_FORMAT=texte` pour le
  développement.
- Règles associées : ce qu'on journalise toujours (requêtes, événements de
  sécurité) et jamais (mot de passe, jeton, e-mail) — voir
  `ARCHITECTURE.md` §10.
