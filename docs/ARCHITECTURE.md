# Architecture du back-end

Ce document explique **comment le code est organisé et pourquoi**. À lire avant
d'écrire la première route.

---

## 1. Technologies

| Rôle | Bibliothèque | Version |
|---|---|---|
| Serveur web | Flask | 3.1.3 |
| Temps réel (WebSocket) | Flask-SocketIO | 5.6.1 |
| Transport WebSocket en développement | simple-websocket | 1.1.0 |
| Autorisation des appels depuis le front | Flask-Cors | 6.0.5 |
| Accès à la base | SQLAlchemy | 2.0.54 |
| Pilote PostgreSQL | pg8000 | 1.31.5 |
| Configuration | python-dotenv | 1.2.2 |
| Tests | pytest | 9.1.1 |
| Base de données | PostgreSQL | 16 (Docker) |
| Documentation d'API | Flasgger | *à venir — voir §7* |

Les versions sont **figées** dans `requirements.txt`. Pour en changer une, on
modifie le fichier et on teste — jamais d'installation à la main sans la
répercuter.

---

## 2. Organisation des dossiers

```
R5A5_..._BACK/
├── docker-compose.yml          PostgreSQL 16 + Adminer
├── requirements.txt            Dépendances, versions figées
├── pytest.ini
├── .env.example                Modèle de configuration (le .env n'est pas versionné)
├── sql/
│   ├── schema_R5A5_sujetB.sql  Source de vérité du schéma
│   └── tests_contraintes.sql   Tests d'intégrité, joués à la création du conteneur
├── docs/
├── tests/
│   ├── conftest.py
│   └── test_socle.py           Vérifie que l'architecture tient ses promesses
└── project_organizer/
    ├── __main__.py             Lancement : python -m project_organizer
    ├── app.py                  Fabrique de l'application
    ├── config.py               Lecture des variables d'environnement
    ├── extensions.py           Instances partagées : socketio (et bientôt Flasgger)
    │
    ├── controllers/            HTTP ↔ services            (modèle : sante_controller.py)
    ├── dtos/                   Schémas d'entrée/sortie    (modèle : sante_dto.py)
    ├── services/               Règles métier              (modèle : sante_service.py)
    ├── repository/             Accès à la base            (modèle : sante_repository.py)
    ├── models/                 Modèles ORM                (vide — une classe par table)
    ├── sockets/                Événements temps réel      (connexion / déconnexion)
    └── utils/
        ├── database.py         Moteur et sessions transactionnelles
        ├── journalisation.py   Logs sur la sortie standard, en JSON
        ├── requetes.py         Une ligne de log par requête HTTP
        └── erreurs.py          Erreurs métier → format du contrat
```

Chaque dossier de couche contient un `__init__.py` qui rappelle ce qu'on y
range et quel fichier prendre pour modèle. **La route `/health` est la seule
fonctionnalité du socle** : elle traverse toutes les couches jusqu'à la base,
et sert d'exemple à recopier.

| Dossier | Il contient | Il ne contient **jamais** |
|---|---|---|
| `controllers/` | Un Blueprint par ressource, qui reçoit la requête, appelle un service, renvoie la réponse | De règle métier, de SQL |
| `dtos/` | Les schémas des charges d'entrée et de sortie | De logique |
| `services/` | Les règles du sujet : qui a le droit, quelle transition d'état est permise, que se passe-t-il quand un résultat est saisi | De code HTTP (`request`, `jsonify`, codes de statut) |
| `repository/` | Les lectures et écritures en base | De règle métier |
| `models/` | La correspondance entre classes Python et tables existantes | De logique |
| `sockets/` | La réception et l'émission des événements WebSocket | De règle métier — il appelle les services, comme un contrôleur |

`static/` et `templates/` ne sont pas utilisés : l'API ne produit aucune page
HTML, l'interface est dans le dépôt front.

---

## 3. Le chemin d'une requête

```
  Front                       Back
  ─────                       ────
  PATCH /api/rencontres/5 ──▶ controllers/rencontre_controller.py
                                 │  valide la charge avec dtos/rencontre_dto.py
                                 │  (400 si invalide, avant tout traitement)
                                 ▼
                              services/rencontre_service.py
                                 │  vérifie les droits (administrateur ?)
                                 │  vérifie l'état (rencontre JOUABLE ?)
                                 │  ouvre UNE transaction
                                 ▼
                              repository/rencontre_repository.py
                                 │  écrit le vainqueur, élimine le perdant,
                                 │  propage le vainqueur dans l'arbre
                                 ▼
                              PostgreSQL
                                 │
                              services/ émet « rencontre:maj » via sockets/
                                 │
  ◀── 200 + Rencontre ─────── controllers/ sérialise avec le DTO de sortie
```

