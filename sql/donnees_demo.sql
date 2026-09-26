-- =============================================================================
--  Données de démonstration — développement uniquement
--
--  À jouer À LA MAIN, une fois, sur une base déjà créée (voir README §5).
--  Ce script n'est PAS dans l'initialisation du conteneur : la base de test
--  reste vide par défaut.
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
