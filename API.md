# API.md — Documentation de l'API (back-end)

API REST + WebSocket de la plateforme de tournois (R5A5, sujet B).
Ce document dit **ce que fait l'API aujourd'hui**, route par route, et ce qui
reste à faire. Il ne remplace pas deux autres sources :

| Source | À utiliser pour |
|---|---|
| **Swagger** — http://localhost:5000/apidoc/swagger (serveur démarré) | Les schémas exacts (corps, réponses, codes d'erreur), générés **depuis le code** : ils ne peuvent pas mentir. Brut : `/apidoc/openapi.json` |
| [`docs/CONTRAT_API.md`](docs/CONTRAT_API.md) | Les règles transverses et les décisions (identique dans le dépôt front). Version 5 |
| `API.md` (ce fichier) | Vue d'ensemble, démarrage rapide, état d'avancement, temps réel |

> Branche documentée : `feature/tournois` (la plus avancée, elle contient
> l'authentification). Légende : ✅ implémenté et testé · ⏳ prévu au contrat,
> pas encore codé.

---

## 1. Démarrage rapide

| | |
|---|---|
| URL de base | `http://localhost:5000` (variable `PORT`) |
| Format | JSON, UTF-8, champs en **camelCase** |
| Authentification | Cookie `jeton` (`HttpOnly`, `SameSite=Lax`), posé par la connexion |
| Origines autorisées (CORS) | Liste `CORS_ORIGINS` du `.env` — `http://localhost:5173` par défaut |
| Temps réel | Socket.IO sur la même URL (§5) |

Pour que le navigateur envoie le cookie, le front appelle `fetch` avec
`credentials: 'include'`. Avec `curl`, on garde le cookie dans un fichier :

```bash
# 1. Créer un compte (ou /connexion) : le cookie est écrit dans cookies.txt
curl -c cookies.txt -X POST http://localhost:5000/api/auth/inscription \
  -H 'Content-Type: application/json' \
  -d '{"pseudo":"alice","email":"alice@iut.fr","motDePasse":"une phrase assez longue"}'

# 2. Appeler une route protégée en renvoyant le cookie
curl -b cookies.txt http://localhost:5000/api/auth/moi

# 3. Une route publique n'a pas besoin de cookie
curl "http://localhost:5000/api/tournois?statut=EN_COURS"
```

Compte administrateur de démonstration : voir `sql/donnees_demo.sql`
(**développement local uniquement**, jamais sur une base partagée).

---

## 2. Conventions

### Erreurs — une seule forme

```json
{ "erreur": "Conflict", "detail": "Transition impossible : EN_COURS → INSCRIPTIONS_OUVERTES." }
```

Pour un corps de requête invalide, `detail` liste les champs fautifs :

```json
{ "erreur": "Bad Request", "detail": { "champs": [ { "champ": "foo", "message": "Extra inputs are not permitted" } ] } }
```

Toute erreur imprévue renvoie un `500` générique : la trace reste dans les logs.

### Codes HTTP

| Code | Sens dans ce projet |
|---|---|
| 200 / 201 / 204 | Succès / créé / succès sans contenu |
| 400 | Charge invalide, **champ inconnu**, ou champ non modifiable par l'appelant. Toute la requête est rejetée |
| 401 | Pas de session, session expirée, falsifiée ou **révoquée** |
| 403 | La ressource est **publique**, mais l'**action** est interdite (ex. un joueur veut clore un tournoi) |
| 404 | Ressource inexistante, **ou invisible** pour l'appelant (ex. espace d'échange d'une équipe dont on n'est pas membre) |
| 409 | Conflit avec l'**état** : transition impossible, rencontre déjà jouée, pseudo pris |
| 413 | Corps de requête de plus de 1 Mio |
| 422 | Violation d'une **règle métier** : vainqueur qui ne joue pas la rencontre, poste déjà occupé… |
| 429 | Plus de 5 tentatives de connexion/inscription par minute et par adresse |

