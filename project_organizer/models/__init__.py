"""
Modèles ORM — la correspondance entre classes Python et tables.

Un fichier par table : `<table>.py`, une classe qui hérite de
`utils.database.Base`.

Les tables existent déjà : sql/schema_R5A5_sujetB.sql est la source de vérité.
On n'appelle jamais Base.metadata.create_all(). Toute évolution du schéma se
fait d'abord dans le script SQL, puis dans le modèle.
"""

from .composer import Composer
from .demande_adhesion import DemandeAdhesion
from .equipe import Equipe
from .jeu import Jeu
from .message import Message
from .rencontre import Rencontre
from .role_jeu import RoleJeu
from .tournoi import Tournoi
from .utilisateur import Utilisateur

__all__ = [
    "Composer",
    "DemandeAdhesion",
    "Equipe",
    "Jeu",
    "Message",
    "Rencontre",
    "RoleJeu",
    "Tournoi",
    "Utilisateur",
]