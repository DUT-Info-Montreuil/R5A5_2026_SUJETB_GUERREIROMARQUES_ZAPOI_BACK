"""
Réponse de GET /health.

La traduction snake_case → camelCase est faite par ModeleApi : ni le
contrôleur ni le service ne manipulent de clé en camelCase.
"""

from typing import Literal

from pydantic import Field

from ..services.sante_service import EtatBase
from .base import ModeleApi


class EtatBaseDto(ModeleApi):
    joignable: bool
    version_postgres: str | None = Field(None, examples=["16.4"])
    tables: int | None = Field(None, description="Nombre de tables du schéma public", examples=[9])
    schema_complet: bool | None = Field(None, description="Vrai si les 9 tables du schéma sont présentes")


class EtatSanteDto(ModeleApi):
    statut: Literal["ok", "degrade"]
    base_de_donnees: EtatBaseDto


def sante_vers_dto(etat: EtatBase) -> EtatSanteDto:
    return EtatSanteDto(
        statut="ok",
        base_de_donnees=EtatBaseDto(
            joignable=True,
            version_postgres=etat.version_postgres,
            tables=etat.tables,
            schema_complet=etat.schema_complet,
        ),
    )


def sante_degradee_dto() -> EtatSanteDto:
    """Aucun détail technique : il est dans les logs, jamais dans la réponse."""
    return EtatSanteDto(statut="degrade", base_de_donnees=EtatBaseDto(joignable=False))