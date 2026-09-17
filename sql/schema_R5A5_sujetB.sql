-- =============================================================================
--  R5A5 2026-2027 — Sujet B : plateforme de tournois
--  Schéma PostgreSQL complet
-- =============================================================================
--
--  Ce script n'est PAS la sortie brute de JMerise. Les retouches de la section 4
--  du document MCD y sont déjà intégrées, parce que le formalisme Merise ne sait
--  pas les exprimer :
--
--    - clé primaire de « composer » ramenée à (equipe, utilisateur)
--    - index unique partiel garantissant un seul capitaine par équipe
--    - dénormalisation de id_tournoi + FK composite pour la règle B-07
--    - index unique partiel sur les demandes en attente
--    - TIMESTAMPTZ au lieu de TIMESTAMP
--    - types ENUM au lieu de VARCHAR, et contraintes CHECK de cohérence
--
--  Testé sur PostgreSQL 14+.
-- =============================================================================


-- -----------------------------------------------------------------------------
--  Réinitialisation (développement uniquement — à retirer en production)
-- -----------------------------------------------------------------------------

DROP TABLE IF EXISTS message           CASCADE;
DROP TABLE IF EXISTS rencontre         CASCADE;
DROP TABLE IF EXISTS demande_adhesion  CASCADE;
DROP TABLE IF EXISTS composer          CASCADE;
DROP TABLE IF EXISTS equipe            CASCADE;
DROP TABLE IF EXISTS tournoi           CASCADE;
DROP TABLE IF EXISTS role_jeu          CASCADE;
DROP TABLE IF EXISTS jeu               CASCADE;
DROP TABLE IF EXISTS utilisateur       CASCADE;

DROP TYPE IF EXISTS type_resultat   CASCADE;
DROP TYPE IF EXISTS statut_match    CASCADE;
DROP TYPE IF EXISTS statut_demande  CASCADE;
DROP TYPE IF EXISTS statut_equipe   CASCADE;
DROP TYPE IF EXISTS statut_tournoi  CASCADE;


-- =============================================================================
--  1. Types énumérés
-- =============================================================================

CREATE TYPE statut_tournoi AS ENUM (
    'INSCRIPTIONS_OUVERTES',
    'INSCRIPTIONS_CLOSES',
    'EN_COURS',
    'TERMINE'
);

CREATE TYPE statut_equipe AS ENUM (
    'EN_LICE',        -- encore en course
    'ELIMINEE',       -- a perdu sportivement
    'DISQUALIFIEE',   -- sortie par décision de l'administrateur
    'VAINQUEUR'
);

CREATE TYPE statut_demande AS ENUM (
    'EN_ATTENTE',
    'ACCEPTEE',
    'REFUSEE',
    'ANNULEE'         -- retirée par le demandeur
);

CREATE TYPE statut_match AS ENUM (
    'EN_ATTENTE',     -- aucune équipe connue
    'JOUABLE',        -- résolvable par l'administrateur
    'TERMINE'
);

CREATE TYPE type_resultat AS ENUM (
    'NORMAL',                  -- match joué
    'FORFAIT',                 -- B-04 / B-15 : l'adversaire est qualifié
    'QUALIFICATION_DIRECTE'    -- pas d'adversaire du tout
);


-- =============================================================================
--  2. Utilisateurs
-- =============================================================================

CREATE TABLE utilisateur (
    id_utilisateur      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pseudo              VARCHAR(50)  NOT NULL UNIQUE,
    email               VARCHAR(255) NOT NULL UNIQUE,
    mot_de_passe_hash   VARCHAR(255) NOT NULL,
    est_administrateur  BOOLEAN      NOT NULL DEFAULT FALSE,
    cree_le             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_utilisateur_email CHECK (position('@' IN email) > 1)
);

COMMENT ON TABLE utilisateur IS
    'Comptes. Le visiteur n''a pas de ligne : c''est l''absence d''authentification.';
COMMENT ON COLUMN utilisateur.est_administrateur IS
    'Seul rôle global. Capitaine et joueur sont contextuels (table composer).';
COMMENT ON COLUMN utilisateur.mot_de_passe_hash IS
    'Empreinte argon2 ou bcrypt. Jamais de mot de passe en clair.';


-- =============================================================================
--  3. Jeux et rôles de jeu
-- =============================================================================

CREATE TABLE jeu (
    id_jeu              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom_jeu             VARCHAR(100) NOT NULL UNIQUE,
    joueurs_par_equipe  SMALLINT     NOT NULL DEFAULT 5
        CHECK (joueurs_par_equipe > 0)
);

