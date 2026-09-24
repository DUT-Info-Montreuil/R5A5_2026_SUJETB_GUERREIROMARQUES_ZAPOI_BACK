# Tournament Organizer — API (back-end)

L'API de la plateforme de tournois (R5A5, sujet B), en Flask, avec sa base
PostgreSQL. L'interface est dans le dépôt
`R5A5_2026_SUJETB_GUERREIROMARQUES_ZAPOI_FRONT`.

> **Toutes les commandes ci-dessous sont à taper dans PowerShell**, depuis le
> dossier du dépôt — par exemple `C:\Users\fabio\Projets\back`.
> Git Bash ne comprend pas les mêmes commandes : voir [Git Bash](#git-bash).

---

## 1. Installation — une seule fois

Il faut avoir installé **Docker Desktop** (démarré), **Python 3.11+** et **Git**.

**① Démarrer la base de données**

```powershell
docker compose up -d
docker compose ps
```

✅ Attendu : la ligne `r5a5_db` indique `healthy` (compter une dizaine de
secondes, relancer `docker compose ps` si elle indique encore `starting`).

**② Créer l'environnement Python**

```powershell
python -m venv .venv
```

✅ Attendu : un dossier `.venv` apparaît.
❌ `Python est introuvable` → remplacer `python` par `py` pour cette commande.

**③ Activer l'environnement**

```powershell
.\.venv\Scripts\Activate.ps1
```

✅ Attendu : `(.venv)` apparaît au début de la ligne de commande.

**④ Installer les dépendances**

```powershell
python -m pip install -r requirements.txt
```

**⑤ Créer le fichier de configuration**

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

La seconde commande affiche une clé. Ouvrir le fichier `.env` et la coller
après `FLASK_SECRET_KEY=`, à la place de la valeur d'exemple.

Le `.env` ne doit **jamais** être commité : il est déjà dans le `.gitignore`.

---

## 2. À chaque nouveau terminal

Un terminal qui vient de s'ouvrir n'a **pas** l'environnement activé.
Avant toute commande `python` :

```powershell
cd C:\Users\fabio\Projets\back
.\.venv\Scripts\Activate.ps1
```

Si `(.venv)` n'est pas au début de la ligne, les commandes `python` échouent.

> Dans PyCharm, ouvrir ce dossier comme projet : son terminal active
> l'environnement tout seul.

---

## 3. Vérifier que tout fonctionne

Trois vérifications, dans l'ordre. Si les trois sont bonnes, le back est
opérationnel.

**① La base tourne**

```powershell
docker compose ps
```

✅ `r5a5_db` est `healthy`.

**② Les tests passent**

```powershell
python -m pytest
```

✅ `14 passed`.

**③ Le serveur répond**

```powershell
python -m project_organizer
```

Laisser ce terminal ouvert : c'est le serveur, il affiche une ligne à chaque
requête. Ouvrir ensuite dans le navigateur :

| Adresse | ✅ Attendu |
|---|---|
| http://localhost:5000/health | `"statut": "ok"` et `"tables": 9` |
| http://localhost:5000/rien | `"erreur": "Not Found"` |
| http://localhost:5000/apidoc/swagger | La documentation de l'API, avec la route `/health` |

Pour arrêter le serveur : `Ctrl + C` dans son terminal.

---

## 4. En cas de problème

| Message | Cause | Solution |
|---|---|---|
| `Python est introuvable ; exécutez sans arguments…` | L'environnement n'est pas activé | [Section 2](#2-à-chaque-nouveau-terminal). À la toute première installation, utiliser `py` |
| `No module named pytest` (ou `flask`, `pydantic`, `flask_pydantic_spec`…) | Dépendances non installées dans ce `.venv` | `python -m pip install -r requirements.txt` |
| `Variable d'environnement manquante : DATABASE_URL` | Pas de fichier `.env` | Étape ⑤ de l'installation |
| `Une stratégie de contrôle d'application a bloqué…` | Windows bloque `pip.exe` ou `flask.exe` | Toujours passer par `python -m pip`, `python -m pytest`… |
| `Activate.ps1 … n'est pas signé` / exécution désactivée | Politique PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, une seule fois |
| `The container name "/r5a5_db" is already in use` | Un ancien conteneur existe, venant d'un autre dossier | `docker rm -f r5a5_db r5a5_adminer` puis `docker compose up -d` |
| `/health` renvoie `"statut": "degrade"` | La base est arrêtée | `docker compose up -d` |
| `column … version_jeton does not exist` | La base a été créée avec une ancienne version du schéma | [Réinitialiser la base](#réinitialiser-la-base) |
| `"tables": 0` | La connexion vise la mauvaise base | Vérifier `DATABASE_URL` dans `.env` |
| `port is already allocated` sur 5432 | Un autre PostgreSQL tourne sur la machine | Dans `docker-compose.yml`, remplacer `"5432:5432"` par `"5433:5432"`, et le port dans `DATABASE_URL` |
| Le port 5000 est occupé | Un ancien serveur tourne encore | Fermer l'autre terminal, ou `Ctrl + C` dedans |
| La page `/apidoc/swagger` reste blanche | L'interface Swagger est chargée depuis Internet (cdn.jsdelivr.net) | Vérifier la connexion Internet ; la description brute reste lisible sur `/apidoc/openapi.json` |

---

## 5. Commandes utiles

### Réinitialiser la base

Le dossier `sql/` n'est joué **qu'à la création** de la base. Après une
modification du schéma, il faut la recréer — toutes les données sont perdues :

```powershell
docker compose down -v
docker compose up -d
```

### Autres commandes

| Besoin | Commande |
|---|---|
| Arrêter la base (données conservées) | `docker compose down` |
| Voir les logs de la base | `docker compose logs -f db` |
| Ouvrir un terminal SQL | `docker compose exec db psql -U r5a5 -d tournois` |
| Voir la structure d'une table | `docker compose exec db psql -U r5a5 -d tournois -c "\d utilisateur"` |
| Interface web de la base | http://localhost:8080 — serveur `db`, utilisateur `r5a5`, mot de passe `r5a5`, base `tournois` |
| Rejouer les tests d'intégrité SQL | `Get-Content sql\tests_contraintes.sql \| docker compose exec -T db psql -U r5a5 -d tournois -v ON_ERROR_STOP=1` |

---

## 6. Pour aller plus loin

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Où ranger quoi, règles entre les couches, conventions |
| http://localhost:5000/apidoc/swagger | Documentation de l'API, générée depuis le code (serveur démarré) |
| [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md) | Contrat entre le front et le back : règles communes, et routes pas encore implémentées |
| [`docs/decisions/`](docs/decisions/) | Fiches de décision |

Pour ajouter une route, recopier le trajet de `/health`, qui traverse toutes
les couches : `controllers/sante_controller.py` → `services/sante_service.py`
→ `repository/sante_repository.py`, avec `dtos/sante_dto.py` pour les modèles
de réponse. La liste de contrôle complète est au §12 de `ARCHITECTURE.md`.

---

## Git Bash

Si vous utilisez Git Bash au lieu de PowerShell, trois commandes changent :

| PowerShell | Git Bash |
|---|---|
| `.\.venv\Scripts\Activate.ps1` | `source .venv/Scripts/activate` |
| `Copy-Item .env.example .env` | `cp .env.example .env` |
| `Get-Content sql\tests_contraintes.sql \| docker compose exec …` | `docker compose exec -T … < sql/tests_contraintes.sql` |

Sur macOS ou Linux, même chose, avec `source .venv/bin/activate`.