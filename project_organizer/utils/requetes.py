"""
Journalisation de chaque requête HTTP (docs/ARCHITECTURE.md §10).

Pour chaque requête : une ligne avec méthode, chemin, statut, durée,
utilisateur, et un identifiant de requête. L'identifiant est aussi renvoyé
dans l'en-tête `X-Request-Id` : quand le front affiche une erreur, on retrouve
la ligne de log correspondante.

Le niveau suit le statut : 5xx en ERROR (le serveur est en défaut), 4xx en
WARNING (la requête est refusée), le reste en INFO. Les 401 et 403 gardent leur
message « Accès refusé » : ce sont les événements de sécurité, ceux que visent
les tests de droits d'accès.

`route` est le motif de la route (`/api/equipes/<int:id_equipe>`), `chemin` le
chemin réellement demandé : le motif permet de regrouper les requêtes d'une même
route, quels que soient les identifiants.

Ce qui n'est JAMAIS journalisé : le corps de la requête (il peut contenir un
mot de passe), l'en-tête Authorization (il contient le jeton), l'adresse
e-mail. On journalise l'identifiant de l'utilisateur, pas son identité.
"""

import logging
import time
import uuid

from flask import Flask, Response, g, request

logger = logging.getLogger("requetes")

_CODES_SECURITE = {401, 403}


def installer(app: Flask) -> None:
    """Branche la journalisation des requêtes sur l'application."""

    @app.before_request
    def _debut() -> None:
        g.id_requete = uuid.uuid4().hex[:12]
        g.debut_requete = time.perf_counter()

    @app.after_request
    def _fin(reponse: Response) -> Response:
        duree_ms = round((time.perf_counter() - g.get("debut_requete", time.perf_counter())) * 1000, 1)
        contexte = {
            "idRequete": g.get("id_requete"),
            "methode": request.method,
            "route": request.url_rule.rule if request.url_rule else None,
            "chemin": request.path,
            "statut": reponse.status_code,
            "dureeMs": duree_ms,
            # Taille du corps de la réponse ; absente pour une réponse en flux.
            "tailleOctets": reponse.content_length,
            # Posé par la couche d'authentification (utils/authentification.py).
            "idUtilisateur": g.get("id_utilisateur"),
        }

        if reponse.status_code in _CODES_SECURITE:
            logger.warning("Accès refusé", extra={"contexte": contexte})
        elif reponse.status_code >= 500:
            logger.error("Requête en échec", extra={"contexte": contexte})
        elif reponse.status_code >= 400:
            logger.warning("Requête refusée", extra={"contexte": contexte})
        else:
            logger.info("Requête traitée", extra={"contexte": contexte})

        reponse.headers["X-Request-Id"] = g.get("id_requete", "")
        return reponse
