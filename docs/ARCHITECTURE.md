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
| Jeton JWT en cookie | flask-jwt-extended | 4.7.4 |
| Hachage des mots de passe | argon2-cffi | 25.1.0 |
| Limitation de débit | Flask-Limiter | 4.1.1 |
| Configuration | python-dotenv | 1.2.2 |
| Tests | pytest | 9.1.1 |
| Base de données | PostgreSQL | 16 (Docker) |
| Validation et documentation d'API | Pydantic + flask-pydantic-spec | 2.13.5 / 0.8.7 |

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
│   ├── donnees_demo.sql        Données de démonstration, jouées à la main
│   └── tests_contraintes.sql   Tests d'intégrité, joués à la création du conteneur
├── docs/
├── tests/
│   ├── conftest.py
│   ├── test_socle.py           Vérifie que l'architecture tient ses promesses
│   ├── test_authentification.py
│   ├── test_protection.py      Toute route non publique exige un jeton
│   ├── test_tournois.py
│   └── test_documentation.py   Documentation générée et validation au format du contrat
└── project_organizer/
    ├── __main__.py             Lancement : python -m project_organizer
    ├── app.py                  Fabrique de l'application
    ├── config.py               Lecture des variables d'environnement
    ├── extensions.py           Instances partagées : socketio, spec (documentation)
    │
    ├── controllers/            HTTP ↔ services            (modèle : sante_controller.py)
    ├── dtos/                   Modèles Pydantic d'entrée/sortie (base.py, modèle : sante_dto.py)
    ├── services/               Règles métier              (modèle : sante_service.py)
    ├── repository/             Accès à la base            (modèle : sante_repository.py)
    ├── models/                 Modèles ORM, une classe par table (types.py : ENUM PostgreSQL)
    ├── sockets/                Événements temps réel      (connexion / déconnexion)
    └── utils/
        ├── database.py         Moteur et sessions transactionnelles
        ├── journalisation.py   Logs sur la sortie standard, en JSON
        ├── requetes.py         Une ligne de log par requête HTTP
        ├── erreurs.py          Erreurs métier → format du contrat
        ├── authentification.py Jeton en cookie, @publique, @administrateur_requis
        ├── mots_de_passe.py    Hachage argon2
        └── entetes_securite.py En-têtes de sécurité sur toutes les réponses
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

Un DTO est un modèle **Pydantic**. Il est la source unique de trois choses :
la validation de ce qui entre, le typage du code, et la documentation d'API
(§7). Modifier un DTO met les trois à jour ensemble.

Le contrat impose le **camelCase** en JSON, Python le **snake_case**. Les
classes de `dtos/base.py` font la traduction, et c'est le seul endroit où elle
a lieu :

| Classe | Pour | Particularité |
|---|---|---|
| `ModeleApi` | Réponses | Champs Python en snake_case, JSON en camelCase ; `vers_json()` pour répondre |
| `ModeleEntree` | Corps de requête | Tout champ inconnu → 400 (contrat §1.4, règle 3) |
| `ErreurDto` | Réponses d'erreur | Forme `{ erreur, detail }`, à déclarer pour chaque code d'erreur |

```python
# dtos/equipe_dto.py
from pydantic import Field

from .base import ModeleApi, ModeleEntree


class CreationEquipeDto(ModeleEntree):
    nom_equipe: str = Field(min_length=1, max_length=50)   # reçu en "nomEquipe"
    id_role: int                                           # reçu en "idRole"


class EquipeDto(ModeleApi):
    id_equipe: int
    nom_equipe: str
    statut_equipe: str
```

Le contrôleur ne valide rien à la main : si le corps ne correspond pas au
modèle, la requête est rejetée en 400 avant d'atteindre la fonction, avec la
liste des champs fautifs :

```json
{ "erreur": "Bad Request", "detail": { "champs": [ { "champ": "nomEquipe", "message": "Field required" } ] } }
```

Ni le contrôleur ni le service ne manipulent de clé en camelCase.

---

## 7. Documentation d'API

Elle est **générée depuis le code** par flask-pydantic-spec, à partir des DTOs
déclarés sur chaque route. Il n'existe donc pas de description écrite à la
main qui pourrait contredire le code.

| Adresse | Contenu |
|---|---|
| http://localhost:5000/apidoc/swagger | Interface Swagger : routes, schémas, essai des requêtes |
| http://localhost:5000/apidoc/openapi.json | Description OpenAPI brute |

Une route documentée :

