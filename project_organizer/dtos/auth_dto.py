"""Corps et réponses des routes d'authentification (contrat §2)."""

from pydantic import Field

from ..models import Utilisateur
from .base import ModeleApi, ModeleEntree

# Longueur plutôt que complexité imposée (cours, « La politique de mot de passe ») ;
# la borne haute évite seulement de hacher des mégaoctets.
MOT_DE_PASSE_LONGUEUR_MIN = 12
MOT_DE_PASSE_LONGUEUR_MAX = 128


class InscriptionDto(ModeleEntree):
    """Corps de POST /api/auth/inscription : pseudo, e-mail et mot de passe (12 caractères minimum)."""
    pseudo: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$", examples=["kairo"])
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", examples=["kairo@iut.fr"])
    mot_de_passe: str = Field(min_length=MOT_DE_PASSE_LONGUEUR_MIN, max_length=MOT_DE_PASSE_LONGUEUR_MAX)


class ConnexionDto(ModeleEntree):
    """Corps de POST /api/auth/connexion : e-mail et mot de passe."""
    email: str = Field(max_length=255, examples=["kairo@iut.fr"])
    mot_de_passe: str = Field(min_length=1, max_length=MOT_DE_PASSE_LONGUEUR_MAX)


class UtilisateurDto(ModeleApi):
    """L'utilisateur connecté : identité et rôle. Jamais de mot de passe ni d'empreinte."""
    id_utilisateur: int
    pseudo: str
    email: str
    est_administrateur: bool


class ReponseAuthentificationDto(ModeleApi):
    """Le jeton n'est pas dans le corps : il part dans un cookie HttpOnly."""
    utilisateur: UtilisateurDto


def utilisateur_vers_dto(utilisateur: Utilisateur) -> UtilisateurDto:
    """Convertit le modèle Utilisateur en réponse d'API (sans mot de passe)."""
    return UtilisateurDto(
        id_utilisateur=utilisateur.id_utilisateur,
        pseudo=utilisateur.pseudo,
        email=utilisateur.email,
        est_administrateur=utilisateur.est_administrateur,
    )
