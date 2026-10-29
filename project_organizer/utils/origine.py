"""
Contrôle de l'origine des écritures (contrat §2, v14).

`SameSite=Lax` empêche le cookie de partir avec un POST venu d'un AUTRE SITE. Mais
un « site », pour le navigateur, regroupe tous les ports d'une même machine et tous
les sous-domaines d'un même domaine : une page servie sur `localhost:8081`, ou sur un
sous-domaine voisin, est du même site que l'API, et son POST emporte le cookie.

Les routes à corps JSON sont déjà à l'abri (une requête JSON d'une autre origine
déclenche un pré-vol CORS, refusé). Celles sans corps ne le sont pas :
`POST /api/equipes/{id}/demandes`, `POST /api/auth/deconnexion`. D'où ce contrôle,
pour toute écriture : si le navigateur annonce une origine (en-tête `Origin`), elle
doit être l'API elle-même ou une origine de `CORS_ORIGINS`.

Sans en-tête `Origin` (curl, tests, autre serveur), la requête passe : ce n'est pas
un navigateur piégé, donc pas une attaque CSRF, et l'authentification s'applique
comme d'habitude.
"""

import logging

from flask import Flask, request

from .erreurs import Forbidden

logger = logging.getLogger(__name__)

_METHODES_D_ECRITURE = {"POST", "PUT", "PATCH", "DELETE"}


def installer(app: Flask, origines_autorisees: list[str]) -> None:
    """Refuse en 403 toute écriture qu'un navigateur envoie depuis une origine non autorisée."""
    autorisees = {origine.rstrip("/") for origine in origines_autorisees}

    @app.before_request
    def _verifier_l_origine() -> None:
        if request.method not in _METHODES_D_ECRITURE:
            return
        origine = request.headers.get("Origin")
        if origine is None:
            return
        # L'API elle-même (la page Swagger, par exemple) : une requête de même origine n'est pas une CSRF.
        if origine in autorisees or origine == request.host_url.rstrip("/"):
            return
        logger.warning(
            "Écriture refusée : origine non autorisée",
            extra={"contexte": {"origine": origine[:200], "methode": request.method, "chemin": request.path}},
        )
        raise Forbidden("Origine non autorisée.")
