# Contrat d'API — Plateforme de tournois (R5A5, sujet B)

**Version 12 — contrat figé.** v4 : le jeton passe dans un cookie `HttpOnly` (§2), après lecture du cours sur l'authentification.
v5 : précisions sur les tournois et l'arbre, issues de leur implémentation — corps de création, `GET /api/jeux`, règles de clôture et de lancement, résultats (§3, §5), abonnement au salon d'un tournoi (§7).
v6 : précisions sur les équipes, les demandes et les membres, issues de leur implémentation (§4).
v7 : espace d'échange et `GET /api/moi/…` (§4, §6), authentification du socket et abonnement `equipe:suivre` (§7).
v8 : règle de lancement « poste obligatoire » (§3), limites du temps réel et route de supervision (§7).
v9 : la déconnexion révoque les jetons (§2.3) et coupe les sockets ouverts (§7), compteur `coupuresPourRevocation` (§7), cache HTTP par `ETag` (§1).
v10 : désistement du capitaine, `DELETE /api/equipes/{id}` (§4) ; motif `dissolution` de `equipe:acces-revoque` (§7).
v11 : un administrateur ne participe pas aux tournois — `403` sur la création d'une équipe et sur une demande d'adhésion (§4).
v12 : plafond de 20 connexions temps réel simultanées par adresse IP, compteur `connexionsRefusees` (§7).

Ce document est la frontière entre le front et le back. Il vit **dans les deux
dépôts**, à l'identique. Toute modification se décide à deux et se répercute des
deux côtés dans le même mouvement.

Tous les choix ouverts ont été tranchés (§10). Le point signalé ⚠ au §1.4 n'est
pas une question en suspens mais une conséquence à respecter à l'implémentation.

---

## 1. Conventions générales

| Sujet | Convention retenue |
|---|---|
| Préfixe | `/api` pour toutes les routes métier. `/health` reste à la racine. |
| Format | JSON en entrée comme en sortie. |
| Nommage des champs | `camelCase`. Le front est en TypeScript, il n'a ainsi aucune conversion à faire ; le back convertit dans sa couche DTO. |
| Dates | ISO 8601 avec fuseau, ex. `2026-09-17T14:30:00+02:00`. La base stocke en `TIMESTAMPTZ`. |
| Identifiants | Entiers, nommés `idTournoi`, `idEquipe`… comme en base. |
| Authentification | Cookie `HttpOnly` `jeton`, posé par l'API et joint par le navigateur (§2). |
| Verbes | CRUD classique. Les changements d'état passent par `PATCH`, pas par des routes d'action. |
| Encodage | UTF-8. |

### 1.1 Forme unique des erreurs

```json
{ "erreur": "Not Found", "detail": "Tournoi introuvable." }
```

Le front ne doit jamais avoir à deviner la structure d'une erreur.

### 1.2 Codes HTTP

| Code | Quand |
|---|---|
| 200 | Succès avec contenu |
| 201 | Ressource créée |
| 204 | Succès sans contenu (suppression) |
| 400 | Charge invalide : champ manquant, format incorrect, **ou champ non modifiable par l'appelant** (voir §1.4) |
| 401 | Non authentifié : jeton absent, expiré, invalide, ou révoqué (voir §2) |
| 403 | Ressource **publique**, mais action interdite (voir §1.3) |
| 404 | Ressource inexistante, **ou invisible pour l'appelant** (voir §1.3) |
| 409 | Conflit avec l'**état** courant : inscriptions closes, tournoi déjà lancé, pseudo déjà pris |
| 422 | Violation d'une **règle métier** : rôle déjà occupé, joueur déjà dans une équipe du tournoi |

La distinction 409 / 422 est volontaire : 409 pour ce qui dépend du cycle de vie
du tournoi, 422 pour ce qui dépend des règles de composition. Elle se justifie
bien à l'oral, à condition de s'y tenir partout.

### 1.3 Ressource interdite : 404 par défaut, 403 sur les ressources publiques

Le principe retenu est le **404** : un utilisateur qui n'a pas le droit
d'accéder à une ressource ne doit pas pouvoir déduire qu'elle existe.

Il ne peut cependant pas s'appliquer partout. Les tournois, les équipes et les
rencontres sont **publics** (B-02) : tout le monde peut les lister sans compte.
Si un joueur tente de clore un tournoi qu'il voit affiché à l'écran et reçoit
« ce tournoi n'existe pas », le message est faux et ne cache rien — la ressource
était visible deux secondes plus tôt.

**Règle retenue :**

| Situation | Code |
|---|---|
| La ressource est publique, seule l'**action** est interdite : clore un tournoi, saisir un résultat, modifier une équipe dont on n'est pas capitaine | **403** |
| La ressource elle-même n'est **pas visible** pour l'appelant : espace d'échange d'une équipe dont il n'est pas membre, demandes d'adhésion | **404** |

C'est le seul découpage qui protège réellement quelque chose : le 404 sert là où
il y a effectivement une information à cacher. Ailleurs, il complique le
débogage sans rien apporter.

