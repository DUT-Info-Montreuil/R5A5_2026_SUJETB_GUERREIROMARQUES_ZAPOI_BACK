"""
Contrôleur d'authentification.

    POST /api/auth/inscription   public
    POST /api/auth/connexion     public
    GET  /api/auth/moi           authentifié

Le contrôleur reste volontairement fin : validation via les DTOs, logique
métier dans le service, sérialisation via les DTOs. Rien d'autre ici.
"""
from flask import Blueprint, g, jsonify, request

from dtos.authentification_dto import (
    reponse_authentification,
    utilisateur_vers_dto,
    valider_connexion,
    valider_inscription,
)
from services import authentification_services
from utils.security import auth_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/inscription")
def inscription():
    donnees = request.get_json(silent=True) or {}
    pseudo, email, mot_de_passe = valider_inscription(donnees)

    jeton, utilisateur = authentification_services.inscrire(pseudo, email, mot_de_passe)

    return jsonify(reponse_authentification(jeton, utilisateur)), 201


@auth_bp.post("/connexion")
def connexion():
    donnees = request.get_json(silent=True) or {}
    email, mot_de_passe = valider_connexion(donnees)

    jeton, utilisateur = authentification_services.connecter(email, mot_de_passe)

    return jsonify(reponse_authentification(jeton, utilisateur)), 200


@auth_bp.get("/moi")
@auth_required
def moi():
    return jsonify(utilisateur_vers_dto(g.utilisateur_courant)), 200