CREATE TABLE role_jeu (
    id_role       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_jeu        BIGINT      NOT NULL REFERENCES jeu (id_jeu) ON DELETE CASCADE,
    libelle_role  VARCHAR(50) NOT NULL,

    UNIQUE (id_jeu, libelle_role)
);

CREATE INDEX idx_role_jeu_jeu ON role_jeu (id_jeu);

COMMENT ON TABLE role_jeu IS
    'Postes numérotés quand le jeu autorise les doublons : Overwatch 2 se déclare
     Tank / Degats 1 / Degats 2 / Soutien 1 / Soutien 2, ce qui permet de garder
     l''unicité du poste dans l''équipe.';


-- =============================================================================
--  4. Tournois
-- =============================================================================

CREATE TABLE tournoi (
    id_tournoi              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom_tournoi             VARCHAR(150)   NOT NULL,
    id_jeu                  BIGINT         NOT NULL REFERENCES jeu (id_jeu),
    statut_tournoi          statut_tournoi NOT NULL
                            DEFAULT 'INSCRIPTIONS_OUVERTES',
    nombre_equipes          SMALLINT       NOT NULL DEFAULT 8
        CHECK (nombre_equipes IN (2, 4, 8, 16)),
    cree_par                BIGINT         NOT NULL
                            REFERENCES utilisateur (id_utilisateur),
    cree_le                 TIMESTAMPTZ    NOT NULL DEFAULT now(),
    inscriptions_closes_le  TIMESTAMPTZ,
    demarre_le              TIMESTAMPTZ,
    termine_le              TIMESTAMPTZ,

    -- Cohérence de la chronologie du cycle de vie
    CONSTRAINT ck_tournoi_chronologie CHECK (
        (inscriptions_closes_le IS NULL OR inscriptions_closes_le >= cree_le)
        AND (demarre_le IS NULL OR demarre_le >= inscriptions_closes_le)
        AND (termine_le IS NULL OR termine_le >= demarre_le)
    )
);

CREATE INDEX idx_tournoi_statut ON tournoi (statut_tournoi);
CREATE INDEX idx_tournoi_jeu    ON tournoi (id_jeu);
CREATE INDEX idx_tournoi_nom    ON tournoi USING gin (to_tsvector('french', nom_tournoi));

COMMENT ON COLUMN tournoi.nombre_equipes IS
    'Le sujet impose 8 (B-12). Le CHECK n''autorise que des puissances de 2 pour
     que l''arbre reste équilibré si le besoin évolue.';


-- =============================================================================
--  5. Équipes
-- =============================================================================

CREATE TABLE equipe (
    id_equipe     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tournoi    BIGINT        NOT NULL REFERENCES tournoi (id_tournoi)
                                ON DELETE CASCADE,
    nom_equipe    VARCHAR(100)  NOT NULL,
    statut_equipe statut_equipe NOT NULL DEFAULT 'EN_LICE',
    motif_sortie  TEXT,
    cree_le       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    UNIQUE (id_tournoi, nom_equipe),

    -- Clé candidate rendue explicite : sans elle, la FK composite de « composer »
    -- ne peut pas être déclarée (règle B-07)
    UNIQUE (id_equipe, id_tournoi),

    -- Un motif n'a de sens que pour une équipe disqualifiée
    CONSTRAINT ck_equipe_motif CHECK (
        motif_sortie IS NULL OR statut_equipe = 'DISQUALIFIEE'
    )
);

CREATE INDEX idx_equipe_tournoi ON equipe (id_tournoi);
CREATE INDEX idx_equipe_statut  ON equipe (id_tournoi, statut_equipe);

COMMENT ON COLUMN equipe.motif_sortie IS
    'Justification libre saisie par l''administrateur. Documentation pour
     l''historique, pas de la logique métier : absence et triche produisent le
     même effet sportif.';


-- =============================================================================
--  6. Composition des équipes  (cœur du modèle)
-- =============================================================================

