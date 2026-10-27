-- =============================================================================
--  Données de démonstration — développement uniquement
--
--  À jouer À LA MAIN, sur une base déjà créée :
--
--      Get-Content sql\demo\donnees_demo.sql | docker compose exec -T db psql -U r5a5 -d tournois
--
--  Ce script vit dans sql/demo/ et non dans sql/ : PostgreSQL ne joue à la
--  création du conteneur que les fichiers situés directement dans sql/, par
--  ordre alphabétique. Dans sql/, celui-ci passerait AVANT le schéma et ferait
--  échouer l'initialisation de la base.
--
--  Rejouable sans risque : les données déjà présentes ne sont pas dupliquées,
--  et les postes des jeux sont ajoutés même si le reste existait déjà.
--
--  Compte administrateur créé :
--      e-mail        admin@agon-cup.fr
--      mot de passe  admin-demo-2026
--  Mot de passe connu de tous : ne jamais jouer ce script ailleurs qu'en local.
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM utilisateur WHERE email = 'admin@agon-cup.fr') THEN
        RAISE NOTICE 'Données de démonstration déjà présentes : rien à faire.';
        RETURN;
    END IF;

    INSERT INTO utilisateur (pseudo, email, mot_de_passe_hash, est_administrateur)
    VALUES ('admin', 'admin@agon-cup.fr',
            '$argon2id$v=19$m=65536,t=3,p=4$ZU+Iv74Bg6MCak3kOk/RoA$mnxOPvcRyBqQjIo9A/wMmw0HgoDZv1wnB6uQ6zZEluU', TRUE);

    INSERT INTO jeu (nom_jeu, joueurs_par_equipe) VALUES
        ('League of Legends', 5), ('Overwatch 2', 5), ('Valorant', 5),
        ('Counter-Strike 2', 5), ('Dota 2', 5)
    ON CONFLICT (nom_jeu) DO NOTHING;

    INSERT INTO tournoi (nom_tournoi, id_jeu, statut_tournoi, cree_par,
                         cree_le, inscriptions_closes_le, demarre_le, termine_le)
    SELECT t.nom, j.id_jeu, t.statut::statut_tournoi, u.id_utilisateur,
           t.cree_le, t.closes_le, t.demarre_le, t.termine_le
    FROM (VALUES
        ('Coupe Inter-IUT — Automne 2026', 'League of Legends', 'EN_COURS',
            TIMESTAMPTZ '2026-09-01 18:00+02', TIMESTAMPTZ '2026-09-20 18:00+02', TIMESTAMPTZ '2026-09-24 18:00+02', NULL::TIMESTAMPTZ),
        ('Nuit CS2 des IUT', 'Counter-Strike 2', 'INSCRIPTIONS_CLOSES',
            TIMESTAMPTZ '2026-09-10 18:00+02', TIMESTAMPTZ '2026-09-25 18:00+02', NULL, NULL),
        ('Open Overwatch 2 — Automne', 'Overwatch 2', 'INSCRIPTIONS_OUVERTES',
            TIMESTAMPTZ '2026-09-15 18:00+02', NULL, NULL, NULL),
        ('Valorant Clash des IUT', 'Valorant', 'INSCRIPTIONS_OUVERTES',
            TIMESTAMPTZ '2026-09-18 18:00+02', NULL, NULL, NULL),
        ('Dota 2 Découverte', 'Dota 2', 'INSCRIPTIONS_OUVERTES',
            TIMESTAMPTZ '2026-09-22 18:00+02', NULL, NULL, NULL),
        ('Coupe Inter-IUT — Printemps 2026', 'League of Legends', 'TERMINE',
            TIMESTAMPTZ '2026-03-01 18:00+01', TIMESTAMPTZ '2026-04-01 18:00+02', TIMESTAMPTZ '2026-04-10 18:00+02', TIMESTAMPTZ '2026-04-18 22:00+02')
    ) AS t (nom, jeu, statut, cree_le, closes_le, demarre_le, termine_le)
    JOIN jeu j ON j.nom_jeu = t.jeu
    CROSS JOIN (SELECT id_utilisateur FROM utilisateur WHERE email = 'admin@agon-cup.fr') u;

    -- Équipes, sans joueurs : de quoi afficher « n / 8 équipes ».
    INSERT INTO equipe (id_tournoi, nom_equipe)
    SELECT tr.id_tournoi, e.nom
    FROM (VALUES
        ('Coupe Inter-IUT — Automne 2026', ARRAY['Hiboux','Nova','Zenith','Nébula','Orage','Kraken','Phénix','Titans']),
        ('Nuit CS2 des IUT',               ARRAY['Hiboux','Nova','Zenith','Nébula','Orage','Kraken','Phénix','Titans']),
        ('Open Overwatch 2 — Automne',     ARRAY['Hiboux','Nova','Zenith','Nébula','Orage']),
        ('Valorant Clash des IUT',         ARRAY['Kraken','Phénix','Titans']),
        ('Dota 2 Découverte',              ARRAY['Orage']),
        ('Coupe Inter-IUT — Printemps 2026', ARRAY['Hiboux','Nova','Zenith','Nébula','Orage','Kraken','Phénix','Titans'])
    ) AS x (tournoi, equipes)
    JOIN tournoi tr ON tr.nom_tournoi = x.tournoi
    CROSS JOIN LATERAL unnest(x.equipes) AS e (nom);

    RAISE NOTICE 'Données de démonstration ajoutées.';
END
$$;


-- -----------------------------------------------------------------------------
--  Postes des jeux de démonstration
--
--  Hors du bloc ci-dessus pour que les bases créées avant l'ajout des postes les
--  reçoivent aussi. Sans poste, personne ne peut créer d'équipe pour ces jeux :
--  la création d'équipe exige un poste du jeu (B-05, B-08).
--  League of Legends et Overwatch 2 reçoivent les leurs du schéma.
-- -----------------------------------------------------------------------------

INSERT INTO role_jeu (id_jeu, libelle_role)
SELECT j.id_jeu, r.libelle
FROM jeu j
JOIN (VALUES
    ('Valorant',         'Duelliste'),
    ('Valorant',         'Initiateur'),
    ('Valorant',         'Controleur'),
    ('Valorant',         'Sentinelle'),
    ('Valorant',         'Polyvalent'),
    ('Counter-Strike 2', 'Entry'),
    ('Counter-Strike 2', 'AWPer'),
    ('Counter-Strike 2', 'Lurker'),
    ('Counter-Strike 2', 'Support'),
    ('Counter-Strike 2', 'Leader'),
    ('Dota 2',           'Carry'),
    ('Dota 2',           'Mid'),
    ('Dota 2',           'Offlane'),
    ('Dota 2',           'Soutien 4'),
    ('Dota 2',           'Soutien 5')
) AS r(jeu, libelle) ON r.jeu = j.nom_jeu
ON CONFLICT (id_jeu, libelle_role) DO NOTHING;