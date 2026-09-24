"""
Service de diagnostic.

La couche service porte les règles et orchestre le repository. Elle ne connaît
ni Flask, ni HTTP, ni les codes de statut : c'est ce qui la rend testable sans
serveur, et réutilisable par le canal WebSocket.
"""

import logging
from dataclasses import dataclass

from ..repository import sante_repository
from ..utils import database

logger = logging.getLogger(__name__)

NOMBRE_TABLES_ATTENDU = 9


class BaseInjoignable(Exception):
    """PostgreSQL ne répond pas, ou la connexion est mal configurée."""


@dataclass(frozen=True)
class EtatBase:
    version_postgres: str
    tables: int

    @property
    def schema_complet(self) -> bool:
        return self.tables == NOMBRE_TABLES_ATTENDU


def etat_de_la_base() -> EtatBase:
    """Interroge la base. Lève BaseInjoignable si elle ne répond pas."""
    try:
        with database.session() as session:
            sante_repository.ping(session)
            etat = EtatBase(
                version_postgres=sante_repository.version_postgres(session),
                tables=sante_repository.compter_tables(session),
            )
    except Exception as erreur:
        # Le détail technique va dans les logs, jamais dans la réponse :
        # il exposerait l'hôte, le port et le pilote utilisés.
        logger.error("Base de données injoignable", extra={"contexte": {"erreur": str(erreur)}})
        raise BaseInjoignable from erreur

    if not etat.schema_complet:
        logger.warning(
            "Schéma incomplet",
            extra={"contexte": {"tablesTrouvees": etat.tables, "tablesAttendues": NOMBRE_TABLES_ATTENDU}},
        )
    return etat
