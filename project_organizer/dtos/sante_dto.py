"""
Mise en forme de la réponse de diagnostic.

Un DTO fait la frontière entre le Python (snake_case, objets du service) et le
JSON échangé avec le front (camelCase, contrat d'API §1). C'est le seul endroit
où cette traduction a lieu : ni le contrôleur ni le service ne la font.
"""

from ..services.sante_service import EtatBase


def sante_vers_dto(etat: EtatBase) -> dict:
    return {
        "statut": "ok",
        "baseDeDonnees": {
            "joignable": True,
            "versionPostgres": etat.version_postgres,
            "tables": etat.tables,
            "schemaComplet": etat.schema_complet,
        },
    }


def sante_degradee_dto() -> dict:
    """Aucun détail technique : il est dans les logs, jamais dans la réponse."""
    return {"statut": "degrade", "baseDeDonnees": {"joignable": False}}
