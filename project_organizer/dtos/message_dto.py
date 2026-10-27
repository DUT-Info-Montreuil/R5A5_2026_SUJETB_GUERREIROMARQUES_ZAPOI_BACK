"""Espace d'échange d'une équipe (contrat §6, B-16)."""

from datetime import datetime

from pydantic import Field, RootModel, field_validator

from ..models import Message
from .base import ModeleApi, ModeleEntree

LONGUEUR_MAX_MESSAGE = 2000


class EnvoiMessageDto(ModeleEntree):
    """Corps de POST /api/equipes/{id}/messages. Du texte brut : le front l'affiche tel quel, sans HTML."""

    contenu: str = Field(max_length=LONGUEUR_MAX_MESSAGE, examples=["On se retrouve à 20 h ?"])

    @field_validator("contenu")
    @classmethod
    def _non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if not valeur:
            raise ValueError("Le message ne peut pas être vide.")
        return valeur


class MessageDto(ModeleApi):
    """Un message. Réponse de POST, élément de GET et charge de l'événement message:nouveau.

    idAuteur et pseudo sont absents quand le compte de l'auteur a été supprimé.
    """

    id_message: int
    id_equipe: int
    id_auteur: int | None = None
    pseudo: str | None = None
    contenu: str
    envoye_le: datetime


class ListeMessagesDto(RootModel[list[MessageDto]]):
    """Les messages d'une équipe, du plus ancien au plus récent."""
    pass


def message_vers_dto(message: Message, pseudo: str | None) -> MessageDto:
    """Convertit un message en réponse d'API ; le pseudo manque si le compte de l'auteur a été supprimé."""
    return MessageDto(
        id_message=message.id_message,
        id_equipe=message.id_equipe,
        id_auteur=message.id_auteur,
        pseudo=pseudo,
        contenu=message.contenu,
        envoye_le=message.envoye_le,
    )
