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


class ConfigurationInvalide(RuntimeError):
    """Levée au démarrage quand une variable est présente mais inacceptable (clé trop faible…)."""


# HS256 : une clé plus courte que la signature (256 bits = 32 octets) s'attaque par force brute.
LONGUEUR_MIN_CLE_SECRETE = 32
# Le texte du modèle .env.example : le recopier tel quel ne doit pas démarrer un serveur.
_DEBUT_CLE_DU_MODELE = "a-remplacer"


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


def _cle_secrete(nom: str) -> str:
    """La clé de signature des jetons : obligatoire, assez longue, et différente du texte du modèle.

    Avec une clé faible ou connue, n'importe qui pourrait fabriquer un jeton
    d'administrateur. On refuse donc de démarrer, plutôt que d'avertir : un
    avertissement dans un journal que personne ne lit ne protège de rien.
    """
    cle = _obligatoire(nom)
    if len(cle) < LONGUEUR_MIN_CLE_SECRETE or cle.lower().startswith(_DEBUT_CLE_DU_MODELE):
        raise ConfigurationInvalide(
            f"{nom} est trop faible : {LONGUEUR_MIN_CLE_SECRETE} caractères minimum, et pas la valeur du modèle.\n"
            'Générez-en une : python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return cle


def _optionnel(nom: str, defaut: str) -> str:
    return os.getenv(nom) or defaut


class Config:
    """Configuration de développement et de production."""

    DATABASE_URL: str = _obligatoire("DATABASE_URL")
    SECRET_KEY: str = _cle_secrete("FLASK_SECRET_KEY")

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

    # Plafond de messages par utilisateur dans l'espace d'échange : freine l'inondation d'un chat.
    LIMITE_MESSAGES: str = _optionnel("LIMITE_MESSAGES", "30 per minute")

    # --- Temps réel (cours, « En production » et « Valider les messages entrants ») ---
    # Heartbeat : un ping toutes les 20 s, et la connexion est jugée morte si le pong n'arrive pas
    # sous 15 s. Plus court que les valeurs par défaut de Socket.IO (25 s / 20 s) : une connexion
    # morte (téléphone dans un tunnel, box redémarrée) est détectée plus vite et ne reste pas dans
    # les salons. L'intervalle reste très en dessous des 60 s du `proxy_read_timeout` de Nginx : un
    # proxy ne coupe donc jamais une connexion silencieuse mais vivante.
    SOCKET_PING_INTERVALLE_SECONDES: int = int(_optionnel("SOCKET_PING_INTERVALLE_SECONDES", "20"))
    SOCKET_PING_DELAI_SECONDES: int = int(_optionnel("SOCKET_PING_DELAI_SECONDES", "15"))
    # Taille maximale d'un message reçu du client. Les seuls messages légitimes sont des
    # identifiants : 4 Kio suffisent largement. Au-delà, la bibliothèque ferme la connexion.
    SOCKET_TAILLE_MAX_OCTETS: int = int(_optionnel("SOCKET_TAILLE_MAX_OCTETS", "4096"))
    # Plafond d'événements par connexion : au-delà, elle est coupée. Un client normal en émet
    # quelques-uns par changement de page.
    SOCKET_EVENEMENTS_MAX: int = int(_optionnel("SOCKET_EVENEMENTS_MAX", "30"))
    SOCKET_FENETRE_DEBIT_SECONDES: int = int(_optionnel("SOCKET_FENETRE_DEBIT_SECONDES", "10"))
    # Fréquence à laquelle le serveur ferme les connexions dont le jeton a expiré.
    SOCKET_VERIFICATION_SECONDES: int = int(_optionnel("SOCKET_VERIFICATION_SECONDES", "30"))

    # Nombre de reverse proxys (Nginx…) devant l'API. 0 en développement. Quand il y en a un, mettre 1 :
    # sans cela, le limiteur de débit voit l'adresse du proxy pour tout le monde (voir utils/proxy.py).
    PROXIES_DE_CONFIANCE: int = int(_optionnel("PROXIES_DE_CONFIANCE", "0"))

    # Adresse d'écoute du serveur de développement (python -m project_organizer).
    # 127.0.0.1 : la machine seule. 0.0.0.0 pour l'ouvrir au réseau local.
    # En production, c'est gunicorn qui écoute (voir le Dockerfile), pas ce serveur.
    HOTE: str = _optionnel("HOTE", "127.0.0.1")

    DEBUG: bool = _optionnel("FLASK_DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = _optionnel("LOG_LEVEL", "INFO").upper()
    PORT: int = int(_optionnel("PORT", "5000"))