CREATE TABLE composer (
    id_equipe       BIGINT      NOT NULL,
    id_tournoi      BIGINT      NOT NULL,   -- dénormalisé volontairement
    id_utilisateur  BIGINT      NOT NULL REFERENCES utilisateur (id_utilisateur)
                                ON DELETE CASCADE,
    id_role         BIGINT      REFERENCES role_jeu (id_role),
    est_capitaine   BOOLEAN     NOT NULL DEFAULT FALSE,
    rejoint_le      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- PK ramenée à deux colonnes : la PK ternaire générée par JMerise
    -- autoriserait le même joueur deux fois dans l'équipe avec deux postes
    PRIMARY KEY (id_equipe, id_utilisateur),

    -- Garantit que id_tournoi est bien celui de l'équipe : sans cette FK
    -- composite, la contrainte B-07 ci-dessous ne garantirait rien
    FOREIGN KEY (id_equipe, id_tournoi)
        REFERENCES equipe (id_equipe, id_tournoi) ON DELETE CASCADE,

    -- B-07 : un joueur n'est que dans une seule équipe par tournoi
    CONSTRAINT uq_un_joueur_par_tournoi UNIQUE (id_tournoi, id_utilisateur),

    -- B-08 : un poste n'est tenu que par un joueur dans l'équipe
    CONSTRAINT uq_composer_role UNIQUE (id_equipe, id_role)
);

-- B-09 : un seul capitaine par équipe.
-- Index unique PARTIEL : contraint uniquement les lignes où est_capitaine
-- est vrai. Inexprimable en MySQL — c'est l'un des arguments qui ont fait
-- retenir PostgreSQL.
CREATE UNIQUE INDEX idx_un_capitaine_par_equipe
    ON composer (id_equipe)
    WHERE est_capitaine;

CREATE INDEX idx_composer_utilisateur ON composer (id_utilisateur);
CREATE INDEX idx_composer_tournoi     ON composer (id_tournoi);


-- =============================================================================
--  7. Demandes d'adhésion  (B-06)
-- =============================================================================

CREATE TABLE demande_adhesion (
    id_demande      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_equipe       BIGINT         NOT NULL REFERENCES equipe (id_equipe)
                                   ON DELETE CASCADE,
    id_utilisateur  BIGINT         NOT NULL REFERENCES utilisateur (id_utilisateur)
                                   ON DELETE CASCADE,
    statut_demande  statut_demande NOT NULL DEFAULT 'EN_ATTENTE',
    cree_le         TIMESTAMPTZ    NOT NULL DEFAULT now(),
    traite_le       TIMESTAMPTZ,
    traite_par      BIGINT         REFERENCES utilisateur (id_utilisateur),

    -- Une demande traitée porte forcément une date de traitement, et inversement
    CONSTRAINT ck_demande_traitement CHECK (
        (statut_demande = 'EN_ATTENTE') = (traite_le IS NULL)
    )
);

-- Une seule demande EN ATTENTE par couple (équipe, joueur).
-- Index partiel obligatoire ici : comme on conserve l'historique des refus,
-- un UNIQUE classique empêcherait un joueur refusé de repostuler.
CREATE UNIQUE INDEX idx_demande_unique_en_attente
    ON demande_adhesion (id_equipe, id_utilisateur)
    WHERE statut_demande = 'EN_ATTENTE';

CREATE INDEX idx_demande_equipe      ON demande_adhesion (id_equipe, statut_demande);
CREATE INDEX idx_demande_utilisateur ON demande_adhesion (id_utilisateur);


-- =============================================================================
--  8. Rencontres et arbre du tournoi
-- =============================================================================

