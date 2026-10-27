"""Routes d'authentification (contrat §2)."""

import logging

from flask import Blueprint, Response as ReponseFlask, g, jsonify, request
from flask_pydantic_spec import Response

from ..config import Config
from ..dtos.auth_dto import (
    ConnexionDto,
    InscriptionDto,
    ReponseAuthentificationDto,
    UtilisateurDto,
    utilisateur_vers_dto,
)
from ..dtos.base import ErreurDto
from ..extensions import limiter, spec
from ..services import auth_service
from ..utils.authentification import (
    fermer_session,
    identite_du_jeton,
    ouvrir_session,
    publique,
    utilisateur_courant,
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _reponse_session(utilisateur, statut: int):
    g.id_utilisateur = utilisateur.id_utilisateur
    corps = ReponseAuthentificationDto(utilisateur=utilisateur_vers_dto(utilisateur))
    reponse = jsonify(corps.vers_json())
    reponse.status_code = statut
    return ouvrir_session(reponse, utilisateur)


@auth_bp.post("/inscription")
@publique
@limiter.limit(Config.LIMITE_CONNEXION)
@spec.validate(
    body=InscriptionDto,
    resp=Response(HTTP_201=ReponseAuthentificationDto, HTTP_409=ErreurDto, HTTP_429=ErreurDto),
    tags=["Authentification"],
)
def inscription():
    """Créer un compte et ouvrir la session.

    Le jeton est posé dans un cookie HttpOnly `jeton` ; il n'apparaît pas dans
    le corps. Mot de passe : 12 caractères minimum.
    """
    donnees: InscriptionDto = request.context.body
    utilisateur = auth_service.inscrire(donnees.pseudo, donnees.email, donnees.mot_de_passe)
    return _reponse_session(utilisateur, 201)


@auth_bp.post("/connexion")
@publique
@limiter.limit(Config.LIMITE_CONNEXION)
@spec.validate(
    body=ConnexionDto,
    resp=Response(HTTP_200=ReponseAuthentificationDto, HTTP_401=ErreurDto, HTTP_429=ErreurDto),
    tags=["Authentification"],
)
def connexion():
    """Ouvrir une session.

    401 avec le même message que l'e-mail soit inconnu ou le mot de passe
    faux. 429 au-delà de 5 tentatives par minute depuis la même adresse.
    """
    donnees: ConnexionDto = request.context.body
    utilisateur = auth_service.authentifier(donnees.email, donnees.mot_de_passe)
    return _reponse_session(utilisateur, 200)


@auth_bp.get("/moi")
@spec.validate(resp=Response(HTTP_200=UtilisateurDto, HTTP_401=ErreurDto), tags=["Authentification"])
def moi():
    """L'utilisateur de la session en cours.

    Sert au front à restaurer la session au chargement de la page.
    """
    return jsonify(utilisateur_vers_dto(utilisateur_courant()).vers_json()), 200


@auth_bp.post("/deconnexion")
@publique
@spec.validate(resp=Response(HTTP_204=None), tags=["Authentification"])
def deconnexion():
    """Fermer la session : efface le cookie **et révoque les jetons du compte**.

    Effacer le cookie ne suffit pas : un jeton volé resterait valable jusqu'à son expiration
    (12 h). La déconnexion incrémente donc `version_jeton` : le jeton est refusé tout de suite,
    sur tous les appareils du compte, et ses connexions temps réel sont coupées sous 30 s.

    Publique pour qu'une session déjà expirée puisse quand même être fermée : sans jeton
    valable, il n'y a rien à révoquer et la réponse reste 204.
    """
    identite = identite_du_jeton()
    if identite is not None:
        if auth_service.revoquer_les_sessions(*identite):
            logger.info("Sessions révoquées à la déconnexion", extra={"contexte": {"idUtilisateur": identite[0]}})
    return fermer_session(ReponseFlask(status=204))
