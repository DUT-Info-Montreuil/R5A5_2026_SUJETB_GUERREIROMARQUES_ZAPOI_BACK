"""
DTOs pour l'authentification.

Le contrat impose du camelCase en JSON (§1) alors que la base et le code
Python restent en snake_case : cette conversion se fait ici, dans un seul
endroit, jamais dans le contrôleur ni dans le modèle.
"""
from repository.models import Utilisateur
from utils.errors import BadRequest


def valider_inscription(donnees: dict) -> tuple[str, str, str]:
    """Retourne (pseudo, email, motDePasse) ou lève 400 si un champ manque."""
    pseudo = donnees.get("pseudo")
    email = donnees.get("email")
    mot_de_passe = donnees.get("motDePasse")

    if not pseudo or not isinstance(pseudo, str):
        raise BadRequest("Le champ 'pseudo' est requis.")
    if not email or not isinstance(email, str):
        raise BadRequest("Le champ 'email' est requis.")
    if not mot_de_passe or not isinstance(mot_de_passe, str):
        raise BadRequest("Le champ 'motDePasse' est requis.")
    if len(mot_de_passe) < 8:
        raise BadRequest("Le mot de passe doit contenir au moins 8 caractères.")

    return pseudo.strip(), email.strip().lower(), mot_de_passe


def valider_connexion(donnees: dict) -> tuple[str, str]:
    email = donnees.get("email")
    mot_de_passe = donnees.get("motDePasse")

    if not email or not isinstance(email, str):
        raise BadRequest("Le champ 'email' est requis.")
    if not mot_de_passe or not isinstance(mot_de_passe, str):
        raise BadRequest("Le champ 'motDePasse' est requis.")

    return email.strip().lower(), mot_de_passe


def utilisateur_vers_dto(utilisateur: Utilisateur) -> dict:
    return {
        "idUtilisateur": utilisateur.id_utilisateur,
        "pseudo": utilisateur.pseudo,
        "email": utilisateur.email,
        "estAdministrateur": utilisateur.est_administrateur,
    }


def reponse_authentification(jeton: str, utilisateur: Utilisateur) -> dict:
    return {"jeton": jeton, "utilisateur": utilisateur_vers_dto(utilisateur)}