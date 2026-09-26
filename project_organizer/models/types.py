"""Types de colonnes partagés par les modèles."""

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.types import TypeDecorator


class EnumPostgres(TypeDecorator):
    """Colonne d'un type ENUM déjà créé par le script SQL.

    pg8000 envoie les paramètres en VARCHAR, et PostgreSQL refuse de comparer
    ou d'écrire un VARCHAR dans un ENUM sans conversion. Chaque valeur envoyée
    est donc convertie explicitement : CAST(… AS statut_tournoi).
    """

    impl = ENUM
    cache_ok = True

    def __init__(self, *valeurs: str, nom: str):
        super().__init__(*valeurs, name=nom, create_type=False)

    def bind_expression(self, valeur_liee):
        return cast(valeur_liee, self.impl)
