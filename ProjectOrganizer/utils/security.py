"""
Primitives de sécurité :
- hachage du mot de passe (werkzeug, déjà présent avec Flask, pas de
  dépendance supplémentaire) ;
- émission / décodage du JWT selon §2.2 du contrat (sub, ver, iat, exp,
  aucun droit encodé) ;
- décorateur @auth_required qui relit les droits en base à chaque requête
  (§2.2 : la signature garantit l'identité, pas les droits) et vérifie
  `ver` contre `utilisateur.version_jeton` (§2.3) ;
- décorateur @admin_required, pour les routes réservées à l'administrateur,
  réutilisable par les autres contrôleurs (tournois, rencontres, ...).
"""
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from repository import utilisateur_repository
from repository.models import Utilisateur
from utils.errors import Unauthorized, Forbidden

DUREE_JETON = timedelta(hours=12)  # §2.1 : un seul jeton, 12h, sans rafraîchissement


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return generate_password_hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    return check_password_hash(mot_de_passe_hash, mot_de_passe)


def generer_jeton(utilisateur: Utilisateur) -> str:
    maintenant = datetime.now(timezone.utc)
    charge = {
        "sub": str(utilisateur.id_utilisateur),
        "ver": utilisateur.version_jeton,
        "iat": maintenant,
        "exp": maintenant + DUREE_JETON,
    }
    return jwt.encode(charge, current_app.config["JWT_SECRET"], algorithm="HS256")


def _extraire_jeton() -> str:
    entete = request.headers.get("Authorization", "")
    if not entete.startswith("Bearer "):
        raise Unauthorized("Jeton manquant.")
    return entete.removeprefix("Bearer ").strip()


def _utilisateur_courant() -> Utilisateur:
    """
    Décode le jeton, relit l'utilisateur en base et vérifie `ver`.
    Toute anomalie (jeton absent, invalide, expiré, révoqué, compte
    supprimé) se traduit uniformément par un 401, comme l'exige §2.
    """
    jeton = _extraire_jeton()
    try:
        charge = jwt.decode(jeton, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Jeton expiré.")
    except jwt.InvalidTokenError:
        raise Unauthorized("Jeton invalide.")

    utilisateur = utilisateur_repository.get_by_id(int(charge["sub"]))
    if utilisateur is None:
        raise Unauthorized("Jeton invalide.")

    # §2.3 : un jeton dont la version ne correspond plus a été révoqué.
    if charge.get("ver") != utilisateur.version_jeton:
        raise Unauthorized("Jeton révoqué.")

    return utilisateur


def auth_required(vue: Callable) -> Callable:
    """Pose g.utilisateur_courant, relu en base à chaque requête (§2.2)."""

    @wraps(vue)
    def enveloppe(*args, **kwargs):
        g.utilisateur_courant = _utilisateur_courant()
        return vue(*args, **kwargs)

    return enveloppe


def admin_required(vue: Callable) -> Callable:
    """
    À réutiliser tel quel par les autres contrôleurs (POST /api/tournois,
    PATCH /api/rencontres/{id}, ...) : la règle "administrateur uniquement"
    ne doit être écrite qu'une fois.
    """

    @wraps(vue)
    def enveloppe(*args, **kwargs):
        g.utilisateur_courant = _utilisateur_courant()
        if not g.utilisateur_courant.est_administrateur:
            raise Forbidden("Action réservée à l'administrateur.")
        return vue(*args, **kwargs)

    return enveloppe
