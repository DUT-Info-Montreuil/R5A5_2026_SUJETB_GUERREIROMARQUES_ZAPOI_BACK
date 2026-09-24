# Tournament Organizer — API

API de la plateforme de tournois de l'association étudiante (R5A5, sujet B).

Ce dépôt contient le back-end : une API REST en Flask, un canal temps réel en
WebSocket, et le schéma de la base PostgreSQL. L'interface est dans le dépôt
**`R5A5_2026_SUJETB_GUERREIROMARQUES_ZAPOI_FRONT`**, qui a besoin de cette API
pour fonctionner.

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Organisation du code, règles entre les couches, conventions |
| [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md) | Contrat figé entre le front et le back |
| [`docs/decisions/`](docs/decisions/) | Fiches de décision |

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

Le fichier `.env` n'est jamais versionné.

---

## Lancement

```bash
python -m project_organizer
```

| Adresse | Rôle |
|---|---|
| `http://localhost:5000/health` | État de l'API et de la base |

Si `/health` répond `"statut": "ok"` avec `"tables": 9`, tout est en place.

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
