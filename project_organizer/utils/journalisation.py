"""
Journalisation applicative.

Deux décisions à documenter dans la fiche « format et destination de la
journalisation » :

DESTINATION — la sortie standard, pas un fichier.
    Un fichier de log doit être créé, tourné, purgé, et disparaît avec le
    conteneur. La sortie standard est lue par Docker (`docker compose logs`),
    par l'IDE, et par n'importe quelle plateforme d'hébergement. Une seule
    destination, aucune gestion de rotation à écrire.

FORMAT — JSON en une ligne par événement.
    Un message en texte libre se lit bien à l'œil mais ne se filtre pas. En
    JSON, on peut chercher toutes les tentatives d'accès refusées d'un
    utilisateur donné. Comme les tests notés portent sur les droits d'accès,
    pouvoir relire ce qui a été refusé et à qui a une vraie valeur.

Le coût : les logs sont moins agréables à lire directement dans le terminal.
D'où LOG_FORMAT=texte, qui permet de repasser en lecture humaine en
développement sans toucher au code.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class FormateurJson(logging.Formatter):
    """Sérialise chaque enregistrement en une ligne JSON."""

    def format(self, record: logging.LogRecord) -> str:
        charge = {
            "horodatage": datetime.now(timezone.utc).isoformat(),
            "niveau": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Contexte métier passé via logger.info("...", extra={"contexte": {...}})
        contexte = getattr(record, "contexte", None)
        if contexte:
            charge["contexte"] = contexte

        if record.exc_info:
            charge["exception"] = self.formatException(record.exc_info)

        return json.dumps(charge, ensure_ascii=False)


def configurer(niveau: str = "INFO") -> None:
    """Installe la journalisation sur la sortie standard."""
    handler = logging.StreamHandler(sys.stdout)

    if os.getenv("LOG_FORMAT", "json").lower() == "texte":
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s %(name)s  %(message)s")
        )
    else:
        handler.setFormatter(FormateurJson())

    racine = logging.getLogger()
    racine.handlers.clear()
    racine.addHandler(handler)
    racine.setLevel(niveau)

    # Werkzeug journalise déjà chaque requête HTTP : on le laisse faire mais on
    # le calme pour ne pas noyer les messages applicatifs.
    logging.getLogger("werkzeug").setLevel("WARNING")
