"""Supervision du temps réel (réservée à l'administrateur)."""

from datetime import datetime

from .base import ModeleApi


class MetriquesTempsReelDto(ModeleApi):
    """Compteurs en mémoire du processus : ils repartent de zéro au redémarrage."""

    demarre_le: datetime
    connexions_actives: int
    connexions_authentifiees: int
    ouvertures_derniere_minute: int
    messages_derniere_minute: int
    ouvertures_total: int
    fermetures_total: int
    messages_total: int
    abonnements_refuses: int
    connexions_refusees: int
    coupures_pour_debit: int
    coupures_pour_expiration: int
    coupures_pour_revocation: int