409 pour ce qui dépend du **cycle de vie** du tournoi, 422 pour ce qui dépend
des **règles de composition ou de jeu**.

### Autres règles

- Un champ sans valeur est **omis** de la réponse (jamais `null`) : `equipeB`
  absent = « pas encore d'équipe ».
- Dates en ISO 8601 (UTC en sortie : `2026-09-01T16:00:00Z`).
- Chaque réponse porte `X-Request-Id` : à donner pour retrouver la ligne de log.
- Chaque réponse porte `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
  et une `Content-Security-Policy` stricte (sauf la page Swagger).
- `PATCH` : liste blanche de champs **par rôle** ; un champ hors liste → 400.

---

## 3. Authentification

Le jeton est un JWT signé (HS256) **dans un cookie `HttpOnly`** : le JavaScript
de la page ne peut pas le lire. Il contient `sub` (identifiant) et `ver`
(version du jeton), **aucun droit**. À chaque requête, l'API relit
l'utilisateur en base : droits d'administrateur à jour, et jeton rejeté si
`ver` ≠ `utilisateur.version_jeton` (révocation instantanée).

| Route | Accès | Réponse |
|---|---|---|
| `POST /api/auth/inscription` ✅ | Public, 5/min | `201 { utilisateur }` + cookie · `400` (pseudo 3–50 caractères `A-Za-z0-9_.-`, mot de passe **12 caractères minimum**) · `409` pseudo ou e-mail pris · `429` |
| `POST /api/auth/connexion` ✅ | Public, 5/min | `200 { utilisateur }` + cookie · `401` **même message** que l'e-mail soit inconnu ou le mot de passe faux · `429` |
| `GET /api/auth/moi` ✅ | Connecté | `200 Utilisateur` — sert au front à restaurer la session au chargement |
| `POST /api/auth/deconnexion` ✅ | Public | `204`, cookie effacé (publique pour qu'une session expirée puisse se fermer) |

`Utilisateur` = `{ idUtilisateur, pseudo, email, estAdministrateur }`.

**Durée de validité** : 12 heures, **portée par le jeton lui-même** (claim
`exp`). Le cookie, lui, est posé avec un `Max-Age` d'environ un an (valeur par
défaut de flask-jwt-extended quand `JWT_SESSION_COOKIE=False`) : passé 12 h,
le navigateur renvoie encore le cookie, mais l'API répond `401` et l'efface.
Le contrat (§2) annonce `Max-Age=43200` : l'écart est sans danger pour la
sécurité, mais à aligner (voir §7).

---

## 4. Routes

### Tournois et jeux

| Route | Accès | Exigence | Codes | |
|---|---|---|---|---|
| `GET /api/tournois` | Public | B-02 | 200 | ✅ |
| `GET /api/tournois/{id}` | Public | B-02 | 200, 404 | ✅ |
| `POST /api/tournois` | Administrateur | B-01 | 201, 400, 401, 403, 422 | ✅ |
| `PATCH /api/tournois/{id}` | Administrateur | B-03, B-04, B-12 | 200, 400, 401, 403, 404, 409, 422 | ✅ |
| `GET /api/tournois/{id}/equipes` | Public | B-02 | 200, 404 | ✅ |
| `GET /api/tournois/{id}/arbre` | Public | B-12, B-19 | 200, 404 | ✅ |
| `GET /api/jeux` | Public | B-01 | 200 | ✅ |

**`GET /api/tournois`** — paramètres facultatifs `recherche` (texte dans le nom,
150 caractères max) et `statut` (`INSCRIPTIONS_OUVERTES`, `INSCRIPTIONS_CLOSES`,
`EN_COURS`, `TERMINE`). Ordre : en cours, inscriptions ouvertes, inscriptions
closes, terminés ; les plus récents d'abord dans chaque groupe.

```json
[{ "idTournoi": 38, "nomTournoi": "Coupe Inter-IUT — Automne 2026",
   "jeu": { "idJeu": 1, "nomJeu": "League of Legends", "joueursParEquipe": 5 },
   "statutTournoi": "EN_COURS", "nombreEquipes": 8, "nombreEquipesInscrites": 8,
   "creeLe": "2026-09-01T16:00:00Z" }]
