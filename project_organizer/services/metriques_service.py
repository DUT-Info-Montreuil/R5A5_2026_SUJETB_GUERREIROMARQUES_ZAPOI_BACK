"""Supervision : un instantané des compteurs du temps réel."""

from ..utils.metriques import metriques


def temps_reel() -> dict:
    """Instantané des compteurs du temps réel (connexions, messages, coupures)."""
    return metriques.instantane()