### 1.4 `PATCH` et autorisation champ par champ

⚠ **Conséquence directe du choix de `PATCH`.** Une même route sert désormais
plusieurs acteurs. `PATCH /api/equipes/{id}` accepte :

- `nomEquipe` — réservé au **capitaine** (B-09)
- `statutEquipe` et `motifSortie` — réservés à l'**administrateur** (disqualification)

Vérifier « l'appelant a-t-il le droit d'appeler cette route » ne suffit donc
plus : il faut vérifier **champ par champ**. Un capitaine qui enverrait
`{ "statutEquipe": "VAINQUEUR" }` gagnerait le tournoi tout seul.

**Règle d'implémentation, à respecter partout :**

1. Chaque route `PATCH` déclare une liste blanche de champs modifiables **par
   rôle**.
2. Tout champ absent de la liste blanche de l'appelant → `400`, et la requête
   entière est rejetée. Jamais d'application partielle.
3. Tout champ inconnu → `400` également.

C'est exactement le genre de faille que vos tests de droits d'accès doivent
couvrir : un test « le capitaine ne peut pas modifier `statutEquipe` » vaut
autant qu'un test sur la route entière.

### 1.5 Cache HTTP (v9)

Le cache est réglé par l'API, route par route, et jamais au petit bonheur :

