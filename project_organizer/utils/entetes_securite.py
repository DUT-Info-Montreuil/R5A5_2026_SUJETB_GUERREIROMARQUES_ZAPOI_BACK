"""
En-têtes de sécurité posés sur toutes les réponses (cours, « Les headers de réponse »).

Une API ne renvoie que du JSON et ne charge rien : la politique de contenu la
plus stricte lui convient. La page Swagger (/apidoc) charge ses scripts depuis
un CDN, elle garde donc la politique par défaut du navigateur.

`Strict-Transport-Security` n'est posé que si COOKIE_SECURE=true, c'est-à-dire quand
le site est servi en HTTPS : annoncé en HTTP, il serait ignoré par le navigateur
et ferait croire à une protection qui n'existe pas.
"""

from flask import Flask, Response, request

from ..config import Config

_PREFIXE_DOCUMENTATION = "/apidoc"
# Deux ans, sous-domaines compris (valeur donnée par le cours, « Les headers de réponse »).
_HSTS = "max-age=63072000; includeSubDomains"


def installer(app: Flask) -> None:
    """Pose les en-têtes de sécurité sur chaque réponse de l'application."""
    @app.after_request
    def _poser_entetes(reponse: Response) -> Response:
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        if Config.COOKIE_SECURE:
            reponse.headers["Strict-Transport-Security"] = _HSTS
        if not request.path.startswith(_PREFIXE_DOCUMENTATION):
            reponse.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return reponse
