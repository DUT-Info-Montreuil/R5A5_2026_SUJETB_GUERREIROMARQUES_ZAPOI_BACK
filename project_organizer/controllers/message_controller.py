"""Espace d'échange d'une équipe (contrat §6)."""

from flask import Blueprint, g, jsonify, request
from flask_limiter.util import get_remote_address
from flask_pydantic_spec import Response

from ..config import Config
from ..dtos.base import ErreurDto
from ..dtos.message_dto import EnvoiMessageDto, ListeMessagesDto, MessageDto, message_vers_dto
from ..extensions import limiter, spec
from ..services import espace_service
from ..utils.authentification import utilisateur_courant

message_bp = Blueprint("messages", __name__)


def _cle_de_debit() -> str:
    """Le plafond de messages est par utilisateur, pas par adresse : toute une
    salle de TP derrière la même adresse ne doit pas se bloquer mutuellement."""
    return f"utilisateur:{g.get('id_utilisateur') or get_remote_address()}"


@message_bp.get("/api/equipes/<int:id_equipe>/messages")
@spec.validate(
    resp=Response(HTTP_200=ListeMessagesDto, HTTP_401=ErreurDto, HTTP_404=ErreurDto),
    tags=["Espace d'échange"],
)
def lister_messages(id_equipe: int):
    """Les messages de l'équipe, du plus ancien au plus récent (B-16, B-18).

    Réservé aux membres d'une équipe encore en lice et aux administrateurs.
    404 pour tout autre appelant, que l'équipe existe ou non : l'espace
    d'échange n'existe pas pour qui n'y a pas accès. Pas de pagination.
    """
    messages = espace_service.lire(id_equipe, utilisateur_courant())
    return jsonify([message_vers_dto(m, pseudo).vers_json() for m, pseudo in messages]), 200


@message_bp.post("/api/equipes/<int:id_equipe>/messages")
@limiter.limit(Config.LIMITE_MESSAGES, key_func=_cle_de_debit)
@spec.validate(
    body=EnvoiMessageDto,
    resp=Response(
        HTTP_201=MessageDto, HTTP_400=ErreurDto, HTTP_401=ErreurDto, HTTP_403=ErreurDto,
        HTTP_404=ErreurDto, HTTP_429=ErreurDto,
    ),
    tags=["Espace d'échange"],
)
def envoyer_message(id_equipe: int):
    """Envoyer un message à son équipe (B-16). Membre d'une équipe en lice.

    Texte brut de 1 à 2000 caractères. 403 si l'appelant est administrateur
    (il lit, il n'écrit pas) ; 404 s'il n'est pas membre ou si l'espace est
    fermé ; 429 au-delà de 30 messages par minute. Le message est poussé aux
    membres abonnés par l'événement message:nouveau.
    """
    donnees: EnvoiMessageDto = request.context.body
    message, pseudo = espace_service.envoyer(id_equipe, utilisateur_courant(), donnees.contenu)
    return jsonify(message_vers_dto(message, pseudo).vers_json()), 201