```

`GET /api/tournois/{id}` renvoie le même objet, plus `inscriptionsClosesLe`,
`demarreLe`, `termineLe` quand ces étapes sont atteintes. C'est aussi la
réponse de `POST` et `PATCH`, et la charge de l'événement `tournoi:maj`.

**`POST /api/tournois`** — `{ "nomTournoi": "…", "idJeu": 1, "nombreEquipes": 8 }`.
`nombreEquipes` vaut 8 par défaut (2, 4 ou 16 acceptés). Le tournoi naît
`INSCRIPTIONS_OUVERTES`. `422` si le jeu n'existe pas.

**`PATCH /api/tournois/{id}`** — champs `nomTournoi` et/ou `statutTournoi`
(au moins un, sinon `400`). Changer `statutTournoi` **déclenche une transition
d'état et ses effets, dans une seule transaction** :

| Transition | Effets | Refus |
|---|---|---|
| `INSCRIPTIONS_OUVERTES` → `INSCRIPTIONS_CLOSES` | Fige les équipes, génère l'arbre, placement des équipes par tirage au sort (B-03, B-12) | `409` si moins de 2 équipes ou plus d'équipes que de places |
| `INSCRIPTIONS_CLOSES` → `EN_COURS` | Équipes incomplètes → `ELIMINEE`, forfait pour leur adversaire (B-04) | `422` si moins de 2 équipes complètes |
| `EN_COURS` → `TERMINE` | Le vainqueur de la finale devient `VAINQUEUR` | `409` tant que la finale n'a pas de vainqueur |

Toute autre transition → `409`. Une transition émet `tournoi:maj`.

**`GET /api/tournois/{id}/equipes`** — par ordre d'inscription :

```json
[{ "idEquipe": 4, "nomEquipe": "Les Rouges", "statutEquipe": "EN_LICE", "nombreMembres": 5 }]
```

`motifSortie` n'apparaît que pour une équipe disqualifiée.

**`GET /api/tournois/{id}/arbre`** — liste vide tant que les inscriptions sont
ouvertes ; sinon, par tour puis par position. Le front reconstruit l'arbre avec
`idRencontreSuivante` et `emplacementSuivant` : aucun calcul de position.

```json
[{ "idRencontre": 1, "tour": 1, "position": 1,
   "equipeA": { "idEquipe": 4, "nomEquipe": "Les Rouges" },
   "equipeB": { "idEquipe": 5, "nomEquipe": "Les Bleus" },
   "statutRencontre": "JOUABLE", "idRencontreSuivante": 5, "emplacementSuivant": "A" }]
