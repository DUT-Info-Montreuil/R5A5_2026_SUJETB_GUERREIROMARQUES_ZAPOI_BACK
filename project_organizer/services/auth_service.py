"""
Inscription et connexion.

Le service ne connaît ni HTTP ni les cookies : il vérifie les identifiants et
renvoie l'utilisateur. L'émission du jeton appartient au contrôleur.
"""

from project_organizer.models import Utilisateur
from project_organizer.repository import utilisateur_repository
from project_organizer.utils import database, mots_de_passe
from project_organizer.utils.erreurs import Conflict, Unauthorized

# Même message dans les deux cas d'échec : deux messages distincts diraient
# quelles adresses sont inscrites (contrat §2, cours « Login et mot de passe »).
MESSAGE_IDENTIFIANTS_INVALIDES = "E-mail ou mot de passe incorrect."


def normaliser_email(email: str) -> str:
    return email.strip().lower()


def inscrire(pseudo: str, email: str, mot_de_passe: str) -> Utilisateur:
    email = normaliser_email(email)
    with database.session() as session:
        if utilisateur_repository.pseudo_existe(session, pseudo):
            raise Conflict("Ce pseudo est déjà utilisé.")
        if utilisateur_repository.par_email(session, email) is not None:
            raise Conflict("Cette adresse e-mail est déjà utilisée.")
        return utilisateur_repository.ajouter(session, pseudo, email, mots_de_passe.hacher(mot_de_passe))


def authentifier(email: str, mot_de_passe: str) -> Utilisateur:
    with database.session() as session:
        utilisateur = utilisateur_repository.par_email(session, normaliser_email(email))

    empreinte = utilisateur.mot_de_passe_hash if utilisateur else None
    # Calculé avant le test : la vérification a lieu même pour un compte inconnu.
    mot_de_passe_valide = mots_de_passe.verifier(mot_de_passe, empreinte)
    if utilisateur is None or not mot_de_passe_valide:
        raise Unauthorized(MESSAGE_IDENTIFIANTS_INVALIDES)
    return utilisateur


def utilisateur_du_jeton(id_utilisateur: int, version_jeton: int) -> Utilisateur | None:
    """L'utilisateur du jeton, ou None si le compte n'existe plus ou si le
    jeton a été révoqué (version_jeton incrémentée depuis son émission)."""
    with database.session() as session:
        utilisateur = utilisateur_repository.par_id(session, id_utilisateur)
    if utilisateur is None or utilisateur.version_jeton != version_jeton:
        return None
    return utilisateur
