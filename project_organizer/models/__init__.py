"""
Modèles ORM — la correspondance entre classes Python et tables.

Un fichier par table : `<table>.py`, une classe qui hérite de
`utils.database.Base`.

Les tables existent déjà : sql/01_schema.sql est la source de vérité. On
n'appelle jamais Base.metadata.create_all(). Toute évolution du schéma se fait
d'abord dans le script SQL, puis dans le modèle.
"""

from .composer import Composer
from .equipe import Equipe
from .jeu import Jeu
from .rencontre import Rencontre
from .tournoi import Tournoi
from .utilisateur import Utilisateur

__all__ = ["Composer", "Equipe", "Jeu", "Rencontre", "Tournoi", "Utilisateur"]
