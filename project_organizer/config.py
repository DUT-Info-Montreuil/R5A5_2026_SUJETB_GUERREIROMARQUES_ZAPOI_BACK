"""
Configuration de l'application, lue depuis les variables d'environnement.

Rien n'est écrit en dur ici : toutes les valeurs viennent du fichier .env, qui
n'est pas versionné. C'est ce qui permet à chacun (et au correcteur) de lancer
le projet avec ses propres paramètres sans modifier une ligne de code.
"""

import os

from dotenv import load_dotenv

# Charge le .env situé à la racine du dépôt, s'il existe.
load_dotenv()


class ConfigurationManquante(RuntimeError):
    """Levée au démarrage quand une variable obligatoire est absente."""


def _obligatoire(nom: str) -> str:
    """Lit une variable d'environnement, ou échoue avec un message explicite.

    On échoue au démarrage plutôt qu'à la première requête : un serveur qui
    démarre avec une configuration incomplète produit des erreurs beaucoup plus
    difficiles à diagnostiquer.
    """
    valeur = os.getenv(nom)
    if not valeur:
        raise ConfigurationManquante(
            f"Variable d'environnement manquante : {nom}.\n"
            f"Copiez .env.example en .env et renseignez-la."
        )
    return valeur


def _optionnel(nom: str, defaut: str) -> str:
    return os.getenv(nom) or defaut


class Config:
    """Configuration de développement et de production."""

    DATABASE_URL: str = _obligatoire("DATABASE_URL")
    SECRET_KEY: str = _obligatoire("FLASK_SECRET_KEY")

    # Origines autorisées pour les appels depuis le front.
    # Liste explicite : on n'autorise jamais "*" sur une API authentifiée.
    CORS_ORIGINS: list[str] = [
        origine.strip()
        for origine in _optionnel("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origine.strip()
    ]

    JWT_DUREE_MINUTES: int = int(_optionnel("JWT_EXPIRATION_MINUTES", "720"))

    # Cookie « Secure » : envoyé uniquement en HTTPS. Désactivé en développement,
    # où l'API tourne en HTTP ; à activer dès qu'il y a un certificat.
    COOKIE_SECURE: bool = _optionnel("COOKIE_SECURE", "false").lower() == "true"

    # Freine la force brute sur la connexion et l'inscription (cours, § limitation de débit).
    LIMITE_CONNEXION: str = _optionnel("LIMITE_CONNEXION", "5 per minute")

    DEBUG: bool = _optionnel("FLASK_DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = _optionnel("LOG_LEVEL", "INFO").upper()
    PORT: int = int(_optionnel("PORT", "5000"))
