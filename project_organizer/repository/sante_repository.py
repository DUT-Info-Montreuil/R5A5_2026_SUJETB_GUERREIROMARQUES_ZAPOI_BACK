"""
Accès base pour le diagnostic.

Exemple de la partie « SQL écrit à la main » de l'approche mixte : ces requêtes
interrogent les métadonnées de PostgreSQL, ce qu'aucun modèle ORM ne couvre.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def ping(session: Session) -> bool:
    """Aller-retour complet avec PostgreSQL : échoue si la base est éteinte."""
    return session.execute(text("SELECT 1")).scalar_one() == 1


def compter_tables(session: Session) -> int:
    """Nombre de tables du schéma public — 9 une fois sql/01_schema.sql appliqué.

    0 signifie presque toujours que la connexion pointe sur la mauvaise base
    (« postgres » au lieu de « tournois »).
    """
    return session.execute(
        text(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
    ).scalar_one()


def version_postgres(session: Session) -> str:
    return session.execute(text("SHOW server_version")).scalar_one()
