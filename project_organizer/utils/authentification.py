"""
Authentification et contrôle d'accès (contrat §2, cours « Brancher l'authentification »).

Trois niveaux, chacun vérifie ce qu'il est seul à pouvoir vérifier :

    1. Toute route exige un jeton valide, sauf celles marquées @publique.
       Un oubli ferme la route au lieu de l'ouvrir.
    2. @administrateur_requis vérifie le rôle à l'entrée de la route.
    3. Le service vérifie le droit sur la ressource visée (capitaine de CETTE
       équipe, membre de CETTE équipe) : lui seul dispose des deux.

Le jeton voyage dans un cookie HttpOnly : le JavaScript de la page ne peut pas
le lire, donc un script injecté ne peut pas l'emporter.
"""

import logging
from collections.abc import Callable
from datetime import timedelta
from functools import wraps

from flask import Flask, Response, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    current_user,
    get_jwt,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from ..config import Config
from ..extensions import jwt
from ..models import Utilisateur
from ..services import auth_service
from .erreurs import Forbidden

logger = logging.getLogger(__name__)

NOM_COOKIE = "jeton"

# Routes créées par les bibliothèques, qu'on ne peut pas décorer : servies sans jeton.
_ENDPOINTS_PUBLICS = {"static"}
_PREFIXES_PUBLICS = ("openapi", "doc_page_")


def configurer(app: Flask, config: type[Config]) -> None:
    """Branche l'authentification sur l'application : réglages du jeton et du cookie, rappels d'erreur, exigence d'un jeton par défaut.
    """
    app.config.update(
        JWT_SECRET_KEY=config.SECRET_KEY,
        # Algorithme imposé : un jeton ne peut pas choisir le sien (« alg: none »).
        JWT_ALGORITHM="HS256",
        JWT_DECODE_ALGORITHMS=["HS256"],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=config.JWT_DUREE_MINUTES),
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_ACCESS_COOKIE_NAME=NOM_COOKIE,
        JWT_ACCESS_COOKIE_PATH="/",
        JWT_COOKIE_SECURE=config.COOKIE_SECURE,
        JWT_COOKIE_SAMESITE="Lax",
        # Cookie persistant (Max-Age) : la session survit à la fermeture du navigateur.
        JWT_SESSION_COOKIE=False,
        # Pas de jeton anti-CSRF : SameSite=Lax bloque les autres sites tant qu'aucune
        # route n'écrit en GET (cours, « CSRF »), et utils/origine.py refuse les écritures
        # venues d'une autre origine du même site (autre port, sous-domaine voisin).
        JWT_COOKIE_CSRF_PROTECT=False,
    )
    jwt.init_app(app)
    _brancher_rappels()

    @app.before_request
    def _exiger_un_jeton() -> None:
        vue = app.view_functions.get(request.endpoint or "")
        if vue is None or request.method == "OPTIONS" or _est_publique(request.endpoint, vue):
            return
        verify_jwt_in_request()


def publique(vue: Callable) -> Callable:
    """Ouvre la route sans jeton. À poser juste sous @bp.get / @bp.post."""
    vue.est_publique = True  # type: ignore[attr-defined]
    return vue


def administrateur_requis(vue: Callable) -> Callable:
    """Réserve une route aux administrateurs : 403 sinon. À placer sous @bp.get / @bp.post."""
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        if not utilisateur_courant().est_administrateur:
            raise Forbidden("Action réservée aux administrateurs.")
        return vue(*args, **kwargs)

    return enveloppe


def utilisateur_courant() -> Utilisateur:
    """L'utilisateur de la requête, relu en base par _charger_utilisateur."""
    return current_user


def identite_du_jeton() -> tuple[int, int] | None:
    """(identifiant, version) portés par le jeton de la requête, ou None s'il est absent, expiré ou falsifié.

    N'exige rien et ne répond jamais 401 : pour une route publique qui agit quand même si
    l'appelant est connu — la déconnexion doit marcher même avec un cookie périmé.
    """
    try:
        verify_jwt_in_request(optional=True)
        charge = get_jwt()
    except Exception:  # noqa: BLE001 — toute anomalie du jeton = appelant inconnu
        return None
    if not charge:
        return None
    return int(charge["sub"]), int(charge.get("ver", 0))


def ouvrir_session(reponse: Response, utilisateur: Utilisateur) -> Response:
    """Pose le cookie de session (jeton signé, HttpOnly) sur la réponse."""
    jeton = create_access_token(
        identity=str(utilisateur.id_utilisateur),
        additional_claims={"ver": utilisateur.version_jeton},
    )
    # max_age explicite : sans lui, flask-jwt-extended pose un cookie d'un an alors que le
    # jeton qu'il contient expire au bout de JWT_DUREE_MINUTES (contrat §2.1 : 12 h).
    set_access_cookies(reponse, jeton, max_age=Config.JWT_DUREE_MINUTES * 60)
    return reponse


def fermer_session(reponse: Response) -> Response:
    """Efface le cookie de session de la réponse."""
    unset_jwt_cookies(reponse)
    return reponse


def _est_publique(endpoint: str | None, vue: Callable) -> bool:
    return (
        getattr(vue, "est_publique", False)
        or endpoint in _ENDPOINTS_PUBLICS
        or (endpoint or "").startswith(_PREFIXES_PUBLICS)
    )


def _refus(detail: str) -> Response:
    """401 au format du contrat. Le cookie invalide est effacé au passage."""
    reponse = jsonify({"erreur": "Unauthorized", "detail": detail})
    reponse.status_code = 401
    return fermer_session(reponse)


def _brancher_rappels() -> None:
    @jwt.user_lookup_loader
    def _charger_utilisateur(_entete: dict, charge: dict) -> Utilisateur | None:
        # Relu en base à chaque requête : révocation (ver) et droits à jour (§2.2).
        utilisateur = auth_service.utilisateur_du_jeton(int(charge["sub"]), charge.get("ver", 0))
        if utilisateur is not None:
            g.id_utilisateur = utilisateur.id_utilisateur
        return utilisateur

    # Par défaut, la bibliothèque répond {"msg": …}, et même 422 pour un jeton
    # malformé : on ramène tout à 401 { erreur, detail }.
    @jwt.unauthorized_loader
    def _sans_jeton(_raison: str):
        return _refus("Authentification requise.")

    @jwt.invalid_token_loader
    def _jeton_invalide(_raison: str):
        return _refus("Session invalide. Reconnectez-vous.")

    @jwt.expired_token_loader
    def _jeton_expire(_entete: dict, _charge: dict):
        return _refus("Session expirée. Reconnectez-vous.")

    @jwt.user_lookup_error_loader
    def _jeton_revoque(_entete: dict, _charge: dict):
        return _refus("Session révoquée. Reconnectez-vous.")
