# CLAUDE.md — Back-end (API Flask) · R5A5 sujet B « Plateforme de tournois »

Ce fichier est lu par Claude à chaque session. Il fixe **comment on travaille**
et **ce qu'il faut savoir du projet**. Les règles de la section 1 passent avant
tout le reste, y compris avant une demande qui les contredirait : dans ce cas,
Claude le signale et demande confirmation.

---

## 1. Règles de travail (non négociables)

### Communication
1. **Parler en français**, partout : réponses, commentaires de code, messages
   de commit, descriptions de PR, documentation.
2. **Toujours expliquer ce qu'on fait** : avant une série d'actions, dire en
   une ou deux phrases ce qui va être fait et pourquoi ; à la fin, dire ce qui
   a été fait, ce qui a été vérifié, et ce qui reste. Ne jamais enchaîner des
   modifications en silence.
3. **Dire la vérité sur l'état du travail.** Un test qui échoue, une étape
   sautée, une hypothèse non vérifiée : on le dit, avec la sortie du test. Ne
   jamais annoncer « ça marche » sans l'avoir exécuté.
4. En cas de doute sur le besoin, **poser la question** plutôt que deviner. Si
   le sujet est flou, c'est à l'enseignant qu'il faut la poser (le dire à
   l'étudiant), pas à Claude de trancher.

### Git et pull requests
5. **Jamais de commit ni de push directement sur `main` ni sur `develop`.**
6. **Toute modification passe par une branche et une pull request** — même
   une correction d'une ligne, même de la documentation. Une branche par
   fonctionnalité : `feat/…`, `fix/…`, `docs/…`, `test/…`.
7. **Ne jamais fusionner une PR soi-même.** La fusion est relue et décidée par
   l'autre membre du binôme. Ne jamais faire de `push --force`, `reset --hard`
   ou réécriture d'historique sur une branche partagée.
8. **Ne créer une PR que si l'étudiant le demande** (ou s'il l'a demandé pour
   la tâche en cours). Elle explique le **pourquoi**, liste ce qui change, et
   dit comment tester. Si le dépôt a un modèle de PR, le suivre.
9. Commits petits et ciblés, au format `type(portée): description` —
   ex. `feat(equipe): exclusion d'un membre`. Jamais de `git add .` à
   l'aveugle : relire `git status` et `git diff --staged` avant de valider.

### Secrets
10. **Ne jamais committer de secret** : mot de passe, clé de signature
    (`FLASK_SECRET_KEY`), jeton, cookie de session, chaîne de connexion avec
    identifiants réels, fichier `.env`. Seul `.env.example` est versionné, avec
    des valeurs **factices**.
11. Avant chaque commit, relire le diff à la recherche de secrets. Si un secret
    a été committé par erreur : **prévenir immédiatement** l'étudiant (le
    supprimer du dernier commit ne suffit pas, il faut le considérer comme
    compromis et le changer).
12. Ne jamais afficher, journaliser ni renvoyer au client un mot de passe, un
    jeton, un en-tête `Authorization`, une adresse e-mail ou un message
    d'erreur technique (trace, hôte, message de la base).

### Actions risquées — demander d'abord
13. Demander confirmation avant : `docker compose down -v` (efface les
    données), toute modification de `sql/schema_R5A5_sujetB.sql` (la base doit
    être recréée), suppression de fichiers, changement de version d'une
    dépendance, modification du contrat d'API.

### Travail rendu à l'enseignant
14. **Les fiches de décision (`docs/decisions/`) et le rapport sur l'IA ne
    doivent pas être rédigés par Claude.** Le sujet note cette partie 3/3 et
    annonce **0/3 pour du texte générique produit par une IA**. Claude peut
    relire, signaler des fautes, poser des questions pour faire émerger le
    raisonnement, vérifier les faits techniques — mais le texte est celui de
    l'étudiant, avec ses mots, ses hésitations et ses coûts réels.
15. Ne pas inventer de comportement : toute route ou règle doit venir du sujet
    (exigences B-01 à B-19) ou du contrat d'API. Sinon, proposer et demander.

---

## 2. Le projet en deux minutes