CREATE TABLE rencontre (
    id_rencontre            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tournoi              BIGINT       NOT NULL REFERENCES tournoi (id_tournoi)
                                         ON DELETE CASCADE,
    tour                    SMALLINT     NOT NULL CHECK (tour >= 1),
    position                SMALLINT     NOT NULL CHECK (position >= 1),

    id_equipe_a             BIGINT       REFERENCES equipe (id_equipe),
    id_equipe_b             BIGINT       REFERENCES equipe (id_equipe),
    id_vainqueur            BIGINT       REFERENCES equipe (id_equipe),

    statut_rencontre        statut_match  NOT NULL DEFAULT 'EN_ATTENTE',
    type_resultat           type_resultat,
    score_a                 SMALLINT     CHECK (score_a >= 0),
    score_b                 SMALLINT     CHECK (score_b >= 0),
    valide_le               TIMESTAMPTZ,

    -- Progression dans l'arbre (association réflexive « alimenter »)
    id_rencontre_suivante   BIGINT       REFERENCES rencontre (id_rencontre)
                                         ON DELETE CASCADE,
    emplacement_suivant     CHAR(1)      CHECK (emplacement_suivant IN ('A', 'B')),

    UNIQUE (id_tournoi, tour, position),

    -- Une équipe ne s'affronte pas elle-même
    CONSTRAINT ck_rencontre_equipes_distinctes CHECK (
        id_equipe_a IS NULL OR id_equipe_b IS NULL OR id_equipe_a <> id_equipe_b
    ),

    -- Le vainqueur est forcément l'un des deux participants
    CONSTRAINT ck_rencontre_vainqueur CHECK (
        id_vainqueur IS NULL
        OR id_vainqueur = id_equipe_a
        OR id_vainqueur = id_equipe_b
    ),

    -- Une rencontre terminée a un vainqueur, un type de résultat et une date
    CONSTRAINT ck_rencontre_terminee CHECK (
        (statut_rencontre = 'TERMINE') = (id_vainqueur IS NOT NULL)
    ),
    CONSTRAINT ck_rencontre_resultat CHECK (
        (id_vainqueur IS NOT NULL) = (type_resultat IS NOT NULL)
    ),
    CONSTRAINT ck_rencontre_validation CHECK (
        (id_vainqueur IS NOT NULL) = (valide_le IS NOT NULL)
    ),

    -- La finale ne mène nulle part ; toute autre rencontre a une suite complète
    CONSTRAINT ck_rencontre_suite CHECK (
        (id_rencontre_suivante IS NULL) = (emplacement_suivant IS NULL)
    ),

    -- Une rencontre n'alimente pas elle-même
    CONSTRAINT ck_rencontre_pas_de_boucle CHECK (
        id_rencontre_suivante IS NULL OR id_rencontre_suivante <> id_rencontre
    )
);

CREATE INDEX idx_rencontre_tournoi  ON rencontre (id_tournoi, tour, position);
CREATE INDEX idx_rencontre_suivante ON rencontre (id_rencontre_suivante);
CREATE INDEX idx_rencontre_equipe_a ON rencontre (id_equipe_a);
CREATE INDEX idx_rencontre_equipe_b ON rencontre (id_equipe_b);

COMMENT ON TABLE rencontre IS
    'Renommée depuis « match », qui est un mot réservé SQL. 7 lignes par tournoi
     à 8 équipes : 4 quarts + 2 demies + 1 finale, créées vides à la clôture.';
COMMENT ON COLUMN rencontre.id_rencontre_suivante IS
    'Rencontre alimentée par le vainqueur. NULL pour la finale.';
COMMENT ON COLUMN rencontre.emplacement_suivant IS
    'Côté (A ou B) occupé par le vainqueur dans la rencontre suivante.';
COMMENT ON COLUMN rencontre.score_a IS
    'Hors périmètre strict (l''administrateur saisit le vainqueur). Conservé car
     peu coûteux et utile à l''affichage.';


-- =============================================================================
--  9. Espace d'échange par équipe  (B-16 à B-18)
-- =============================================================================

CREATE TABLE message (
    id_message  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_equipe   BIGINT      NOT NULL REFERENCES equipe (id_equipe)
                            ON DELETE CASCADE,
    id_auteur   BIGINT      REFERENCES utilisateur (id_utilisateur)
                            ON DELETE SET NULL,
    contenu     TEXT        NOT NULL CHECK (length(trim(contenu)) > 0),
    envoye_le   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_message_equipe ON message (id_equipe, envoye_le DESC);

COMMENT ON COLUMN message.id_auteur IS
    'Référence utilisateur et non composer : un joueur exclu (B-17) voit sa ligne
     composer supprimée, mais ses messages doivent survivre. ON DELETE SET NULL
     pour conserver l''historique même si le compte disparaît.';


-- =============================================================================
--  10. Jeu d'essai minimal  (développement — à retirer en production)
-- =============================================================================

INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES
    ('League of Legends', 5),
    ('Overwatch 2',       5);

INSERT INTO role_jeu (id_jeu, libelle_role)
SELECT j.id_jeu, r.libelle
FROM jeu j
JOIN (VALUES
    ('League of Legends', 'Top'),
    ('League of Legends', 'Jungle'),
    ('League of Legends', 'Mid'),
    ('League of Legends', 'ADC'),
    ('League of Legends', 'Support'),
    ('Overwatch 2',       'Tank'),
    ('Overwatch 2',       'Degats 1'),
    ('Overwatch 2',       'Degats 2'),
    ('Overwatch 2',       'Soutien 1'),
    ('Overwatch 2',       'Soutien 2')
) AS r(jeu, libelle) ON r.jeu = j.nom_jeu;