"""
En-têtes de sécurité posés sur toutes les réponses (cours, « Les headers de réponse »).

Une API ne renvoie que du JSON et ne charge rien : la politique de contenu la
plus stricte lui convient. La page Swagger (/apidoc) charge ses scripts depuis
un CDN, elle garde donc la politique par défaut du navigateur.
"""

from flask import Flask, Response, request

_PREFIXE_DOCUMENTATION = "/apidoc"


def installer(app: Flask) -> None:
    @app.after_request
    def _poser_entetes(reponse: Response) -> Response:
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        if not request.path.startswith(_PREFIXE_DOCUMENTATION):
            reponse.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return reponse