- **Sujet B** : plateforme de tournois e-sport en équipes de 5, arbre à
  élimination directe de 8 équipes, chat d'équipe, suivi en direct.
  Notation sur 20, sans plafond (sujet B). Rendu : ~15 jours après le
  2026-10-15.
- **Deux dépôts** : ce back (`…_BACK`) et le front (`…_FRONT`, React + TS).
  Le **contrat d'API** `docs/CONTRAT_API.md` est identique dans les deux :
  toute modification se répercute des deux côtés dans le même mouvement.
- **Pile** : Flask 3.1, SQLAlchemy 2 + pg8000, PostgreSQL 16 (Docker),
  Pydantic 2 + flask-pydantic-spec (validation **et** doc OpenAPI),
  Flask-SocketIO (temps réel), flask-jwt-extended (jeton en cookie HttpOnly),
  argon2-cffi, Flask-Limiter, pytest.
- **Barème** : architecture 4 · droits d'accès 3 · temps réel 4 · docs
  développeur + API 2 · journalisation 2 · tests 1 · décisions + rapport IA 3 ·
  UX 1. Les tests visés sont des **tests de sécurité** : pour chaque règle
  d'accès, un test qui prouve qu'un utilisateur non autorisé est refusé.

### Où en est-on (branche `feature/tournois`)

| Domaine | État |
|---|---|
| Authentification (inscription, connexion, `moi`, déconnexion), cookie HttpOnly, révocation par `version_jeton` | ✅ |
| Tournois : liste, détail, création, machine à états, équipes inscrites, arbre | ✅ |
| Rencontres : saisie d'un résultat (normal, forfait, qualification directe) + propagation dans l'arbre | ✅ |
| Temps réel : salon `tournoi:{id}`, événements `tournoi:maj` et `rencontre:maj` | ✅ |
| **Équipes** : création, renommage, demandes d'adhésion, rôles, exclusion, passation du capitanat (B-05 à B-11) | ⏳ tables SQL prêtes (`equipe`, `composer`, `demande_adhesion`, `role_jeu`) ; modèles ORM `Equipe` et `Composer` seulement ; aucune route d'écriture |
| **Espace d'échange** : messages d'équipe, salon `equipe:{id}`, `equipe:acces-revoque` (B-16 à B-18) | ⏳ table SQL `message` prête ; ni modèle ORM, ni route, ni événement |
| Disqualification (`PATCH /api/equipes/{id}`, B-15) | ⏳ |
| Fiches de décision, rapport IA | ⏳ à écrire **par l'étudiant** |

Le détail route par route est dans [`API.md`](API.md).

---

## 3. Commandes

Tout se lance depuis la racine du dépôt, environnement Python activé
(`.venv`). Les commandes passent toujours par `python -m …`.