---

## 4. Règle de dépendance entre les couches

Chaque couche ne connaît que celle du dessous.

```
controllers/  ─┐
sockets/      ─┴─▶  services/  ──▶  repository/  ──▶  models/
                        │
                        └──▶  utils/  (accessible à tous)
```

Conséquences concrètes :

- un service ne fait **jamais** `from flask import request` ;
- un repository ne lève **jamais** d'exception HTTP ;
- un contrôleur n'écrit **jamais** de requête SQL.

C'est ce qui rend les services testables sans lancer de serveur, et ce qui
permet au canal WebSocket de réutiliser exactement les mêmes règles que les
routes HTTP.

---

## 5. Accès aux données : ORM et SQL

L'approche est **mixte**, avec une règle pour trancher :

> Si la requête tient en une ligne d'ORM lisible → **ORM**.
> Dès qu'il y a trois jointures ou une condition fine → **SQL explicite** dans
> `repository/`.

En pratique, l'ORM couvre le CRUD (créer une équipe, la renommer, lister des
tournois) ; le SQL explicite couvre l'arbre du tournoi et les vérifications de
droits d'accès.

**Le script SQL est la source de vérité du schéma.** Les modèles ORM décrivent
des tables qui existent déjà : on n'appelle **jamais** `Base.metadata.create_all()`.
Toute évolution du schéma se fait d'abord dans `sql/schema_R5A5_sujetB.sql`,
puis dans le modèle correspondant.

Toute écriture passe par `database.session()`, qui valide à la sortie du bloc
et annule en cas d'erreur. Les opérations en plusieurs étapes (saisie d'un
résultat, clôture des inscriptions) tiennent dans **une seule** transaction.

---

## 6. DTOs et nommage des champs

Le contrat d'API impose le **camelCase** en JSON ; Python impose le
**snake_case**. Le DTO fait la traduction, dans les deux sens, et c'est le
**seul** endroit où elle a lieu :

```python
# dtos/equipe_dto.py
from ..utils.erreurs import BadRequest

def valider_creation_equipe(donnees: dict) -> tuple[str, int]:
    """Entrée : vérifie la charge reçue, lève 400 si elle est invalide."""
    nom = donnees.get("nomEquipe")
    id_role = donnees.get("idRole")
    if not isinstance(nom, str) or not nom.strip():
        raise BadRequest("Le champ 'nomEquipe' est requis.")
    if not isinstance(id_role, int):
        raise BadRequest("Le champ 'idRole' est requis.")
    return nom.strip(), id_role

def equipe_vers_dto(equipe) -> dict:
    """Sortie : objet Python → dictionnaire JSON en camelCase."""
    return {
        "idEquipe": equipe.id_equipe,
        "nomEquipe": equipe.nom_equipe,
        "statutEquipe": equipe.statut_equipe,
    }
```

Le contrôleur appelle la validation, passe les valeurs au service, et renvoie
`jsonify(equipe_vers_dto(...))`. Ni le contrôleur ni le service ne manipulent
de clé en camelCase.

---

## 7. Documentation d'API

Le contrat d'API (`docs/CONTRAT_API.md`) est la référence tant que la
documentation interactive n'est pas en place.

**Prochaine étape : Flasgger**, qui génère une interface Swagger à partir des
routes Flask. Vérifié compatible avec la pile du projet (Flasgger 0.9.7.1 avec
Flask 3.1.3). Il s'ajoutera dans `extensions.py`, et chaque route sera
documentée par sa docstring, en suivant l'approche du cours.

Deux règles à respecter en la mettant en place, pour rester fidèle au contrat :

- chaque route documente ses codes d'erreur (400, 401, 403, 404, 409, 422) ;
- les schémas de réponse sont en camelCase, comme le JSON réellement renvoyé.

---

## 8. Temps réel

Le canal temps réel utilise Flask-SocketIO, qui fournit des **salons** (rooms).

| Salon | Abonnement autorisé |
|---|---|
| `tournoi:{idTournoi}` | Tout le monde, même sans compte (B-19) |
| `equipe:{idEquipe}` | Membres de l'équipe, selon la règle d'accès (B-16, B-18) |

Les événements et leur contenu sont définis au §7 du contrat.

