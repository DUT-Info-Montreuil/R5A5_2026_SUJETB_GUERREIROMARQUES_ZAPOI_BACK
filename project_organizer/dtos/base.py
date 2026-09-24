"""
Modèles de base de tous les DTOs.

Un DTO Pydantic est la source unique de trois choses : la validation de ce
qui entre, le typage du code, et la documentation OpenAPI. Modifier un DTO
met les trois à jour ensemble.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ModeleApi(BaseModel):
    """Champs en snake_case côté Python, en camelCase dans le JSON (contrat §1)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def vers_json(self) -> dict:
        # exclude_none : un champ sans valeur est omis plutôt qu'envoyé à null.
        # mode="json" : dates en ISO 8601 (contrat §1) ; sans lui, Flask les
        # écrirait au format « Thu, 17 Sep 2026 12:30:00 GMT ».
        # exclude_none : un champ sans valeur est omis plutôt qu'envoyé à null.
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ModeleEntree(ModeleApi):
    """Corps de requête : un champ inconnu est refusé (contrat §1.4, règle 3)."""

    model_config = ConfigDict(extra="forbid")


class ErreurDto(ModeleApi):
    """Forme unique des erreurs (contrat §1.1), à déclarer pour chaque code
    d'erreur d'une route : la documentation liste alors toutes ses erreurs."""

    erreur: str = Field(examples=["Not Found"])
    detail: Any = Field(None, examples=["Tournoi introuvable."])