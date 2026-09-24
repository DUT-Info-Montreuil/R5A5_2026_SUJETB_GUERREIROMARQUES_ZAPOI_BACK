# Contrat d'API — Plateforme de tournois (R5A5, sujet B)

**Version 3 — contrat figé.**

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
| Authentification | En-tête `Authorization: Bearer <jeton>`. |
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

---

## 2. Authentification

### `POST /api/auth/inscription`

Public.

```json
// Entrée
{ "pseudo": "alice", "email": "alice@iut.fr", "motDePasse": "…" }

// 201
{ "jeton": "eyJ…", "utilisateur": { "idUtilisateur": 1, "pseudo": "alice",
  "email": "alice@iut.fr", "estAdministrateur": false } }
```

`409` si le pseudo ou l'e-mail est déjà pris.

### `POST /api/auth/connexion`

Public. Entrée `{ "email", "motDePasse" }`, sortie identique à l'inscription.

`401` en cas d'échec — **avec le même message que l'e-mail soit inconnu ou le
mot de passe faux.** Distinguer les deux permettrait d'énumérer les comptes.

### `GET /api/auth/moi`

Authentifié. Renvoie l'utilisateur du jeton. Sert au front à restaurer sa
session au rechargement de la page.

### 2.1 Cycle de vie du jeton

**Un seul jeton, valable 12 heures, sans jeton de rafraîchissement.** À
expiration, le front reçoit `401`, efface le jeton et redirige vers l'écran de
connexion.

Douze heures parce qu'un tournoi se joue sur une soirée : personne ne doit être
déconnecté au milieu d'une demi-finale. Le rafraîchissement automatique suppose
un second jeton, son stockage, sa rotation, sa révocation et une route dédiée :
beaucoup de mécanique pour un outil utilisé le temps d'une compétition.

### 2.2 Ce que le jeton contient — et ne contient pas

```json
{ "sub": "1", "ver": 3, "iat": 1789650000, "exp": 1789693200 }
```

| Claim | Rôle |
|---|---|
| `sub` | Identifiant de l'utilisateur |
| `ver` | Valeur de `utilisateur.version_jeton` à l'émission (§2.3) |
| `iat` / `exp` | Émission et expiration |

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
| `DELETE /api/equipes/{id}/membres/{idUtilisateur}` | Capitaine, ou le membre lui-même | B-06, B-09, B-17 |

### `POST /api/tournois/{id}/equipes`

```json
{ "nomEquipe": "Les Rouges", "idRole": 3 }
```

Le créateur devient capitaine **et** premier membre, dans la même transaction
(B-05). `idRole` est son poste de jeu.

- `409` si les inscriptions sont closes, ou si le nom est déjà pris dans ce tournoi.
- `422` si le joueur appartient déjà à une équipe de ce tournoi (B-07).

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

- `403` si l'appelant n'est pas administrateur — **à tester** (B-13).
- `409` si la rencontre n'est pas `JOUABLE`, ou est déjà `TERMINE`.
- `422` si `idVainqueur` ne participe pas à cette rencontre.

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

**Pagination : aucune.** `GET` renvoie tous les messages de l'équipe, du plus
ancien au plus récent. Un tournoi dure une soirée, le volume reste faible. Si ça
devenait un problème, l'ajout se ferait par un paramètre `avant=<idMessage>`
sans casser l'existant.

---

## 7. Temps réel

Les événements poussés font autant partie du contrat que les routes HTTP.

**Connexion** : le client se connecte au WebSocket en présentant son jeton. Le
serveur l'authentifie à la connexion **et** à chaque abonnement.

**Salons**

| Salon | Qui peut s'y abonner |
|---|---|
| `tournoi:{idTournoi}` | Tout le monde, même non connecté (B-19) |
| `equipe:{idEquipe}` | Membres de l'équipe uniquement, selon la règle du §6 |

**Événements serveur → client**

| Événement | Charge | Quand |
|---|---|---|
| `message:nouveau` | Objet `Message` complet | Un membre poste (B-16) |
| `rencontre:maj` | Objet `Rencontre` complet | Un résultat est validé (B-14, B-19) |
| `tournoi:maj` | Objet `Tournoi` complet | Changement d'état (B-03, B-04) |
| `equipe:acces-revoque` | `{ "idEquipe": 4, "motif": "exclusion" \| "elimination" \| "disqualification" }` | Le destinataire perd l'accès (B-17, B-18) |

**Les charges contiennent l'objet complet**, pas seulement un identifiant : le
client affiche directement sans second aller-retour. C'est sans risque ici,
aucun de ces objets ne contient d'information sensible, et l'abonnement au salon
a déjà été autorisé.

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
| B-08 | `PATCH …/membres/{id}` (`idRole`), contrôle des 5 joueurs au lancement |
| B-09 | `PATCH /api/equipes/{id}`, `PATCH …/membres/{id}`, `DELETE …/membres/{id}` |
| B-10 | `403` sur les routes d'équipe, et liste blanche de champs — **à tester** |
| B-11 | `409` sur toutes les écritures d'équipe après clôture |
| B-12 | Généré par la transition `INSCRIPTIONS_CLOSES`, lu par `GET …/arbre` |
| B-13 | `403` sur `PATCH /api/rencontres/{id}` — **à tester** |
| B-14 | Propagation dans `PATCH /api/rencontres/{id}` |
| B-15 | `PATCH /api/rencontres/{id}` avec `typeResultat: "FORFAIT"` |
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

Ce document est figé. Toute modification ultérieure est un changement de
contrat : annoncée à l'autre, répercutée des deux côtés dans la même séance.
