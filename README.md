# Agôn Cup — API

API de la plateforme de tournois de l'association étudiante (R5A5, sujet B).

Ce dépôt contient le back-end : une API REST en Flask, un canal temps réel en
WebSocket, et le schéma de la base PostgreSQL. L'interface est dans le dépôt
**`R5A5_2026_SUJETB_GUERREIROMARQUES_ZAPOI_FRONT`**, qui a besoin de cette API
pour fonctionner.

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Organisation du code, règles entre les couches, conventions |
| [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md) | Contrat figé entre le front et le back |
| [`docs/TESTS_DROITS_ACCES.md`](docs/TESTS_DROITS_ACCES.md) | Chaque règle d'accès du sujet, avec le test qui la prouve |
| [`API.md`](API.md) | Routes, temps réel, limites connues |
| [`docs/decisions/`](docs/decisions/) | Fiches de décision |

---

## Démarrage rapide : toute la pile avec Docker

Pour voir le site fonctionner sans rien installer d'autre que Docker : la base,
l'API et l'interface démarrent ensemble, derrière un seul port.

```bash
mkdir agon-cup && cd agon-cup
git clone <adresse du dépôt back>  back
git clone <adresse du dépôt front> front
cd back
docker compose -f docker-compose.complet.yml up --build
```

Quand les trois services sont `healthy` (1 à 3 minutes la première fois, le
temps de construire les images), ouvrir **http://localhost:8080**.

Pour ajouter les comptes et tournois de démonstration, dans un second terminal :

```bash
docker compose -f docker-compose.complet.yml --profile demo run --rm demo
```

La commande affiche les identifiants (`admin@agon-cup.fr`, `joueur01@demo.iut.fr`…)
et quoi essayer avec chacun. Arrêter : `Ctrl+C`, puis
`docker compose -f docker-compose.complet.yml down` (ajouter `-v` pour effacer la base).