| Réponse | `Cache-Control` | Pourquoi |
|---|---|---|
| `GET` **public** réussi (tournois, jeux, arbre, équipes d'un tournoi) | `no-cache` + `ETag` | Le navigateur peut garder une copie mais **doit revalider** : si rien n'a changé, l'API répond `304` sans corps. Un résultat saisi est donc visible tout de suite. |
| Toute autre réponse de `/api` (routes privées, écritures, erreurs) | `no-store` | Données personnelles ou état qui change : rien n'est conservé. |

Il n'y a **jamais de `max-age`** : un `max-age` ferait afficher un arbre périmé
pendant un tournoi en direct. Le temps réel prévient d'un changement ; le
cache ne doit pas le masquer.

---

## 2. Authentification

Le jeton voyage dans un **cookie `HttpOnly`** posé par l'API, et non dans le
corps des réponses : le JavaScript de la page ne peut pas le lire, donc un
script injecté ne peut pas l'emporter. Le navigateur le joint seul à chaque
requête vers l'API ; le front appelle `fetch` avec `credentials: 'include'`.

```
Set-Cookie: jeton=eyJ…; HttpOnly; SameSite=Lax; Path=/; Max-Age=43200
```

| Attribut | Pourquoi |
|---|---|
| `HttpOnly` | Illisible en JavaScript |
| `SameSite=Lax` | Protection CSRF : le front (`localhost:5173`) et l'API (`localhost:5000`) sont le même site. **Aucune route n'écrit en GET** |
| `Secure` | Activé par `COOKIE_SECURE=true`, dès que l'API est servie en HTTPS |
| `Max-Age` | 12 heures (§2.1) |

La documentation détaillée des routes (corps, réponses, erreurs) est générée
depuis le code : `http://localhost:5000/apidoc/swagger`. Ce qui suit fixe les
règles.

| Route | Accès | Réponse |
|---|---|---|
| `POST /api/auth/inscription` | Public, 5 essais par minute | `201 { utilisateur }` + cookie ; `409` pseudo ou e-mail pris ; `400` mot de passe de moins de 12 caractères |
| `POST /api/auth/connexion` | Public, 5 essais par minute | `200 { utilisateur }` + cookie ; `401` ; `429` au-delà de la limite |
| `GET /api/auth/moi` | Authentifié | `200 Utilisateur` : sert au front à restaurer la session au chargement |
| `POST /api/auth/deconnexion` | Public | `204`, cookie effacé **et jeton révoqué** (v9) : l'appel est publique pour qu'une session expirée puisse être fermée, et sans effet de révocation si le cookie est absent ou invalide |

`Utilisateur` : `{ idUtilisateur, pseudo, email, estAdministrateur }`.

La connexion répond `401` **avec le même message que l'e-mail soit inconnu ou
le mot de passe faux**, et prend le même temps dans les deux cas. Distinguer
les deux permettrait d'énumérer les comptes.

### 2.1 Cycle de vie du jeton

**Un seul jeton, valable 12 heures, sans jeton de rafraîchissement.** À
expiration, l'API répond `401` et efface le cookie ; le front redirige vers
l'écran de connexion.

Douze heures parce qu'un tournoi se joue sur une soirée : personne ne doit être
déconnecté au milieu d'une demi-finale. Le rafraîchissement automatique suppose
un second jeton, son stockage, sa rotation, sa révocation et une route dédiée :
beaucoup de mécanique pour un outil utilisé le temps d'une compétition.

### 2.2 Ce que le jeton contient — et ne contient pas

```json
{ "sub": "1", "ver": 3, "iat": 1789650000, "exp": 1789693200,
  "nbf": 1789650000, "jti": "…", "type": "access", "fresh": false }
```

`nbf`, `jti`, `type` et `fresh` sont ajoutés par flask-jwt-extended ; le projet
ne s'en sert pas.

| Claim | Rôle |
|---|---|
| `sub` | Identifiant de l'utilisateur |
| `ver` | Valeur de `utilisateur.version_jeton` à l'émission (§2.3) |
| `iat` / `exp` | Émission et expiration |

Algorithme imposé côté serveur (`HS256`) : un jeton qui en annonce un autre est refusé.

**Aucun droit n'est inscrit dans le jeton** — ni l'appartenance aux équipes, ni
le statut d'administrateur.

La signature garantit l'**identité** : personne ne peut fabriquer un jeton
prétendant être quelqu'un d'autre sans la clé du serveur. Mais elle ne garantit
rien sur les **droits**, qui sont une information figée au moment de la
connexion. Si l'on retire ses droits d'administrateur à quelqu'un, un jeton qui
les affirmerait resterait valable jusqu'à expiration.

Les droits sont donc relus en base **à chaque requête** :

- l'appartenance aux équipes et le rôle de capitaine, parce que B-17 exige une
  perte d'accès immédiate ;
- `est_administrateur`, pour la même raison, et parce que c'est gratuit : la
  ligne de l'utilisateur est de toute façon chargée pour vérifier `ver`.

### 2.3 Révocation — `utilisateur.version_jeton`

Un JWT n'est pas révocable par nature : une fois émis, il vaut jusqu'à son
expiration, même si le compte est supprimé. D'où une colonne entière
`version_jeton` sur `utilisateur`, initialisée à 1.

Le jeton embarque cette valeur dans `ver`. À chaque requête, le serveur la
compare à celle en base et rejette le jeton avec `401` si elles diffèrent.

Incrémenter `version_jeton` invalide donc instantanément **tous** les jetons
déjà émis pour ce compte. À faire lors d'un changement de mot de passe, d'un
retrait des droits d'administrateur, d'un soupçon de vol, ou d'une déconnexion
de toutes les sessions.

**v9 : la déconnexion incrémente `version_jeton`.** Un jeton copié avant la déconnexion cesse de fonctionner (`401`), et les autres appareils du même compte sont déconnectés aussi (« se déconnecter partout »). L'incrément est atomique (`UPDATE … WHERE version_jeton = :ver`) : rejouer un ancien jeton après une nouvelle connexion ne révoque pas la session récente. Les sockets ouverts avec ce jeton sont fermés par la boucle de surveillance (§7).

Le coût est nul : la ligne de l'utilisateur est déjà lue à chaque requête. Pas
de table de jetons révoqués, pas de jeton de rafraîchissement, pas de route
supplémentaire.

---

## 3. Tournois

| Route | Accès | Exigence |
|---|---|---|
| `GET /api/tournois` | Public | B-02 |
| `GET /api/tournois/{id}` | Public | B-02 |
| `POST /api/tournois` | Administrateur | B-01 |
| `PATCH /api/tournois/{id}` | Administrateur | B-03, B-04, B-12 |
| `GET /api/tournois/{id}/equipes` | Public | B-02 |
| `GET /api/tournois/{id}/arbre` | Public | B-12, B-19 |
| `GET /api/jeux/{id}/roles` | Public | B-05 (postes proposés à la création d'une équipe) |
| `GET /api/jeux` | Public | B-01 (liste proposée à la création) |

### `GET /api/tournois`

Paramètres : `recherche` (texte libre sur le nom), `statut` (filtre).

```json
[
  {
    "idTournoi": 1,
    "nomTournoi": "Coupe de printemps",
    "jeu": { "idJeu": 1, "nomJeu": "League of Legends", "joueursParEquipe": 5 },
    "statutTournoi": "INSCRIPTIONS_OUVERTES",
    "nombreEquipes": 8,
    "nombreEquipesInscrites": 3,
    "creeLe": "2026-09-17T14:30:00+02:00"
  }
]
```

### `GET /api/tournois/{id}` — l'objet `Tournoi` complet

Les champs de la liste, plus les dates du cycle de vie, omises tant qu'elles
ne sont pas atteintes. C'est aussi la réponse de `POST` et de `PATCH`, et la
charge de l'événement `tournoi:maj`.

```json
{
  "idTournoi": 1, "nomTournoi": "Coupe de printemps",
  "jeu": { "idJeu": 1, "nomJeu": "League of Legends", "joueursParEquipe": 5 },
  "statutTournoi": "EN_COURS", "nombreEquipes": 8, "nombreEquipesInscrites": 8,
  "creeLe": "2026-09-17T14:30:00+02:00",
  "inscriptionsClosesLe": "2026-09-20T18:00:00+02:00",
  "demarreLe": "2026-09-24T18:00:00+02:00"
}
```

### `POST /api/tournois`

```json
{ "nomTournoi": "Coupe de printemps", "idJeu": 1, "nombreEquipes": 8 }
```

`nombreEquipes` est facultatif : 8 par défaut (B-12), 2, 4 ou 16 acceptés. Le
tournoi naît `INSCRIPTIONS_OUVERTES`. `201 Tournoi` ; `422` si le jeu n'existe
pas.

### `GET /api/tournois/{id}/equipes`

```json
[ { "idEquipe": 4, "nomEquipe": "Les Rouges", "statutEquipe": "EN_LICE", "nombreMembres": 5 } ]
```

Par ordre d'inscription. `motifSortie` n'apparaît que pour une équipe disqualifiée.

### `GET /api/jeux`

`[ { "idJeu": 1, "nomJeu": "League of Legends", "joueursParEquipe": 5 } ]`, par
ordre alphabétique.

### `PATCH /api/tournois/{id}`

Champs modifiables par l'administrateur : `nomTournoi`, `statutTournoi`.

**Un `PATCH` sur `statutTournoi` n'est pas une simple écriture de champ : il
déclenche une transition d'état, avec ses effets de bord.** C'est le point à
garder en tête, puisque vous avez préféré `PATCH` aux routes d'action.

| Transition demandée | Effets, dans une seule transaction |
|---|---|
| `INSCRIPTIONS_OUVERTES` → `INSCRIPTIONS_CLOSES` | Fige la composition des équipes (B-03) **et** génère les 7 rencontres de l'arbre avec leurs liens (B-12) |
| `INSCRIPTIONS_CLOSES` → `EN_COURS` | Déclare forfait les équipes incomplètes (B-04) |
| `EN_COURS` → `TERMINE` | Marque l'équipe gagnante `VAINQUEUR` |

Toute autre transition → `409`. La machine à états vit dans **une seule fonction
de service**, appelée par cette route : c'est elle qui valide la transition
avant d'agir, parce qu'une contrainte SQL ne voit pas la valeur précédente.

Précisions (v5) :

- **Clôture** : `409` s'il y a moins de 2 équipes inscrites. Les équipes sont
  placées par tirage au sort, d'abord sur tous les côtés A du premier tour,
  puis sur les côtés B : avec 5 équipes sur 8, une rencontre et trois
  qualifications directes. Une rencontre du premier tour sans aucune équipe
  reste `EN_ATTENTE` pour toujours.
- **Lancement** : une équipe est incomplète quand elle a moins de membres que
  `jeu.joueursParEquipe` **ou** qu'un de ses membres n'a pas de poste (B-08 :
  cinq joueurs, chacun avec un rôle). Elle passe `ELIMINEE` ; si elle avait un adversaire,
  sa rencontre se termine en `FORFAIT` à son profit. `422` si moins de deux
  équipes sont complètes, poste compris.
- **Fin** : `409` tant que la finale n'a pas de vainqueur.
- Une requête sans aucun champ → `400`.

---

## 4. Équipes et composition

| Route | Accès | Exigence |
|---|---|---|
| `POST /api/tournois/{id}/equipes` | Joueur connecté | B-05 |
| `GET /api/equipes/{id}` | Public | B-02 |
| `PATCH /api/equipes/{id}` | Capitaine (`nomEquipe`) / Administrateur (`statutEquipe`, `motifSortie`) | B-09, B-10 |
| `POST /api/equipes/{id}/demandes` | Joueur connecté | B-06 |
| `GET /api/equipes/{id}/demandes` | Capitaine | B-06 |
| `PATCH /api/demandes/{id}` | Capitaine | B-06 |
| `PATCH /api/equipes/{id}/membres/{idUtilisateur}` | Capitaine | B-08, B-09 |
| `DELETE /api/equipes/{id}` | Capitaine | B-06 |
| `DELETE /api/equipes/{id}/membres/{idUtilisateur}` | Capitaine, ou le membre lui-même | B-06, B-09, B-17 |
| `GET /api/moi/equipes` | Connecté | B-16 (où joue-t-on ?) |
| `GET /api/moi/demandes` | Connecté | B-06 (demandes en attente) |

### `POST /api/tournois/{id}/equipes`

```json
{ "nomEquipe": "Les Rouges", "idRole": 3 }
```

Le créateur devient capitaine **et** premier membre, dans la même transaction
(B-05). `idRole` est son poste de jeu.

- `403` si l'appelant est administrateur (v11) : il organise le tournoi et en saisit les résultats, il n'y joue pas ; pour participer, il utilise un compte joueur.
- `409` si les inscriptions sont closes, ou si le nom est déjà pris dans ce tournoi.
- `422` si le joueur appartient déjà à une équipe de ce tournoi (B-07).

Pour un jeu **en solo** (`joueursParEquipe` = 1), l'inscription est une équipe d'un seul joueur : le front la nomme d'après le pseudo et l'API n'a rien de particulier à faire.

### `GET /api/equipes/{id}`

```json
{
  "idEquipe": 4,
  "idTournoi": 1,
  "nomEquipe": "Les Rouges",
  "statutEquipe": "EN_LICE",
  "membres": [
    { "idUtilisateur": 1, "pseudo": "alice", "estCapitaine": true,
      "role": { "idRole": 3, "libelleRole": "Mid" } }
  ]
}
```

### `PATCH /api/demandes/{id}`

Entrée `{ "statutDemande": "ACCEPTEE" }` ou `"REFUSEE"`.

L'acceptation ajoute le joueur à l'équipe dans la même transaction.

- `409` si la demande n'est plus `EN_ATTENTE`, ou si les inscriptions sont closes.
- `422` si le joueur a rejoint une autre équipe du tournoi entre-temps (B-07),
  ou si l'équipe est déjà complète.

L'historique des demandes refusées est conservé : un joueur refusé peut
repostuler, ce que l'index partiel en base autorise explicitement.

### `PATCH /api/equipes/{id}/membres/{idUtilisateur}`

Champs : `idRole` (attribution du poste, B-08) et `estCapitaine` (passation,
B-09).

Passer `{ "estCapitaine": true }` sur un autre membre rétrograde
automatiquement le capitaine en place — l'index unique partiel en base interdit
deux capitaines, donc les deux écritures se font dans la même transaction.

- `409` si les inscriptions sont closes (B-11).
- `422` si le poste est déjà tenu par un autre membre de l'équipe.

### `DELETE /api/equipes/{id}` (v10)

Le **désistement** : le capitaine dissout son équipe tant que les inscriptions
sont ouvertes. Les membres, les demandes en attente et les messages partent avec
elle ; la place est libérée dans le tournoi et le nom redevient disponible.
Chaque membre reçoit `equipe:acces-revoque` avec le motif `dissolution`.

- `204` sans contenu.
- `403` si l'appelant n'est pas le capitaine (l'administrateur non plus : il dispose de la disqualification).
- `404` si l'équipe n'existe pas.
- `409` si les inscriptions sont closes : une équipe inscrite à l'arbre ne disparaît plus.

Un capitaine qui veut **partir en laissant l'équipe** passe d'abord la main
(`PATCH …/membres/{id}` avec `estCapitaine`), puis quitte (`DELETE …/membres/{id}`).

### `DELETE /api/equipes/{id}/membres/{idUtilisateur}`

Deux usages sur la même route : le capitaine exclut un membre (B-09), ou un
joueur quitte l'équipe de lui-même (B-06). Le back distingue par l'identité de
l'appelant.

- `403` si l'appelant n'est ni capitaine ni le membre concerné.
- `409` si les inscriptions sont closes (B-11).
- `422` si le capitaine tente de s'exclure sans avoir passé la main.

**Conséquence temps réel (B-17)** : cette route doit aussi expulser la connexion
WebSocket active du joueur et lui émettre `equipe:acces-revoque`. Supprimer la
ligne en base ne suffit pas — un socket déjà ouvert continuerait de recevoir les
messages.

### Précisions (v6)

- **Réponses** — `Equipe` : `{ idEquipe, idTournoi, nomEquipe, statutEquipe, motifSortie?, membres: [ { idUtilisateur, pseudo, estCapitaine, role?: { idRole, libelleRole } } ] }`.
  `Demande` : `{ idDemande, idEquipe, idUtilisateur, pseudo, statutDemande, creeLe, traiteLe? }`.
  `role` est omis tant qu'aucun poste n'est attribué.
- **Création** — `409` aussi si le tournoi est complet. `422` si `idRole` n'est pas un poste du jeu du tournoi. Un nom d'équipe est unique par tournoi, sans tenir compte de la casse.
- **`POST /api/equipes/{id}/demandes`** — pas de corps. `403` pour un administrateur (v11). `409` si une demande est déjà en attente ou si les inscriptions sont closes ; `422` si le joueur a déjà une équipe dans ce tournoi, ou si l'équipe est complète.
- **`GET /api/equipes/{id}/demandes`** — paramètre facultatif `statut` ; sans filtre, tout l'historique. `404` pour quiconque n'est pas capitaine de l'équipe, **administrateur compris**.
- **`PATCH /api/demandes/{id}`** — `statutDemande` vaut `ACCEPTEE` ou `REFUSEE`. `404` si l'appelant n'est pas le capitaine de l'équipe. L'acceptation ajoute le joueur **sans poste**.
- **`PATCH /api/equipes/{id}`** — `statutEquipe` n'accepte que `DISQUALIFIEE`. `403` si l'appelant n'est ni capitaine ni administrateur ; `400` si un champ est hors de la liste de son rôle. Renommage : `409` si les inscriptions sont closes (B-11, comme toute écriture d'équipe, §10). Disqualification : `409` si le tournoi n'est pas `EN_COURS` ou si l'équipe n'est plus en lice.
- **`GET /api/moi/equipes`** (v7) — `[ { idEquipe, nomEquipe, statutEquipe, estCapitaine, idTournoi, nomTournoi, statutTournoi } ]`, les plus récentes d'abord. Sert à retrouver ses équipes sans parcourir chaque tournoi.
- **`GET /api/moi/demandes`** (v7) — `[ { idDemande, statutDemande, creeLe, idEquipe, nomEquipe, idTournoi, nomTournoi } ]`, uniquement les demandes en attente de l'utilisateur.
- **`PATCH …/membres/{idUtilisateur}`** — `estCapitaine` n'accepte que `true` : le capitanat se transmet, il ne se retire pas. `403` pour tout appelant qui n'est pas capitaine de l'équipe, administrateur compris (B-10).

---

## 5. Compétition

| Route | Accès | Exigence |
|---|---|---|
| `PATCH /api/rencontres/{id}` | Administrateur | B-13, B-14, B-15 |
| `PATCH /api/equipes/{id}` (`statutEquipe`) | Administrateur | Disqualification |
| `GET /api/tournois/{id}/arbre` | Public | B-12, B-19 |

### `PATCH /api/rencontres/{id}`

Une seule route pour les trois situations, puisque le mécanisme est le même :
l'administrateur désigne un vainqueur, et celui-ci remonte dans l'arbre.

```json
// Match joué (B-13)
{ "idVainqueur": 4, "typeResultat": "NORMAL", "scoreA": 2, "scoreB": 1 }

// Forfait (B-04, B-15)
{ "idVainqueur": 4, "typeResultat": "FORFAIT" }

// Pas d'adversaire
{ "idVainqueur": 4, "typeResultat": "QUALIFICATION_DIRECTE" }
```

Effets, dans une seule transaction (B-14) : enregistrement du résultat,
élimination du perdant, propagation du vainqueur dans la rencontre suivante à
l'emplacement prévu, et passage de celle-ci en `JOUABLE` si ses deux équipes
sont désormais connues.

- `400` si `scoreA` et `scoreB` ne sont pas envoyés ensemble, ou avec un
  autre type que `NORMAL`.
- `403` si l'appelant n'est pas administrateur — **à tester** (B-13).
- `409` si la rencontre n'est pas `JOUABLE`, est déjà `TERMINE`, ou si le
  tournoi n'est pas `EN_COURS`.
- `422` si `idVainqueur` ne participe pas à cette rencontre ; si
  `QUALIFICATION_DIRECTE` est demandée alors que les deux équipes sont
  connues, ou l'inverse ; si le score du vainqueur n'est pas le plus élevé.

Une rencontre devient `JOUABLE` quand chacun de ses deux côtés est connu :
une équipe y est placée, ou aucune ne pourra jamais y arriver (côté vide au
premier tour, ou alimenté par une rencontre elle-même vide). Réponse :
`200 Rencontre`.

### Disqualification — `PATCH /api/equipes/{id}`

```json
{ "statutEquipe": "DISQUALIFIEE", "motifSortie": "Comportement inapproprié" }
```

Passe l'équipe en `DISQUALIFIEE`, enregistre le motif, marque sa rencontre en
cours ou à venir en `FORFAIT` au profit de l'adversaire, et ferme son espace
d'échange.

`400` si l'appelant est le capitaine et non l'administrateur (§1.4).

### `GET /api/tournois/{id}/arbre`

```json
[
  {
    "idRencontre": 1, "tour": 1, "position": 1,
    "equipeA": { "idEquipe": 4, "nomEquipe": "Les Rouges" },
    "equipeB": { "idEquipe": 5, "nomEquipe": "Les Bleus" },
    "idVainqueur": null,
    "statutRencontre": "JOUABLE",
    "typeResultat": null,
    "idRencontreSuivante": 5,
    "emplacementSuivant": "A"
  }
]
```

Le front reconstruit l'arbre à partir de `idRencontreSuivante` et
`emplacementSuivant`. Aucun calcul de position à faire : la base porte déjà les
liens.

Ordre : par tour, puis par position. Liste vide tant que les inscriptions sont
ouvertes. Comme partout, un champ sans valeur est **omis** plutôt qu'envoyé à
`null` : `equipeB` absente signifie « pas encore d'équipe ». `scoreA` et
`scoreB` apparaissent quand ils ont été saisis.

---

## 6. Espace d'échange

| Route | Accès | Exigence |
|---|---|---|
| `GET /api/equipes/{id}/messages` | Membre de l'équipe, ou administrateur | B-16, B-18 |
| `POST /api/equipes/{id}/messages` | Membre d'une équipe `EN_LICE` | B-16, B-18 |

**La règle d'accès, formulée une fois pour toutes :**

> Lecture : être membre de l'équipe **et** l'équipe est `EN_LICE`, **ou** être
> administrateur (B-18).
> Écriture : être membre **et** l'équipe est `EN_LICE`. L'administrateur lit
> mais n'écrit pas.

Cette règle vit dans **une seule fonction** côté back, appelée par les deux
routes **et** par le gestionnaire WebSocket. Trois implémentations séparées,
c'est trois occasions de diverger — et ce sont précisément les points que vos
tests de sécurité doivent couvrir.

C'est ici que le `404` du §1.3 s'applique pleinement : un non-membre ne doit pas
apprendre que l'espace existe.

**Précisions (v7).**

- `Message` : `{ idMessage, idEquipe, idAuteur?, pseudo?, contenu, envoyeLe }`. `idAuteur` et `pseudo` sont omis quand le compte de l'auteur a disparu.
- `POST` : corps `{ contenu }`, texte brut de 1 à 2 000 caractères (espaces de bord retirés, message vide refusé en `400`). Réponse `201 Message`. `403` si l'appelant est administrateur ; `404` s'il n'est pas membre, si l'équipe n'est plus en lice ou si elle n'existe pas ; `429` au-delà de 30 messages par minute **et par utilisateur** (pas par adresse : une salle de TP partage la sienne).
- Le message est diffusé aux membres abonnés par `message:nouveau` **après** la validation de la transaction.
- Chaque refus d'accès est journalisé au niveau `WARNING` (équipe, utilisateur, lecture ou écriture, membre ou non), sans jamais en informer l'appelant au-delà du `404`.

**Pagination : aucune.** `GET` renvoie tous les messages de l'équipe, du plus
ancien au plus récent. Un tournoi dure une soirée, le volume reste faible. Si ça
devenait un problème, l'ajout se ferait par un paramètre `avant=<idMessage>`
sans casser l'existant.

---

## 7. Temps réel

Les événements poussés font autant partie du contrat que les routes HTTP.

**Connexion** : le navigateur joint le cookie `jeton` à la connexion au
WebSocket (`withCredentials: true` côté client). Le serveur l'authentifie à la
connexion **et** à chaque abonnement.

**Salons**

| Salon | Qui peut s'y abonner |
|---|---|
| `tournoi:{idTournoi}` | Tout le monde, même non connecté (B-19) |
| `equipe:{idEquipe}` | Membres de l'équipe uniquement, selon la règle du §6 |

**Authentification du socket (v7).** À la connexion, le serveur lit le cookie `jeton`, le vérifie (signature, expiration, `ver` contre `utilisateur.version_jeton`) et garde l'identité **côté serveur**, par connexion. Un visiteur se connecte quand même : il ne peut suivre que les tournois. L'identité n'est **jamais** lue dans un message du client, et l'appartenance à l'équipe est revérifiée à **chaque** `equipe:suivre`.

**Abonnement client → serveur** (v5, v7)

| Événement | Charge | Accusé de réception |
|---|---|---|
| `tournoi:suivre` | `{ "idTournoi": 1 }` | `{ "ok": true }`, ou `false` si l'identifiant est invalide |
| `tournoi:quitter` | `{ "idTournoi": 1 }` | idem |
| `equipe:suivre` (v7) | `{ "idEquipe": 4 }` | `{ "ok": true }` ; `{ "ok": false }` pour **tous** les refus (non connecté, non-membre, espace fermé, équipe inconnue) : la réponse ne dit jamais pourquoi |
| `equipe:quitter` (v7) | `{ "idEquipe": 4 }` | idem |

**Événements serveur → client**

| Événement | Charge | Quand |
|---|---|---|
| `message:nouveau` | Objet `Message` complet | Un membre poste (B-16) |
| `rencontre:maj` | Objet `Rencontre` complet | Un résultat est validé (B-14, B-19) : un événement par rencontre modifiée, la jouée et celle qui reçoit le vainqueur |
| `tournoi:maj` | Objet `Tournoi` complet | Changement d'état ou de nom (B-03, B-04). Après une transition, l'arbre a pu changer : le client le relit |
| `equipe:acces-revoque` | `{ "idEquipe": 4, "motif": "exclusion" \| "elimination" \| "disqualification" \| "dissolution" }` | Le destinataire perd l'accès (B-17, B-18) |

**Les charges contiennent l'objet complet**, pas seulement un identifiant : le
client affiche directement sans second aller-retour. C'est sans risque ici,
aucun de ces objets ne contient d'information sensible, et l'abonnement au salon
a déjà été autorisé.

**Limites (v8).** Elles protègent le serveur d'un client défaillant ou malveillant ; toutes sont réglables par variable d'environnement.

| Limite | Valeur par défaut | Effet au-delà |
|---|---|---|
| Heartbeat | ping toutes les 20 s, pong attendu sous 15 s | connexion jugée morte et fermée (inférieur aux 60 s de `proxy_read_timeout` de Nginx) |
| Taille d'un message reçu | 4 096 octets | la bibliothèque ferme la connexion |
| Événements par connexion | 30 en 10 s | connexion coupée, `WARNING` journalisé |
| Connexions simultanées par adresse IP (v12) | 20 | connexion refusée à l'ouverture (`connect_error` côté client), `WARNING` journalisé |
| Jeton expiré | vérifié toutes les 30 s | connexion fermée ; le client se reconnecte en visiteur |
| Jeton révoqué (v9) | vérifié toutes les 30 s, avec l'expiration | connexion fermée ; le client se reconnecte en visiteur |

**Supervision (v8)** : `GET /api/metriques/temps-reel`, **administrateur seulement** (`401` sans session, `403` pour un joueur). Renvoie `{ demarreLe, connexionsActives, connexionsAuthentifiees, ouverturesDerniereMinute, messagesDerniereMinute, ouverturesTotal, fermeturesTotal, messagesTotal, abonnementsRefuses, connexionsRefusees, coupuresPourDebit, coupuresPourExpiration, coupuresPourRevocation }`. Les compteurs sont en mémoire : ils repartent de zéro au redémarrage.

`equipe:acces-revoque` est l'événement qu'on oublie. Sans lui, un joueur exclu
garde son écran de chat ouvert et continue de recevoir les messages jusqu'à ce
qu'il recharge la page. Le serveur doit l'émettre **et** retirer le socket du
salon.

---

## 8. Couverture des exigences

| Exigence | Route ou événement |
|---|---|
| B-01 | `POST /api/tournois` |
| B-02 | `GET /api/tournois`, `GET /api/tournois/{id}`, `GET /api/tournois/{id}/arbre` |
| B-03 | `PATCH /api/tournois/{id}` → `INSCRIPTIONS_CLOSES` |
| B-04 | `PATCH /api/tournois/{id}` → `EN_COURS` |
| B-05 | `POST /api/tournois/{id}/equipes` |
| B-06 | `POST /api/equipes/{id}/demandes`, `PATCH /api/demandes/{id}`, `DELETE …/membres/{id}` |
| B-07 | `422` sur création d'équipe et acceptation de demande |
| B-08 | `PATCH …/membres/{id}` (`idRole`), contrôle au lancement : 5 joueurs **et** un poste chacun |
| B-09 | `PATCH /api/equipes/{id}`, `PATCH …/membres/{id}`, `DELETE …/membres/{id}` |
| B-10 | `403` sur les routes d'équipe, et liste blanche de champs |
| B-11 | `409` sur toutes les écritures d'équipe après clôture |
| B-12 | Généré par la transition `INSCRIPTIONS_CLOSES`, lu par `GET …/arbre` |
| B-13 | `403` sur `PATCH /api/rencontres/{id}` |
| B-14 | Propagation dans `PATCH /api/rencontres/{id}` |
| B-15 | `PATCH /api/rencontres/{id}` avec `typeResultat: "FORFAIT"` ; `PATCH /api/equipes/{id}` → `DISQUALIFIEE` |
| B-16 | `GET`/`POST …/messages` + `message:nouveau` |
| B-17 | `DELETE …/membres/{id}` + `equipe:acces-revoque` + expulsion du salon |
| B-18 | Règle d'accès du §6 + `equipe:acces-revoque` |
| B-19 | `rencontre:maj`, `tournoi:maj` sur le salon `tournoi:{id}` |

---

## 9. Ce que le back doit garantir hors du contrat

Rappel utile au moment d'implémenter : la base assure l'intégrité structurelle,
mais ces règles-là restent du ressort de Flask.

- Les transitions d'état du tournoi (une contrainte SQL ne voit pas la valeur précédente).
- Le décompte de cinq joueurs au lancement (un `CHECK` ne compte pas les lignes d'une autre table).
- La cohérence entre le rôle attribué et le jeu du tournoi — rien n'empêche en
  base d'assigner un poste de League of Legends dans un tournoi Overwatch.
- La liste blanche de champs par rôle sur chaque `PATCH` (§1.4).
- La comparaison de `ver` avec `utilisateur.version_jeton` à chaque requête (§2.3).

---

## 10. Décisions prises

| # | Question | Décision |
|---|---|---|
| 1 | Nommage des champs JSON | `camelCase` |
| 2 | 409 et 422 | Distincts : 409 pour l'état, 422 pour les règles métier |
| 3 | Ressource interdite | `404` par défaut, `403` quand la ressource est publique (§1.3) |
| 4 | Transitions d'état | `PATCH` sur la ressource, pas de routes d'action |
| 5 | Messages | Chargement complet, pas de pagination |
| 6 | Charges d'événement | Objet complet |
| 7 | Jeton | 12 h, un seul jeton, sans rafraîchissement |
| 8 | Droits dans le jeton | Aucun — tout est relu en base à chaque requête (§2.2) |
| 9 | Révocation | Colonne `utilisateur.version_jeton` comparée à chaque requête (§2.3) |
| 10 | Transport du jeton (v4) | Cookie `HttpOnly` `SameSite=Lax`, plus d'en-tête `Authorization` (§2) |
| 11 | Mots de passe (v4) | argon2, 12 caractères minimum, 5 essais par minute |
| 12 | Écritures du chat (v7) | En HTTP, jamais par le socket : le socket notifie, il ne crée pas |
| 13 | Identité du socket (v7) | Lue dans le cookie à la connexion, gardée côté serveur, jamais dans un message |
| 14 | Limites du temps réel (v8, v12) | Heartbeat 20 s / 15 s, 4 096 octets, 30 événements par 10 s, 20 connexions par adresse, fermeture à l'expiration du jeton |
| 15 | Déconnexion (v9) | Révoque le jeton (`version_jeton`) et coupe les sockets ouverts ; « se déconnecter » vaut « se déconnecter partout » |
| 16 | Cache HTTP (v9) | `no-cache` + `ETag` sur les `GET` publics (revalidation, `304`), `no-store` partout ailleurs ; jamais de `max-age` |

Ce document est figé. Toute modification ultérieure est un changement de
contrat : annoncée à l'autre, répercutée des deux côtés dans la même séance.
