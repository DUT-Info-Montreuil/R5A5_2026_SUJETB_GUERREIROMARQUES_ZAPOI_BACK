-- =============================================================================
--  R5A5 — Sujet B : vérification des contraintes d'intégrité
-- =============================================================================
--
--  Ce script tente délibérément d'insérer des données INVALIDES.
--  Chaque test affiche « OK » si la base a bien REFUSÉ l'insertion.
--  Si un test affiche « ECHEC », le script s'arrête : la contrainte
--  correspondante ne protège pas ce qu'elle devrait.
--
--  Lancement :
--      psql -U postgres -d tournois -v ON_ERROR_STOP=1 -f tests_contraintes.sql
--
--  Tout est annulé à la fin (ROLLBACK) : la base reste propre.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
--  Jeu d'essai
-- -----------------------------------------------------------------------------

INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash, est_administrateur)
VALUES ('admin', 'admin@iut.fr', 'hash', TRUE),
       ('alice', 'alice@iut.fr', 'hash', FALSE),
       ('bob',   'bob@iut.fr',   'hash', FALSE);

INSERT INTO tournoi (nom_tournoi, id_jeu, cree_par)
SELECT 'Coupe de printemps', j.id_jeu, u.id_utilisateur
FROM jeu j, utilisateur u
WHERE j.nom_jeu = 'League of Legends' AND u.pseudo = 'admin';

INSERT INTO tournoi (nom_tournoi, id_jeu, cree_par)
SELECT 'Coupe d''automne', j.id_jeu, u.id_utilisateur
FROM jeu j, utilisateur u
WHERE j.nom_jeu = 'League of Legends' AND u.pseudo = 'admin';

INSERT INTO equipe (id_tournoi, nom_equipe)
SELECT id_tournoi, 'Les Rouges' FROM tournoi WHERE nom_tournoi = 'Coupe de printemps';

INSERT INTO equipe (id_tournoi, nom_equipe)
SELECT id_tournoi, 'Les Bleus'  FROM tournoi WHERE nom_tournoi = 'Coupe de printemps';

INSERT INTO equipe (id_tournoi, nom_equipe)
SELECT id_tournoi, 'Les Verts'  FROM tournoi WHERE nom_tournoi = 'Coupe d''automne';

-- Alice est capitaine des Rouges, au poste Top
INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, id_role, est_capitaine)
SELECT e.id_equipe, e.id_tournoi, u.id_utilisateur, r.id_role, TRUE
FROM equipe e, utilisateur u, role_jeu r, jeu j
WHERE e.nom_equipe = 'Les Rouges' AND u.pseudo = 'alice'
  AND r.libelle_role = 'Top' AND r.id_jeu = j.id_jeu
  AND j.nom_jeu = 'League of Legends';

-- Bob est simple membre des Rouges, au poste Mid
INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, id_role, est_capitaine)
SELECT e.id_equipe, e.id_tournoi, u.id_utilisateur, r.id_role, FALSE
FROM equipe e, utilisateur u, role_jeu r, jeu j
WHERE e.nom_equipe = 'Les Rouges' AND u.pseudo = 'bob'
  AND r.libelle_role = 'Mid' AND r.id_jeu = j.id_jeu
  AND j.nom_jeu = 'League of Legends';


-- =============================================================================
--  TEST 1 — B-07 : un joueur dans une seule équipe par tournoi
-- =============================================================================
DO $$
BEGIN
    INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, est_capitaine)
    SELECT e.id_equipe, e.id_tournoi, u.id_utilisateur, FALSE
    FROM equipe e, utilisateur u
    WHERE e.nom_equipe = 'Les Bleus' AND u.pseudo = 'alice';

    RAISE EXCEPTION 'TEST 1 ECHEC : Alice a pu rejoindre deux équipes du même tournoi';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'TEST 1 OK   : B-07 respectée (deuxième équipe refusée)';
END $$;


-- =============================================================================
--  TEST 2 — B-09 : un seul capitaine par équipe (index unique partiel)
-- =============================================================================
DO $$
BEGIN
    UPDATE composer SET est_capitaine = TRUE
    WHERE id_utilisateur = (SELECT id_utilisateur FROM utilisateur WHERE pseudo = 'bob');

    RAISE EXCEPTION 'TEST 2 ECHEC : deux capitaines acceptés dans la même équipe';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'TEST 2 OK   : un seul capitaine par équipe';
END $$;


-- =============================================================================
--  TEST 3 — B-08 : un poste n'est tenu que par un joueur dans l'équipe
-- =============================================================================
DO $$
BEGIN
    UPDATE composer
    SET id_role = (SELECT r.id_role FROM role_jeu r, jeu j
                   WHERE r.libelle_role = 'Top' AND r.id_jeu = j.id_jeu
                     AND j.nom_jeu = 'League of Legends')
    WHERE id_utilisateur = (SELECT id_utilisateur FROM utilisateur WHERE pseudo = 'bob');

    RAISE EXCEPTION 'TEST 3 ECHEC : deux joueurs au même poste dans l''équipe';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'TEST 3 OK   : un poste par joueur dans l''équipe';
END $$;