| Besoin | Commande |
|---|---|
| Démarrer la base | `docker compose up -d` (attendre `healthy`) |
| Installer | `python -m pip install -r requirements.txt` |
| Configurer | copier `.env.example` en `.env`, y mettre une clé : `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| **Lancer les tests** | `python -m pytest` — la base doit tourner |
| Lancer le serveur | `python -m project_organizer` → http://localhost:5000 |
| Documentation Swagger | http://localhost:5000/apidoc/swagger |
| Tests d'intégrité SQL | voir README, section « Tests » |
| Données de démo (local seulement) | `sql/donnees_demo.sql`, joué à la main |
| Réinitialiser la base | `docker compose down -v && docker compose up -d` — **demander d'abord** |

**Avant toute PR** : `python -m pytest` doit passer en entier, et la nouvelle
route doit apparaître dans Swagger avec **tous** ses codes d'erreur.

---

## 4. Architecture — à respecter

Détail dans `docs/ARCHITECTURE.md`. L'essentiel :

```
controllers/ ─┐
sockets/     ─┴─▶ services/ ──▶ repository/ ──▶ models/        utils/ : accessible à tous
```

- **`controllers/`** : un Blueprint par ressource ; lit la requête, appelle
  **un** service, renvoie un DTO. Aucune règle métier, aucun SQL.
- **`services/`** : toutes les règles du sujet (droits, transitions d'état,
  transactions). **Jamais** d'import `flask.request`, de `jsonify`, de code HTTP.
- **`repository/`** : lectures/écritures. Jamais d'exception HTTP, jamais de
  règle métier.
- **`models/`** : classes ORM des tables **existantes**. Jamais
  `Base.metadata.create_all()` : `sql/schema_R5A5_sujetB.sql` est la source de
  vérité du schéma (on le modifie d'abord, puis le modèle).
- **`sockets/`** : comme un contrôleur, appelle les services ; les services
  émettent via `sockets/diffusion.py` **après** la validation de la
  transaction (jamais avant : un rollback annoncerait un état qui n'existe pas).
- **`dtos/`** : Pydantic. `ModeleEntree` (corps de requête, champ inconnu → 400),
  `ModeleApi` (réponses, camelCase en JSON / snake_case en Python),
  `ErreurDto`. La traduction camelCase ↔ snake_case n'a lieu que dans `dtos/base.py`.

**Ajouter une fonctionnalité** (ordre à suivre) : contrat d'API → `dtos/` →
`repository/` → `services/` → `controllers/` → `sockets/` si besoin →
`tests/` (au moins un test de refus) → `@spec.validate(...)` avec tous les codes.
Modèle à recopier : le trajet de `/health`, ou `tournoi_*` pour une ressource complète.

### Conventions de code
- Métier en français (`equipe`, `rencontre`, `capitaine`), termes techniques
  établis en anglais (`controller`, `repository`).
- Fichiers : `<ressource>_controller.py`, `_service.py`, `_repository.py`, `_dto.py`.
- Pas de nombre magique : une constante nommée.
- Commentaires : le **pourquoi**, jamais le quoi.
- Les erreurs métier se lèvent avec `utils/erreurs.py` (`BadRequest`,
  `Forbidden`, `NotFound`, `Conflict`, `UnprocessableEntity`) ; le format
  `{ "erreur", "detail" }` est unique.

---

## 5. Sécurité et droits d'accès (3 points + tests)

- **Refuser par défaut** : toute route exige un jeton, sauf `@publique`
  (posé juste sous `@bp.get`/`@bp.post`). Toute nouvelle route publique
  s'ajoute **aussi** à `ROUTES_PUBLIQUES` dans `tests/test_protection.py`.
- **Trois niveaux** : jeton (`before_request`) → rôle (`@administrateur_requis`)
  → droit sur la ressource (dans le **service** : capitaine de *cette* équipe,
  membre de *cette* équipe).
- **Aucun droit dans le jeton.** Tout est relu en base à chaque requête, y
  compris `ver` comparé à `utilisateur.version_jeton` (révocation).
- **Codes** : 401 non authentifié · 403 ressource publique mais action interdite
  · 404 ressource invisible pour l'appelant (espace d'échange d'une équipe dont
  on n'est pas membre) · 409 conflit d'**état** (inscriptions closes) ·
  422 violation de **règle métier** (poste occupé, joueur déjà dans une équipe).
- **`PATCH` : liste blanche de champs par rôle.** Tout champ hors liste, ou
  inconnu, fait échouer la requête **entière** en 400. Un capitaine qui envoie
  `statutEquipe` ne doit rien obtenir — et un test le prouve.
- **Une seule fonction de règle d'accès à l'espace d'échange**, appelée par
  la route de lecture, la route d'écriture **et** le gestionnaire WebSocket.
- **Jamais de SQL construit par concaténation** : paramètres liés
  (`text(...)` avec `:nom`) ou ORM.
- Mots de passe : argon2, 12 caractères minimum ; connexion/inscription limitées
  à 5 par minute ; même message d'erreur que l'e-mail existe ou non.

---

## 6. Temps réel (4 points) — règles tirées du cours

Choix du projet : **Flask-SocketIO** (chat bidirectionnel + salons natifs).
Voir la fiche de décision n° 02 (à rédiger par l'étudiant). Rappel du cours :
polling < SSE < WebSocket < Socket.IO < WebRTC en complexité ; on ne prend le
canal bidirectionnel que si le besoin le justifie. Ici : SSE suffirait pour le
suivi du tournoi (B-19), mais le chat (B-16) a besoin des deux sens.

À respecter dans le code :

1. **Les écritures restent en HTTP** (`POST /api/equipes/{id}/messages`) : on
   garde validation, codes de statut, journalisation, doc d'API. Le socket sert
   à **notifier** (`message:nouveau`), pas à créer.
2. **Authentifier à la connexion ET à chaque abonnement.** Le cookie `jeton`
   est joint par le navigateur ; un contrôle fait seulement à l'ouverture ne
   suffit pas (droits qui changent, jeton expiré).
3. **IDOR sur les salons** : le client peut demander n'importe quel
   `idEquipe`. L'identité vient de la **connexion authentifiée**, jamais du
   message ; appartenance à l'équipe vérifiée avant `join_room`, et revérifiée
   à l'envoi.
4. **B-17 : exclure ne suffit pas de supprimer la ligne.** Émettre
   `equipe:acces-revoque` **et** retirer le socket du salon (`leave_room`).
5. **Origin** : `cors_allowed_origins` doit rester une liste explicite (jamais
   `*`) — les WebSockets échappent au CORS classique, c'est le « CSRF des
   WebSockets ».
6. **Snapshot puis deltas** : après reconnexion, les événements émis pendant la
   coupure sont perdus (pas de `Last-Event-ID` en WebSocket). Le client relit
   l'état par HTTP, et **rejoint à nouveau ses salons** à chaque `connect`.
7. **Charges = objet complet** (contrat §7) ; ne jamais y mettre de donnée
   sensible. Taille des messages bornée (1 Mio pour le corps HTTP aujourd'hui) ;
   à prévoir : longueur max d'un message de chat, débit limité par connexion.
8. **Heartbeat / ping** à une période inférieure au `proxy_read_timeout` du
   proxy (60 s par défaut sous Nginx ; Socket.IO envoie le sien toutes les 25 s).
9. **Production** (si on déploie derrière Nginx) : en-têtes `Upgrade` /
   `Connection "upgrade"` pour `/socket.io/`, `proxy_buffering off` pour tout
   flux, arrêt progressif du serveur, reconnexion avec délai croissant aléatoire.
10. **Mode asynchrone** : `async_mode="threading"` (dev). Une connexion = un
    thread ; suffisant pour un tournoi d'une soirée, à justifier à l'oral.

---

## 7. Journalisation (2 points)

Sortie standard, JSON une ligne par événement (`LOG_FORMAT=texte` en dev).
Journaliser **toujours** : chaque requête (méthode, chemin, statut, durée,
`idUtilisateur`, `idRequete`) et chaque événement de sécurité (401, 403,
connexion échouée, exclusion, disqualification, transition d'état).
**Jamais** : mot de passe, jeton, `Authorization`, e-mail, corps de requête.
Utiliser `logger.info("…", extra={"contexte": {...}})`, pas `print`.

---

## 8. Tests

- `python -m pytest` (base PostgreSQL requise ; `tests/conftest.py` fournit
  `client`, `inscrire` et le nettoyage des comptes `test_*`).
- **Pour chaque règle d'accès du sujet** : un test « refusé » (401/403/404
  selon le contrat) **et** un test « autorisé ». On teste la sécurité, pas
  seulement le fonctionnel.
- Toute règle de PATCH par champ : un test par champ interdit.
- Un test qui échoue n'est **jamais** désactivé, ignoré ni supprimé pour passer
  au vert : on corrige le code ou on discute du test.

---

## 9. Ne pas faire

- ❌ Contourner `@publique` / `@administrateur_requis` ou ajouter une route
  sans test de refus.
- ❌ Déduire un droit d'un champ envoyé par le client (`idUtilisateur` dans le
  corps, rôle dans le jeton).
- ❌ Émettre un événement temps réel avant le `commit` de la transaction.
- ❌ Écrire de la logique métier dans un contrôleur, un socket ou un repository.
- ❌ Modifier le schéma SQL sans le modèle ORM correspondant (et inversement),
  ou sans prévenir qu'il faut recréer la base.
- ❌ Ajouter une dépendance sans la figer dans `requirements.txt`.
- ❌ Rédiger à la place de l'étudiant les fiches de décision ou le rapport IA.
