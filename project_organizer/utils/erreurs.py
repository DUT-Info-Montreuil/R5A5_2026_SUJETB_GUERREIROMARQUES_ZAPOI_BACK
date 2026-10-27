"""
Erreurs métier, traduites en réponses au format du contrat (§1.1, §1.2).

Un service lève une de ces exceptions sans rien savoir de HTTP ; les
gestionnaires enregistrés dans app.py la convertissent en `{ erreur, detail }`
avec le bon code. Conception reprise de la branche feature-authentification.

Choix du code — contrat §1.2 et §1.3 :
    400 BadRequest            charge invalide, champ non modifiable
    401 Unauthorized          jeton absent, expiré, invalide ou révoqué
    403 Forbidden             ressource publique, action interdite
    404 NotFound              ressource inexistante ou invisible pour l'appelant
    409 Conflict              conflit avec l'ÉTAT (inscriptions closes, pseudo pris)
    422 UnprocessableEntity   violation d'une RÈGLE MÉTIER (poste occupé, B-07)
"""

import json
import logging

from flask import Flask, Request, Response, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Erreur métier : porte le code HTTP et le libellé du format d'erreur du contrat (§1.1)."""
    code = 500
    erreur = "Internal Server Error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(ApiError):
    """400 : requête invalide."""
    code = 400
    erreur = "Bad Request"


class Unauthorized(ApiError):
    """401 : pas de session valable."""
    code = 401
    erreur = "Unauthorized"


class Forbidden(ApiError):
    """403 : la ressource est publique mais l'action est interdite."""
    code = 403
    erreur = "Forbidden"


class NotFound(ApiError):
    """404 : ressource inexistante, ou invisible pour l'appelant."""
    code = 404
    erreur = "Not Found"


class Conflict(ApiError):
    """409 : conflit avec l'état de la ressource (transition impossible, doublon)."""
    code = 409
    erreur = "Conflict"


class UnprocessableEntity(ApiError):
    """422 : requête bien formée mais contraire à une règle métier."""
    code = 422
    erreur = "Unprocessable Entity"


def enregistrer_gestionnaires(app: Flask) -> None:
    """Toutes les erreurs sortent au format du contrat { erreur, detail }.

    - Erreur métier levée par un service → sa réponse, avec son code.
    - Erreur HTTP de Flask (404 route inconnue, 405 méthode…) → même format.
    - Toute autre exception → 500. La trace complète va dans les logs ; le
      client ne reçoit jamais le détail, qui exposerait l'intérieur du code.
    """

    @app.errorhandler(ApiError)
    def _erreur_metier(erreur: ApiError):
        return jsonify({"erreur": erreur.erreur, "detail": erreur.detail}), erreur.code

    @app.errorhandler(HTTPException)
    def _erreur_http(erreur: HTTPException):
        return jsonify({"erreur": erreur.name, "detail": erreur.description}), erreur.code

    @app.errorhandler(Exception)
    def _erreur_inattendue(_erreur: Exception):
        logger.exception("Erreur non gérée")
        return jsonify({"erreur": "Internal Server Error", "detail": "Erreur interne."}), 500



# --- Crochets de flask-pydantic-spec -----------------------------------------
# La bibliothèque produit ses propres réponses d'erreur ; ces deux crochets les
# réécrivent au format du contrat, pour que le front n'ait qu'une forme à lire.

def avant_validation(_requete: Request, reponse: Response | None, erreur: ValidationError | None, _vue) -> None:
    """Corps de requête invalide → 400 { erreur, detail: { champs: [...] } }."""
    if erreur is None or reponse is None:
        return
    champs = [
        {"champ": ".".join(str(morceau) for morceau in probleme["loc"]), "message": probleme["msg"]}
        for probleme in erreur.errors()
    ]
    reponse.set_data(json.dumps({"erreur": "Bad Request", "detail": {"champs": champs}}, ensure_ascii=False))


def apres_validation(_requete: Request, reponse: Response, erreur: ValidationError | None, _vue) -> None:
    """Réponse non conforme à son DTO → 500 au format du contrat.

    C'est un bug de notre code, pas du client : la documentation annoncerait
    une forme que la route ne renvoie pas.
    """
    if erreur is None:
        return
    logger.error("Réponse non conforme à son DTO", extra={"contexte": {"erreur": str(erreur)}})
    reponse.set_data(json.dumps({"erreur": "Internal Server Error", "detail": "Erreur interne."}))
