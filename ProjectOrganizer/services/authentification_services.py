"""
Service d'authentification. Le contrôleur ne fait qu'appeler ces fonctions ;
toute la logique (unicité, vérification, message d'erreur volontairement
ambigu) vit ici, pour rester testable indépendamment de Flask.
"""
from repository import utilisateur_repository
from repository.models import Utilisateur
from utils.errors import Conflict, Unauthorized
from utils.security import generer_jeton, hacher_mot_de_passe, verifier_mot_de_passe


def inscrire(pseudo: str, email: str, mot_de_passe: str) -> tuple[str, Utilisateur]:
    if utilisateur_repository.get_by_pseudo(pseudo) is not None:
        raise Conflict("Ce pseudo est déjà pris.")
    if utilisateur_repository.get_by_email(email) is not None:
        raise Conflict("Cet e-mail est déjà utilisé.")

    utilisateur = utilisateur_repository.create(
        pseudo=pseudo,
        email=email,
        mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
    )
    return generer_jeton(utilisateur), utilisateur


def connecter(email: str, mot_de_passe: str) -> tuple[str, Utilisateur]:
    utilisateur = utilisateur_repository.get_by_email(email)

    # §2 du contrat : même message que l'e-mail soit inconnu ou le mot de
    # passe faux, pour ne pas permettre d'énumérer les comptes existants.
    if utilisateur is None or not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hash):
        raise Unauthorized("E-mail ou mot de passe incorrect.")

    return generer_jeton(utilisateur), utilisateur
