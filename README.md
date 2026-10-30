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

## Versions utilisées

Ce sont celles avec lesquelles le projet est testé (plus de 300 tests du back,
tests du front, parcours dans un vrai navigateur). D'autres versions
récentes fonctionneront sans doute, mais elles n'ont pas été vérifiées.

| Outil | Version | Où elle intervient |
|---|---|---|
| Docker Desktop | version récente, avec `docker compose` (v2) | Lancement de toute la pile, ou de la base seule |
| Python | **3.13** | Back (l'image Docker utilise `python:3.13-slim`) |
| PostgreSQL | **16** | Base de données (image `postgres:16`, rien à installer) |
| Node.js | **22** (npm 10) | Front en développement (l'image Docker utilise `node:22-alpine`) |
| Flask / Flask-SocketIO | 3.1.3 / 5.6.1 | API et temps réel (Socket.IO) |
| SQLAlchemy / pg8000 | 2.0.54 / 1.31.5 | Accès à la base |
| React / Vite / TypeScript | 19 / 8.3.5 / 6.0 | Interface |
| Git | récent | Clonage des deux dépôts |

Les dépendances exactes sont figées dans `requirements.txt` (back) et
`package-lock.json` (front).

---

## Démarrage rapide sous Windows : toute la pile avec Docker

C'est le chemin recommandé pour **voir le site fonctionner** (par exemple pour la
correction). Il ne demande que **Docker Desktop** (démarré, avec l'intégration
WSL 2 activée, qui est le réglage par défaut) et **Git**. Ni Python, ni Node, ni
PostgreSQL à installer. Commandes à lancer dans **PowerShell** :

```powershell
mkdir agon-cup
cd agon-cup
git clone https://github.com/DUT-Info-Montreuil/R5A5_2026_SUJETB_GUERREIROMARQUES_ZAPOI_BACK.git back
git clone https://github.com/DUT-Info-Montreuil/R5A5_2026_SUJETB_GUERREIROMARQUES_ZAPOI_FRONT.git front
cd back
docker compose -f docker-compose.complet.yml up --build
```

Les deux dépôts doivent être **côte à côte** (`back` et `front` dans le même
dossier) : le Compose du back construit l'image du front depuis `..\front`.
(PowerShell 5 ne comprend pas `&&` : les commandes sont donc sur des lignes séparées.)

Attendre que les trois services (`db`, `api`, `front`) soient `healthy` : 1 à 3
minutes la première fois, le temps de construire les images. Puis ouvrir
**http://localhost:8080**.

Pour ajouter les comptes et tournois de démonstration, dans **un second
PowerShell**, depuis le dossier `back` :

```powershell
docker compose -f docker-compose.complet.yml --profile demo run --rm demo
```

La commande affiche les identifiants (`admin@agon-cup.fr`, `joueur01@demo.iut.fr`…)
et quoi essayer avec chacun. Le chargement dure une à deux minutes. Sans lui, le
site est **vide** : ni jeux joués, ni équipes, ni tournois. (Les douze jeux, eux,
sont toujours là.)

Arrêter : `Ctrl+C`, puis `docker compose -f docker-compose.complet.yml down`
(ajouter `-v` pour effacer la base et repartir de zéro).

| Réglage | Rôle | Défaut |
|---|---|---|
| `PORT_WEB` | Port de l'interface | `8080` |
| `CHEMIN_FRONT` | Dossier du dépôt front | `../front` |
| `FLASK_SECRET_KEY` | Clé de signature des sessions | tirée au hasard à chaque démarrage |

Pour changer un réglage sous PowerShell : `$env:PORT_WEB = "8090"` avant la
commande `docker compose`.

L'interface (nginx) sert le site **et** relaie `/api` et le WebSocket vers l'API :
le navigateur ne parle qu'à `localhost:8080`, ce qui évite tout réglage CORS.
Le serveur de l'API est **gunicorn** (un processus, 100 threads), pas le serveur
de développement de Flask.

> **Mise à jour du code.** Après un `git pull` dans les deux dossiers, relancer
> `docker compose -f docker-compose.complet.yml up --build`. Si le schéma ou le
> catalogue de jeux a changé : `down -v` d'abord (le dossier `sql/` n'est rejoué
> qu'à la création de la base).

> **Fins de ligne.** Le dépôt contient un `.gitattributes` qui force les fins de
> ligne Unix (LF) pour `docker-entrypoint.sh`, les scripts SQL et les
> configurations. Sans lui, Git pour Windows les convertit en CRLF et le conteneur
> de l'API ne démarre pas (`no such file or directory`). Si vous aviez cloné le
> dépôt **avant** l'ajout de ce fichier : `git rm --cached -r .` puis
> `git reset --hard`, ou simplement recloner.

Pour **développer** (rechargement automatique, tests), suivre l'installation
ci-dessous : la base seule dans Docker, l'API et le front sur la machine.

---

## Prérequis (développement)

- **Docker Desktop** — pour PostgreSQL
- **Python 3.13**
- **Node.js 22** — pour le front, voir son dépôt
- **Git**

PostgreSQL n'est **pas** à installer sur la machine.

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
serveur `db`, utilisateur `r5a5`, mot de passe `r5a5`, base `tournois`. Elle prend
le même port que l'interface de la pile complète : ne pas lancer les deux ensemble
(ou changer `PORT_WEB`).

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

Le script crée un administrateur, 40 joueurs et treize tournois (six à des étapes différentes — inscriptions ouvertes, closes, en cours, terminé… —, deux ouverts sans équipe, deux en solo, et trois de plus pour que le palmarès et le direct aient du contenu), puis affiche les identifiants et quoi essayer avec quel compte. Il est rejouable ; `--reinitialiser` supprime les tournois de démonstration puis les recrée. Ses mots de passe sont publics : il refuse donc de tourner si `COOKIE_SECURE=true`, ou si la base contient déjà un compte qui n'est pas un compte de démonstration (une base utilisée par de vraies personnes, y compris dans Docker). `--forcer` passe outre ce second contrôle, sur une base locale seulement.

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

**Le site est vide (aucun tournoi, aucune équipe)**

Le back ne charge **jamais** de données tout seul. Les douze jeux viennent du
schéma SQL, à la création de la base ; les comptes et les tournois de démonstration
viennent du script `scripts/donnees_demo.py` (ou, avec Docker, de la commande
`--profile demo run --rm demo`). À lancer une fois.

**« L'API est injoignable » alors que le back est démarré**

Souvent, **un autre programme occupe déjà le port 5000** (une ancienne instance du
back restée en arrière-plan, ou un autre projet). Le nouveau back démarre sans
erreur, mais le navigateur parle à l'ancien. Test : ouvrir
`http://localhost:5000/health`. Une page « Not Found » en HTML, ou du JSON qui ne
commence pas par `{"baseDeDonnees"`, montre que ce n'est pas notre API. Qui occupe
le port, sous PowerShell :

```powershell
Get-NetTCPConnection -LocalPort 5000 | Select-Object LocalAddress, State, OwningProcess
Get-Process -Id <numéro affiché> | Select-Object Id, ProcessName, Path
Stop-Process -Id <numéro> -Force
```

Ou changer de port : `PORT=5001` dans le `.env` du back, et
`VITE_API_URL=http://localhost:5001` dans le `.env` du front.

**Le temps réel ne charge pas (l'arbre ou le chat ne se mettent pas à jour)**

Ouvrir la page `/diagnostic` du front : elle dit si « Temps réel » répond, et
pourquoi sinon. Causes à vérifier, dans cet ordre :

1. **Le site est ouvert à une autre adresse que celle autorisée.** Le back
   n'accepte que `CORS_ORIGINS` (par défaut `http://localhost:5173`) : ouvrir
   `http://localhost:5173`, pas `http://127.0.0.1:5173`.
2. **Le plafond de connexions par adresse est atteint.** L'API limite à 20
   connexions temps réel simultanées par adresse IP (`SOCKET_CONNEXIONS_MAX_PAR_ADRESSE`).
   Après beaucoup de rechargements, ou avec beaucoup d'onglets ouverts, les
   suivantes sont refusées. Le journal du back dit alors
   `Connexion temps réel refusée : trop de connexions depuis cette adresse`.
   Redémarrer le back remet le compteur à zéro ; en développement, on peut aussi
   relever le plafond dans le `.env` (`SOCKET_CONNEXIONS_MAX_PAR_ADRESSE=200`).
3. **Les dépendances ne sont pas à jour.** Après un `git pull` :
   `python -m pip install -r requirements.txt` (le temps réel a besoin de
   `Flask-SocketIO` et de `simple-websocket`).
4. **Un pare-feu ou un antivirus coupe le WebSocket.** Dans la console du
   navigateur (F12, onglet Réseau, filtre « WS »), la connexion `socket.io`
   doit afficher le statut 101. Sinon, noter le message d'erreur.

**Un message « 429 » (trop de requêtes) à la connexion**

La connexion est limitée à 5 essais par minute et par adresse, l'inscription à
10 par heure. Attendre une minute. Un plafond global de 1 200 requêtes par minute et
par adresse existe aussi (`LIMITE_GLOBALE` dans `.env`) : il ne se déclenche que lors d'un
usage anormal, par exemple un script qui boucle.

**Docker : `exec ./docker-entrypoint.sh: no such file or directory`**

Le script a été extrait avec des fins de ligne Windows (CRLF). Voir la note
« Fins de ligne » plus haut : recloner le dépôt, ou `git rm --cached -r .` puis
`git reset --hard`.