```python
from flask import request
from flask_pydantic_spec import Response

from ..dtos.base import ErreurDto
from ..dtos.equipe_dto import CreationEquipeDto, EquipeDto
from ..extensions import spec


@equipes_bp.post("/api/tournois/<int:id_tournoi>/equipes")
@spec.validate(
    body=CreationEquipeDto,
    resp=Response(HTTP_201=EquipeDto, HTTP_401=ErreurDto, HTTP_404=ErreurDto, HTTP_409=ErreurDto),
    tags=["Équipes"],
)
def creer_equipe(id_tournoi: int):
    """Inscrire une équipe à un tournoi (B-05).

    La première ligne de la docstring devient le titre de la route dans
    Swagger, la suite sa description.
    """
    donnees: CreationEquipeDto = request.context.body
    equipe = equipe_service.creer(id_tournoi, donnees.nom_equipe, donnees.id_role)
    return jsonify(equipe_vers_dto(equipe).vers_json()), 201
```

Règles :

- **Chaque code d'erreur possible est déclaré** dans `Response(...)`, avec
  `ErreurDto`. Une documentation limitée au cas qui marche oblige le front à
  découvrir les erreurs en les provoquant.
- **La réponse est vérifiée contre son DTO.** Une route qui renverrait autre
  chose que ce que la documentation annonce répond 500 et laisse une ligne
  d'erreur dans les logs : c'est un bug à corriger.
- **Validation : 400, pas 422.** La bibliothèque renvoie 422 par défaut ; notre
  contrat réserve 422 aux règles métier (§1.2). Le réglage est dans
  `extensions.py`, la mise au format du contrat dans `utils/erreurs.py`.
- **Une seule source par information.** Quand une route est implémentée, sa
  description détaillée dans `CONTRAT_API.md` est remplacée par un renvoi vers
  Swagger. Le contrat garde les règles transverses : format des erreurs, sens
  des codes, authentification, découpage 403 / 404.

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

Tout est dans `utils/authentification.py`. Trois niveaux, chacun vérifie ce
qu'il est seul à pouvoir vérifier :

| Niveau | Où | Vérifie |
|---|---|---|
| 1. Jeton | `before_request`, pour **toutes** les routes | Cookie présent, signature, expiration, `ver` = `version_jeton` en base |
| 2. Rôle | `@administrateur_requis` sur la route | `est_administrateur`, relu en base |
| 3. Ressource | Le **service** | Capitaine de *cette* équipe, membre de *cette* équipe… |

**Refuser par défaut.** Une route sans décorateur exige un jeton. Une route
publique le déclare avec `@publique`, posé juste sous `@bp.get` / `@bp.post` :

```python
@tournoi_bp.get("")
@publique
@spec.validate(...)
def lister_tournois(): ...


@tournoi_bp.post("")
@administrateur_requis
@spec.validate(...)
def creer_tournoi():
    createur = utilisateur_courant()   # l'utilisateur relu en base
    ...
```

`tests/test_protection.py` appelle chaque route de l'API sans jeton et exige
un `401`, sauf pour la liste `ROUTES_PUBLIQUES`. Ajouter une route publique,
c'est donc l'ajouter à cette liste : un oubli de `@publique` se voit tout de
suite, un oubli de protection aussi.

**Le jeton** est un cookie `HttpOnly` `SameSite=Lax` (contrat §2), créé par
`ouvrir_session()` et effacé par `fermer_session()`. Il ne contient que `sub`
et `ver` (plus les champs techniques de flask-jwt-extended) : **aucun droit**.

**Mots de passe** : `utils/mots_de_passe.py`, argon2. Quand l'e-mail est
inconnu, un hachage leurre est vérifié quand même, pour que la réponse prenne
le même temps.

**Limitation de débit** : `@limiter.limit(Config.LIMITE_CONNEXION)` sur la
connexion et l'inscription (5 par minute et par adresse par défaut).

**En-têtes de sécurité** : `utils/entetes_securite.py` pose `nosniff`,
`X-Frame-Options: DENY` et une `Content-Security-Policy` stricte sur toutes les
réponses, sauf la page Swagger.

Code HTTP selon la situation (§1.3 du contrat) :

| Situation | Code |
|---|---|
| Pas de jeton, jeton expiré, falsifié ou révoqué | 401 |
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
2. `dtos/` : un modèle d'entrée (`ModeleEntree`) et un modèle de sortie (`ModeleApi`).
3. `repository/` : lectures et écritures, ORM ou SQL selon la règle du §5.
4. `services/` : règles du sujet, vérification des droits, transaction unique.
5. `controllers/` : la route, qui ne fait qu'appeler le service.
6. `sockets/` : l'événement temps réel éventuel, émis par le service.
7. `tests/` : au moins un test qui prouve qu'un utilisateur non autorisé est refusé.
8. `@spec.validate(...)` sur la route, avec **tous** ses codes d'erreur ; vérifier dans Swagger, puis `python -m pytest`.