-- =============================================================================
--  TEST 4 — FK composite : impossible de mentir sur le tournoi d'une équipe
--           (c'est elle qui rend le TEST 1 réellement fiable)
-- =============================================================================
DO $$
BEGIN
    INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, est_capitaine)
    SELECT e.id_equipe,
           (SELECT id_tournoi FROM tournoi WHERE nom_tournoi = 'Coupe d''automne'),
           u.id_utilisateur, FALSE
    FROM equipe e, utilisateur u
    WHERE e.nom_equipe = 'Les Bleus' AND u.pseudo = 'admin';

    RAISE EXCEPTION 'TEST 4 ECHEC : un membre a pu être rattaché au mauvais tournoi';
EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'TEST 4 OK   : le tournoi du membre doit être celui de son équipe';
END $$;


-- =============================================================================
--  TEST 5 — Un motif de sortie n'a de sens que pour une équipe disqualifiée
-- =============================================================================
DO $$
BEGIN
    UPDATE equipe SET motif_sortie = 'Comportement inapproprié'
    WHERE nom_equipe = 'Les Bleus';

    RAISE EXCEPTION 'TEST 5 ECHEC : motif accepté sur une équipe non disqualifiée';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'TEST 5 OK   : motif réservé aux équipes disqualifiées';
END $$;


-- =============================================================================
--  TEST 6 — Une équipe ne s'affronte pas elle-même
-- =============================================================================
DO $$
BEGIN
    INSERT INTO rencontre (id_tournoi, tour, position, id_equipe_a, id_equipe_b)
    SELECT e.id_tournoi, 1, 1, e.id_equipe, e.id_equipe
    FROM equipe e WHERE e.nom_equipe = 'Les Rouges';

    RAISE EXCEPTION 'TEST 6 ECHEC : une équipe a pu s''affronter elle-même';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'TEST 6 OK   : deux équipes distinctes exigées';
END $$;


-- =============================================================================
--  TEST 7 — Le vainqueur est forcément l'un des deux participants
-- =============================================================================
DO $$
BEGIN
    INSERT INTO rencontre (id_tournoi, tour, position,
                           id_equipe_a, id_equipe_b, id_vainqueur,
                           statut_rencontre, type_resultat, valide_le)
    SELECT t.id_tournoi, 1, 1,
           (SELECT id_equipe FROM equipe WHERE nom_equipe = 'Les Rouges'),
           (SELECT id_equipe FROM equipe WHERE nom_equipe = 'Les Bleus'),
           (SELECT id_equipe FROM equipe WHERE nom_equipe = 'Les Verts'),
           'TERMINE', 'NORMAL', now()
    FROM tournoi t WHERE t.nom_tournoi = 'Coupe de printemps';

    RAISE EXCEPTION 'TEST 7 ECHEC : une équipe extérieure a pu gagner la rencontre';
EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'TEST 7 OK   : le vainqueur est l''un des deux participants';
END $$;


-- =============================================================================
--  TEST 8 — Une seule demande EN ATTENTE par couple (équipe, joueur)
-- =============================================================================
INSERT INTO demande_adhesion (id_equipe, id_utilisateur)
SELECT e.id_equipe, u.id_utilisateur
FROM equipe e, utilisateur u
WHERE e.nom_equipe = 'Les Bleus' AND u.pseudo = 'admin';

DO $$
BEGIN
    INSERT INTO demande_adhesion (id_equipe, id_utilisateur)
    SELECT e.id_equipe, u.id_utilisateur
    FROM equipe e, utilisateur u
    WHERE e.nom_equipe = 'Les Bleus' AND u.pseudo = 'admin';

    RAISE EXCEPTION 'TEST 8 ECHEC : deux demandes en attente pour le même couple';
EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'TEST 8 OK   : une seule demande en attente à la fois';
END $$;


-- =============================================================================
--  TEST 9 — Un joueur refusé doit pouvoir REPOSTULER
--           (c'est ce qui justifie l'index PARTIEL au lieu d'un UNIQUE simple)
-- =============================================================================
DO $$
BEGIN
    UPDATE demande_adhesion SET statut_demande = 'REFUSEE', traite_le = now();

    INSERT INTO demande_adhesion (id_equipe, id_utilisateur)
    SELECT e.id_equipe, u.id_utilisateur
    FROM equipe e, utilisateur u
    WHERE e.nom_equipe = 'Les Bleus' AND u.pseudo = 'admin';

    RAISE NOTICE 'TEST 9 OK   : un joueur refusé peut repostuler';
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'TEST 9 ECHEC : impossible de repostuler après un refus';
END $$;


-- =============================================================================
--  TEST 10 — B-07 ne doit PAS empêcher de jouer dans plusieurs tournois
-- =============================================================================
DO $$
BEGIN
    INSERT INTO composer (id_equipe, id_tournoi, id_utilisateur, est_capitaine)
    SELECT e.id_equipe, e.id_tournoi, u.id_utilisateur, TRUE
    FROM equipe e, utilisateur u
    WHERE e.nom_equipe = 'Les Verts' AND u.pseudo = 'alice';

    RAISE NOTICE 'TEST 10 OK  : Alice peut jouer dans un second tournoi';
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'TEST 10 ECHEC : B-07 est trop stricte, elle bloque les autres tournois';
END $$;


ROLLBACK;

\echo ''
\echo '>>> Tous les tests sont passés. La base est restée propre (ROLLBACK).'