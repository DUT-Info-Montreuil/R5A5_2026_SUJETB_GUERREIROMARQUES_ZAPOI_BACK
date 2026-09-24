"""
Journalisation de chaque requête HTTP (docs/ARCHITECTURE.md §10).

Pour chaque requête : une ligne avec méthode, chemin, statut, durée,
utilisateur, et un identifiant de requête. L'identifiant est aussi renvoyé
dans l'en-tête `X-Request-Id` : quand le front affiche une erreur, on retrouve
la ligne de log correspondante.

Les réponses 401 et 403 sont journalisées en WARNING : ce sont les événements
de sécurité, ceux que visent les tests de droits d'accès.

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
            "chemin": request.path,
            "statut": reponse.status_code,
            "dureeMs": duree_ms,
            # Renseigné par la couche d'authentification quand elle existera.
            "idUtilisateur": g.get("id_utilisateur"),
        }

        if reponse.status_code in _CODES_SECURITE:
            logger.warning("Accès refusé", extra={"contexte": contexte})
        elif reponse.status_code >= 500:
            logger.error("Requête en échec", extra={"contexte": contexte})
        else:
            logger.info("Requête traitée", extra={"contexte": contexte})

        reponse.headers["X-Request-Id"] = g.get("id_requete", "")
        return reponse