**Une seule règle d'accès pour trois points d'entrée.** Le droit de lire
l'espace d'échange d'une équipe est vérifié par **une seule fonction** de
`services/`, appelée par la route de lecture, la route d'écriture, et le
gestionnaire d'abonnement WebSocket. Trois implémentations séparées, c'est
trois occasions de diverger — et ce sont précisément les points visés par les
tests de sécurité.

**B-17 ne se règle pas qu'en base.** Exclure un joueur supprime sa ligne dans
`composer`, mais un socket déjà ouvert continuerait de recevoir les messages.
Le service d'exclusion doit aussi émettre `equipe:acces-revoque` et retirer le
socket du salon.

---

## 9. Authentification et droits

> Pas encore implémentée dans le socle. Les règles ci-dessous découlent du
> contrat d'API et s'appliqueront quand elle le sera.

- Le jeton JWT ne contient que l'identité (`sub`) et la version (`ver`) —
  **aucun droit**.
- À chaque requête authentifiée, la ligne `utilisateur` est relue : on compare
  `ver` à `version_jeton` (révocation) et on lit `est_administrateur`.
- L'appartenance aux équipes et le rôle de capitaine sont vérifiés en base, par
  le service concerné.

Code HTTP selon la situation (§1.3 du contrat) :

| Situation | Code |
|---|---|
| Pas de jeton, jeton expiré ou révoqué | 401 |
| Ressource publique, action interdite | 403 |
| Ressource invisible pour l'appelant | 404 |

Sur une route `PATCH`, les droits se vérifient **champ par champ** : chaque
route déclare les champs modifiables par rôle, et tout champ hors liste fait
échouer la requête entière en 400 (§1.4 du contrat).

---

## 10. Journalisation

| Choix | Valeur |
|---|---|
| Destination | Sortie standard |
| Format | JSON, une ligne par événement (`LOG_FORMAT=texte` en développement) |
| Configuration | `utils/journalisation.py` |

**Niveaux**

| Niveau | Usage dans ce projet |
|---|---|
| `DEBUG` | Détail utile uniquement en développement |
| `INFO` | Démarrage, requête traitée, transition d'état du tournoi |
| `WARNING` | Anormal mais géré : accès refusé, connexion échouée, schéma incomplet |
| `ERROR` | Échec d'une opération : base injoignable, exception non prévue |
| `CRITICAL` | L'application ne peut plus fonctionner |

**Toujours journaliser** : chaque requête (méthode, chemin, statut, durée,
`idUtilisateur`, identifiant de requête) et chaque **événement de sécurité** —
connexion échouée, 401, 403, exclusion d'un joueur, disqualification.

**Ne jamais journaliser** : mot de passe, jeton, en-tête `Authorization`,
adresse e-mail. On journalise l'`idUtilisateur`, pas l'identité en clair.

**Ne jamais renvoyer au client** un message d'erreur technique (trace, message
de la base, hôte, port). Le détail va dans les logs ; le client reçoit un
message générique.

---

## 11. Conventions

| Sujet | Règle |
|---|---|
| Langue du code | Français pour le métier (`equipe`, `rencontre`, `capitaine`), anglais pour les termes techniques établis (`controller`, `repository`, `schema`) |
| Nommage des fichiers | `<ressource>_controller.py`, `<ressource>_service.py`, `<ressource>_repository.py`, `<ressource>_dto.py` |
| Nombres magiques | Interdits : une constante nommée (`NOMBRE_EQUIPES = 8`) |
| Commentaires | Expliquent le **pourquoi**, jamais le **quoi** |
| Branches | `main` toujours fonctionnelle ; une branche par fonctionnalité : `feat/…`, `fix/…`, `docs/…` |
| Fusion | Par pull request, relue par l'autre membre du binôme |
| Commits | `type(portée): description` — ex. `feat(equipe): exclusion d'un membre` |

---

## 12. Ajouter une fonctionnalité — liste de contrôle

1. La route est-elle dans le **contrat d'API** ? Sinon, la décider à deux d'abord.
2. `dtos/` : validation de l'entrée et conversion de la sortie en camelCase.
3. `repository/` : lectures et écritures, ORM ou SQL selon la règle du §5.
4. `services/` : règles du sujet, vérification des droits, transaction unique.
5. `controllers/` : la route, qui ne fait qu'appeler le service.
6. `sockets/` : l'événement temps réel éventuel, émis par le service.
7. `tests/` : au moins un test qui prouve qu'un utilisateur non autorisé est refusé.
8. Documenter la route (Flasgger, une fois en place) et la tester avec `python -m pytest`.