| Réglage (variable d'environnement) | Rôle | Défaut |
|---|---|---|
| `PORT_WEB` | Port de l'interface | `8080` |
| `CHEMIN_FRONT` | Dossier du dépôt front | `../front` |
| `FLASK_SECRET_KEY` | Clé de signature des sessions | tirée au hasard à chaque démarrage |

L'interface (nginx) sert le site **et** relaie `/api` et le WebSocket vers l'API :
le navigateur ne parle qu'à `localhost:8080`, ce qui évite tout réglage CORS.
Le serveur de l'API est **gunicorn** (un processus, 100 threads), pas le serveur
de développement de Flask.

Pour **développer** (rechargement automatique, tests), suivre l'installation
ci-dessous : la base seule dans Docker, l'API et le front sur la machine.

---

## Prérequis

- **Docker** (Docker Desktop sous Windows ou macOS) — pour PostgreSQL
- **Python 3.11 ou plus récent**
- **Git**

Rien d'autre : PostgreSQL n'est **pas** à installer sur la machine.

---

## Installation

### 1. Base de données

```bash
docker compose up -d
```

PostgreSQL 16 démarre, crée la base `tournois` et joue automatiquement les
scripts du dossier `sql/` : le schéma, puis la suite de tests d'intégrité.

Vérifier qu'elle tourne :

```bash
docker compose ps        # r5a5_db doit être « healthy »
```

Une interface d'inspection (Adminer) est disponible sur `http://localhost:8080` :
serveur `db`, utilisateur `r5a5`, mot de passe `r5a5`, base `tournois`.

### 2. Environnement Python

```bash
python -m venv .venv
```

Activation :

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Installation des dépendances :

```bash
python -m pip install -r requirements.txt
```

> Toujours `python -m pip` plutôt que `pip`, et `python -m flask` plutôt que
> `flask` : voir [Dépannage sous Windows](#dépannage-sous-windows).

### 3. Configuration

```bash
cp .env.example .env
```

Les valeurs par défaut conviennent au docker-compose fourni. Seule
`FLASK_SECRET_KEY` doit être remplacée ; en générer une avec :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

L'API **refuse de démarrer** si la clé fait moins de 32 caractères ou si c'est
encore la valeur du modèle (`a-remplacer…`) : une clé devinable permettrait de
fabriquer de faux jetons.

Le fichier `.env` n'est jamais versionné.

---

## Lancement

```bash
python -m project_organizer
```

| Adresse | Rôle |
|---|---|
| `http://localhost:5000/health` | État de l'API et de la base |
| `http://localhost:5000/apidoc/swagger` | Documentation interactive de l'API |

L'API écoute sur `127.0.0.1` (la machine seulement) ; `HOTE=0.0.0.0` l'ouvre au
réseau local, ce qu'il ne faut faire qu'en connaissance de cause. Le mode debug
de Flask ne s'active qu'avec `FLASK_DEBUG=true`.

Si `/health` répond `"statut": "ok"` avec `"tables": 9`, tout est en place.

---

## Comptes et données de démonstration

Pour essayer le site avec des comptes déjà prêts (**local uniquement**) :

```bash
python scripts/donnees_demo.py
```

Le script crée un administrateur, 40 joueurs et dix tournois (six à des étapes différentes — inscriptions ouvertes, closes, en cours, terminé… — et quatre sans équipe, pour montrer le catalogue de jeux), puis affiche les identifiants et quoi essayer avec quel compte. Il est rejouable ; `--reinitialiser` supprime les tournois de démonstration puis les recrée. Il refuse de tourner si `COOKIE_SECURE=true` (ses mots de passe sont publics).

Le catalogue compte **douze jeux** avec leurs vrais postes (top, jungle, mid, ADC et support pour League of Legends ; tank, DPS et heal à six pour Overwatch 2 ; positions 1 à 5 pour Dota 2 ; un seul poste pour les duels comme les échecs). Il est défini dans `sql/schema_R5A5_sujetB.sql`, section 10, donc créé avec la base : sur une base existante, `docker compose down -v && docker compose up -d`.

| Profil | Comment l'obtenir |
|---|---|
| Visiteur | Rien à faire : ne pas se connecter |
| Joueur | S'inscrire sur `/inscription`, ou utiliser `joueur01@demo.iut.fr` |
| Capitaine | Un joueur qui crée une équipe dans un tournoi aux inscriptions ouvertes |
| Administrateur | `admin@agon-cup.fr`, ou promouvoir un compte : `docker compose exec db psql -U r5a5 -d tournois -c "UPDATE utilisateur SET est_administrateur = TRUE WHERE pseudo = 'monpseudo';"` puis recharger la page |

Pour tester plusieurs profils en même temps, utiliser des fenêtres de navigation privée distinctes (le cookie de session est partagé dans une même fenêtre).

---

## Tests

```bash
python -m pytest
```

Les tests notés portent sur les **droits d'accès** : pour chaque règle du
sujet, un test vérifie qu'un utilisateur non autorisé est bien refusé.

Les contraintes d'intégrité de la base ont leur propre suite, rejouée à chaque
création du conteneur. Pour la relancer à la main :

```bash
docker compose exec -T db psql -U r5a5 -d tournois -v ON_ERROR_STOP=1 < sql/tests_contraintes.sql
```

---

## Commandes utiles

| Besoin | Commande |
|---|---|
| Voir les logs de la base | `docker compose logs -f db` |
| Arrêter la base | `docker compose down` |
| Repartir d'une base vide | `docker compose down -v && docker compose up -d` |
| Ouvrir un terminal SQL | `docker compose exec db psql -U r5a5 -d tournois` |

> Le dossier `sql/` n'est rejoué **qu'à la création** du volume. Après une
> modification du schéma, `docker compose up` ne suffit pas : utiliser
> `docker compose down -v`.

---

## Dépannage sous Windows

**« Une stratégie de contrôle d'application a bloqué ce fichier »**

Le contrôle d'application de Windows peut bloquer les exécutables générés dans
`.venv\Scripts\` (`pip.exe`, `flask.exe`…). Les appeler à travers Python
contourne le problème, sans rien désactiver :

```bash
python -m pip install -r requirements.txt
python -m project_organizer
```

**Pilote PostgreSQL**

Le projet utilise `pg8000`, un pilote écrit entièrement en Python. Le pilote
habituel, `psycopg`, embarque une bibliothèque native que la même protection
bloque. Rien à faire : c'est déjà configuré.

**PowerShell refuse d'activer l'environnement virtuel**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Le port 5432 est déjà utilisé**

Un autre PostgreSQL tourne sur la machine. Dans `docker-compose.yml`, remplacer
`"5432:5432"` par `"5433:5432"`, puis ajuster le port dans `DATABASE_URL`.
