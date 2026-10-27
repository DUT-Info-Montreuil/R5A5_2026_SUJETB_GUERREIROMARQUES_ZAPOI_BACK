"""
Émission des événements temps réel (contrat §7).

Les services appellent ces fonctions APRÈS la validation de leur transaction :
un événement émis puis annulé par un rollback annoncerait aux clients un état
qui n'a jamais existé.

Trois sortes de salons :
    tournoi:{id}       public, pour suivre un tournoi (B-19)
    equipe:{id}        l'espace d'échange d'une équipe (B-16), accès contrôlé
    utilisateur:{id}   les connexions d'un même utilisateur : sert à lui parler
                       à lui seul, et à retrouver ses sockets pour les expulser
"""

from ..extensions import socketio


def salon_tournoi(id_tournoi: int) -> str:
    """Nom du salon d'un tournoi (ouvert à tous)."""
    return f"tournoi:{id_tournoi}"


def salon_equipe(id_equipe: int) -> str:
    """Nom du salon d'une équipe (ses membres, et les administrateurs)."""
    return f"equipe:{id_equipe}"


def salon_utilisateur(id_utilisateur: int) -> str:
    """Nom du salon personnel d'un utilisateur : y sont placées toutes ses connexions."""
    return f"utilisateur:{id_utilisateur}"


def tournoi_maj(id_tournoi: int, tournoi: dict) -> None:
    """Annonce le tournoi à jour à ses abonnés."""
    socketio.emit("tournoi:maj", tournoi, to=salon_tournoi(id_tournoi))


def rencontre_maj(id_tournoi: int, rencontre: dict) -> None:
    """Annonce une rencontre à jour aux abonnés du tournoi."""
    socketio.emit("rencontre:maj", rencontre, to=salon_tournoi(id_tournoi))


def message_nouveau(id_equipe: int, message: dict) -> None:
    """Pousse un nouveau message aux membres abonnés à l'espace de l'équipe."""
    socketio.emit("message:nouveau", message, to=salon_equipe(id_equipe))


def acces_revoque(id_equipe: int, motif: str, ids_utilisateurs: list[int]) -> None:
    """B-17, B-18 : prévient chaque utilisateur, puis retire ses sockets du salon de l'équipe.

    Supprimer une ligne en base ne suffit pas : un socket déjà ouvert resterait
    dans le salon et continuerait de recevoir les messages. L'événement part
    d'abord (par le salon personnel, que l'utilisateur garde), l'expulsion suit.
    """
    for id_utilisateur in ids_utilisateurs:
        socketio.emit(
            "equipe:acces-revoque",
            {"idEquipe": id_equipe, "motif": motif},
            to=salon_utilisateur(id_utilisateur),
        )
        _retirer_du_salon(id_equipe, id_utilisateur)


def _retirer_du_salon(id_equipe: int, id_utilisateur: int) -> None:
    serveur = socketio.server
    for sid, _ in list(serveur.manager.get_participants("/", salon_utilisateur(id_utilisateur))):
        serveur.leave_room(sid, salon_equipe(id_equipe), namespace="/")
