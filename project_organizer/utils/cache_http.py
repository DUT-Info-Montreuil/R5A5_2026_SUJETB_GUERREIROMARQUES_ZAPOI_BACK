"""
Mise en cache HTTP des réponses de l'API (cours, « CORS & Caching »).

Deux politiques, choisies d'après ce que la réponse contient :

  - Lecture PUBLIQUE (liste des tournois, arbre, équipe…) : `Cache-Control: no-cache` + ETag.
    « no-cache » ne veut pas dire « ne pas stocker » mais « revalider avant de réutiliser » :
    le navigateur redemande, envoie `If-None-Match`, et reçoit un 304 sans corps si rien n'a
    changé. Une donnée qui bouge pendant un tournoi n'est donc jamais périmée, et on économise
    la bande passante quand elle ne bouge pas.
  - Tout le reste (réponses privées, écritures, erreurs, /health) : `Cache-Control: no-store`.
    Un proxy ou un navigateur partagé ne doit jamais garder le profil, les équipes ou les
    messages de quelqu'un, ni l'état de santé de la base.

On ne fixe volontairement aucun `max-age` : un tournoi change en direct, et le temps réel
prévient déjà les clients. Un délai de fraîcheur afficherait un arbre périmé.
"""

from flask import Flask, Response, request

_PREFIXE_API = "/api/"


def installer(app: Flask) -> None:
    """Branche la politique de cache sur toutes les réponses de l'API."""

    @app.after_request
    def _regler_la_mise_en_cache(reponse: Response) -> Response:
        if not request.path.startswith(_PREFIXE_API):
            # /health et la documentation : jamais mis en cache (un état de santé périmé ment).
            if request.path == "/health":
                reponse.headers["Cache-Control"] = "no-store"
            return reponse
        if _est_une_lecture_publique(app, reponse):
            reponse.add_etag()
            reponse.headers["Cache-Control"] = "no-cache"
            return reponse.make_conditional(request)
        reponse.headers["Cache-Control"] = "no-store"
        return reponse


def _est_une_lecture_publique(app: Flask, reponse: Response) -> bool:
    if request.method != "GET" or reponse.status_code != 200:
        return False
    vue = app.view_functions.get(request.endpoint or "")
    return bool(getattr(vue, "est_publique", False))
