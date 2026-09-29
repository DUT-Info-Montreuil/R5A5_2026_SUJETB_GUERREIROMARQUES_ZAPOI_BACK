"""
Émission des événements temps réel (contrat §7).

Les services appellent ces fonctions APRÈS la validation de leur transaction :
un événement émis puis annulé par un rollback annoncerait aux clients un état
qui n'a jamais existé.
"""

from ..extensions import socketio


def salon_tournoi(id_tournoi: int) -> str:
    return f"tournoi:{id_tournoi}"


def tournoi_maj(id_tournoi: int, tournoi: dict) -> None:
    socketio.emit("tournoi:maj", tournoi, to=salon_tournoi(id_tournoi))


def rencontre_maj(id_tournoi: int, rencontre: dict) -> None:
    socketio.emit("rencontre:maj", rencontre, to=salon_tournoi(id_tournoi))
