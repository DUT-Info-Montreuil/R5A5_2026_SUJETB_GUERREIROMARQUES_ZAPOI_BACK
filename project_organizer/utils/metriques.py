"""
Métriques du temps réel (cours, « Superviser les connexions »).

Le cours distingue trois choses à surveiller :

    les connexions   ouvertures, fermetures et leurs motifs → les logs
    les métriques    connexions actives, débit de messages, fréquence des
                     ouvertures → ce module
    les anomalies    échecs d'authentification, connexions refusées, coupures
                     → des logs WARNING, et les compteurs de ce module

Une hausse inhabituelle des ouvertures sur la dernière minute révèle un
problème de réseau, un délai d'inactivité mal réglé ou des redémarrages
fréquents : c'est la « fréquence des reconnexions » du cours. Le serveur ne
peut pas distinguer une reconnexion d'une première connexion, il compte donc
toutes les ouvertures.

Tout est en mémoire et propre à un processus, comme le limiteur de débit : un
déploiement sur plusieurs instances demanderait un stockage partagé.
"""

import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime, timezone

FENETRE_SECONDES = 60


class MetriquesTempsReel:
    """Compteurs du temps réel, en mémoire, protégés par un verrou."""
    def __init__(self, horloge: Callable[[], float] = time.monotonic):
        self._horloge = horloge
        self._verrou = threading.Lock()
        self.remettre_a_zero()

    def remettre_a_zero(self) -> None:
        """Remet tous les compteurs à zéro (démarrage, tests)."""
        with self._verrou:
            self._demarre_le = datetime.now(timezone.utc)
            self._actives = 0
            self._authentifiees = 0
            self._compteurs: Counter[str] = Counter()
            self._ouvertures: deque[float] = deque()
            self._messages: deque[float] = deque()

    # --- Ce que le code signale ------------------------------------------------

    def ouverture(self, authentifiee: bool) -> None:
        """Une connexion s'ouvre ; `authentifiee` si elle porte un jeton valable."""
        with self._verrou:
            self._actives += 1
            self._authentifiees += int(authentifiee)
            self._compteurs["ouvertures"] += 1
            self._ouvertures.append(self._horloge())

    def fermeture(self, authentifiee: bool) -> None:
        """Une connexion se ferme."""
        with self._verrou:
            self._actives = max(0, self._actives - 1)
            self._authentifiees = max(0, self._authentifiees - int(authentifiee))
            self._compteurs["fermetures"] += 1

    def message_envoye(self) -> None:
        """Un message d'équipe vient d'être posté."""
        with self._verrou:
            self._compteurs["messages"] += 1
            self._messages.append(self._horloge())

    def abonnement_refuse(self) -> None:
        """Un abonnement à un salon vient d'être refusé."""
        with self._verrou:
            self._compteurs["abonnementsRefuses"] += 1

    def connexion_refusee(self) -> None:
        """Une connexion refusée à l'ouverture : son adresse a déjà trop de connexions ouvertes."""
        with self._verrou:
            self._compteurs["connexionsRefusees"] += 1

    def coupure(self, motif: str) -> None:
        """Une connexion coupée par le serveur : « debit » (trop d'événements), « expiration » (jeton expiré)
        ou « revocation » (jeton révoqué par une déconnexion)."""
        with self._verrou:
            self._compteurs[f"coupures_{motif}"] += 1

    # --- Ce qu'on en lit ------------------------------------------------------------

    def _derniere_minute(self, instants: deque[float]) -> int:
        limite = self._horloge() - FENETRE_SECONDES
        while instants and instants[0] < limite:
            instants.popleft()
        return len(instants)

    def instantane(self) -> dict:
        """Photo des compteurs, au format de la route de supervision."""
        with self._verrou:
            return {
                "demarreLe": self._demarre_le,
                "connexionsActives": self._actives,
                "connexionsAuthentifiees": self._authentifiees,
                "ouverturesDerniereMinute": self._derniere_minute(self._ouvertures),
                "messagesDerniereMinute": self._derniere_minute(self._messages),
                "ouverturesTotal": self._compteurs["ouvertures"],
                "fermeturesTotal": self._compteurs["fermetures"],
                "messagesTotal": self._compteurs["messages"],
                "abonnementsRefuses": self._compteurs["abonnementsRefuses"],
                "connexionsRefusees": self._compteurs["connexionsRefusees"],
                "coupuresPourDebit": self._compteurs["coupures_debit"],
                "coupuresPourExpiration": self._compteurs["coupures_expiration"],
                "coupuresPourRevocation": self._compteurs["coupures_revocation"],
            }


# Une seule instance par processus.
metriques = MetriquesTempsReel()