```

`statutRencontre` : `EN_ATTENTE` → `JOUABLE` → `TERMINE`.

### Rencontres

| Route | Accès | Exigence | Codes | |
|---|---|---|---|---|
| `PATCH /api/rencontres/{id}` | Administrateur | B-13, B-14, B-15 | 200, 400, 401, 403, 404, 409, 422 | ✅ |

```json
{ "idVainqueur": 4, "typeResultat": "NORMAL", "scoreA": 2, "scoreB": 1 }   // match joué
{ "idVainqueur": 4, "typeResultat": "FORFAIT" }                            // forfait
{ "idVainqueur": 4, "typeResultat": "QUALIFICATION_DIRECTE" }              // pas d'adversaire
```

Dans une seule transaction : résultat enregistré, perdant `ELIMINEE`, vainqueur
placé dans la rencontre suivante, qui devient `JOUABLE` si ses deux côtés sont
connus. Une saisie simultanée est sérialisée par un verrou sur le tournoi.
Émet **un `rencontre:maj` par rencontre modifiée** (la jouée et celle qui reçoit
le vainqueur).

- `400` : `scoreA`/`scoreB` envoyés l'un sans l'autre, ou avec un type autre que `NORMAL`.
- `403` : l'appelant n'est pas administrateur (B-13).
- `409` : tournoi pas `EN_COURS`, rencontre pas `JOUABLE` ou déjà `TERMINE`.
- `422` : le vainqueur ne joue pas cette rencontre ; `QUALIFICATION_DIRECTE`
  alors que les deux équipes sont connues (ou l'inverse) ; score du vainqueur
  pas strictement supérieur.

### Diagnostic

| Route | Accès | Réponse |
|---|---|---|
| `GET /health` ✅ | Public | `200` : `{ statut: "ok", baseDeDonnees: { joignable, versionPostgres, tables, schemaComplet } }` · `503` si la base est arrêtée, **sans détail technique** |

### Équipes, demandes, espace d'échange — ⏳ à implémenter

Spécifiées au contrat (§4, §6), **aucune route codée à ce jour**. Les tables SQL
existent (`equipe`, `composer`, `demande_adhesion`, `role_jeu`, `message`).

| Route prévue | Accès | Exigence |
|---|---|---|
| `POST /api/tournois/{id}/equipes` | Joueur connecté | B-05, B-07 |
| `GET /api/equipes/{id}` | Public | B-02 |
| `PATCH /api/equipes/{id}` | Capitaine (`nomEquipe`) · Administrateur (`statutEquipe`, `motifSortie`) | B-09, B-10, B-15 |
| `POST /api/equipes/{id}/demandes` | Joueur connecté | B-06 |
| `GET /api/equipes/{id}/demandes` | Capitaine | B-06 |
| `PATCH /api/demandes/{id}` | Capitaine | B-06 |
| `PATCH /api/equipes/{id}/membres/{idUtilisateur}` | Capitaine | B-08, B-09 |
| `DELETE /api/equipes/{id}/membres/{idUtilisateur}` | Capitaine, ou le membre lui-même | B-06, B-09, B-17 |
| `GET /api/equipes/{id}/messages` | Membre, ou administrateur | B-16, B-18 |
| `POST /api/equipes/{id}/messages` | Membre d'une équipe `EN_LICE` | B-16, B-18 |

Risques de sécurité à couvrir **par des tests dès l'écriture** : le capitaine
qui envoie `statutEquipe` (400) ; un non-membre qui lit les messages (404, pas
403) ; l'exclusion qui doit aussi expulser le socket (B-17).

---

## 5. Temps réel (Socket.IO)

Le serveur parle le protocole **Socket.IO** (pas un WebSocket brut) : il faut
`socket.io-client` côté navigateur. Même URL que l'API,
`{ withCredentials: true }` pour que le cookie parte avec la connexion.

```ts
import { io } from 'socket.io-client';
const socket = io('http://localhost:5000', { withCredentials: true });
socket.on('connect', () => socket.emit('tournoi:suivre', { idTournoi: 38 }));
socket.on('rencontre:maj', (rencontre) => { /* … */ });
```

### Salons

| Salon | Qui peut s'abonner | État |
|---|---|---|
| `tournoi:{idTournoi}` | Tout le monde, même sans compte (B-19) | ✅ |
| `equipe:{idEquipe}` | Membres de l'équipe, selon la règle d'accès du contrat §6 | ⏳ |

### Client → serveur

| Événement | Charge | Accusé |
|---|---|---|
| `tournoi:suivre` ✅ | `{ "idTournoi": 38 }` | `{ "ok": true }`, `{ "ok": false }` si l'identifiant n'est pas un entier > 0 |
| `tournoi:quitter` ✅ | `{ "idTournoi": 38 }` | idem |

À l'ouverture, le serveur envoie `bienvenue` (`{ message }`) — utile pour le
diagnostic. **Le serveur oublie les salons d'une connexion perdue** : le client
doit rejoindre à chaque `connect`, pas une seule fois.

### Serveur → client

| Événement | Charge | Quand | État |
|---|---|---|---|
| `tournoi:maj` | `Tournoi` complet | Transition d'état ou renommage (B-03, B-04). Après une transition l'arbre a pu changer : le client le relit | ✅ |
| `rencontre:maj` | `Rencontre` complet | Résultat saisi (B-14, B-19) — un événement par rencontre modifiée | ✅ |
| `message:nouveau` | `Message` complet | Un membre poste (B-16) | ⏳ |
| `equipe:acces-revoque` | `{ idEquipe, motif: "exclusion" \| "elimination" \| "disqualification" }` | Le destinataire perd l'accès (B-17, B-18) | ⏳ |

Garanties : les événements sont émis **après** la validation de la transaction ;
les charges sont l'objet complet (pas un simple identifiant). **Pas de rejeu** :
les événements émis pendant une coupure sont perdus, le client recharge l'état
par HTTP à la reconnexion (motif « snapshot puis deltas »).

---

## 6. Couverture des exigences du sujet B

| Exigence | État | Où |
|---|---|---|
| B-01 créer un tournoi | ✅ | `POST /api/tournois` |
| B-02 chercher et consulter | ✅ | `GET /api/tournois`, `…/{id}`, `…/equipes`, `…/arbre` |
| B-03 clore les inscriptions | ✅ | `PATCH /api/tournois/{id}` → `INSCRIPTIONS_CLOSES` |
| B-04 lancer, forfait des équipes incomplètes | ✅ | `PATCH /api/tournois/{id}` → `EN_COURS` |
| B-05 créer une équipe | ⏳ | — |
| B-06 demander à rejoindre / quitter | ⏳ | — |
| B-07 une équipe par tournoi | ⏳ | contrainte SQL prête |
| B-08 cinq joueurs avec un rôle | ◐ | décompte vérifié au lancement ; attribution des rôles ⏳ |
| B-09 gérer son équipe (capitaine) | ⏳ | — |
| B-10 seul le capitaine touche à l'équipe | ⏳ | à tester |
| B-11 composition figée après clôture | ⏳ | — |
| B-12 arbre généré à la clôture | ✅ | tirage au sort, 2/4/8/16 équipes |
| B-13 seul l'admin saisit un résultat | ✅ | `403` testé |
| B-14 le vainqueur avance | ✅ | propagation dans l'arbre |
| B-15 forfait | ◐ | forfait par résultat ✅ ; disqualification d'une équipe ⏳ |
| B-16 espace d'échange temps réel | ⏳ | — |
| B-17 exclu = accès coupé immédiatement | ⏳ | — |
| B-18 espace fermé si équipe éliminée | ⏳ | — |
| B-19 suivi en direct | ✅ | `tournoi:maj`, `rencontre:maj` |

---

## 7. Écarts constatés entre le contrat et le code

À arbitrer à deux, puis à corriger dans **les deux** dépôts si le contrat change.

1. **Durée du cookie** : le contrat dit `Max-Age=43200` (12 h), l'API pose
   environ un an (la validité réelle de 12 h est bien appliquée par `exp`).
   Correction : passer `max_age` à `set_access_cookies`.
2. **Connexion Socket.IO non authentifiée** : le contrat (§7) prévoit une
   authentification « à la connexion et à chaque abonnement ». Seul le salon
   public existe pour l'instant, donc rien n'est exposé ; l'authentification
   devra être ajoutée **avant** le salon `equipe:{id}`.
3. **Commentaires obsolètes** : `models/__init__.py` cite `sql/01_schema.sql`
   (le fichier s'appelle `sql/schema_R5A5_sujetB.sql`) ; un commentaire du
   schéma SQL (colonne `mot_de_passe_hash`) parle de `scrypt` alors que le code
   utilise argon2.
