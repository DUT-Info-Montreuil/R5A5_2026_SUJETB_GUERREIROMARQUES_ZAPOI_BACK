"""
Instances partagées par toute l'application.

Elles sont créées ici, sans application, puis attachées à l'application dans
`create_app()`. Les contrôleurs et les gestionnaires de sockets les importent
depuis ce module — c'est ce qui évite les imports circulaires avec app.py.
"""

from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_pydantic_spec import FlaskPydanticSpec
from flask_socketio import SocketIO

from .utils.erreurs import apres_validation, avant_validation

# async_mode="threading" : fonctionne avec le serveur de développement de Flask
# et simple-websocket, sans eventlet ni gevent à installer.
socketio = SocketIO(async_mode="threading")

# Documentation OpenAPI générée depuis les DTOs, servie sur /apidoc/swagger.
# 400 et non 422 (valeur par défaut de la bibliothèque) : notre contrat réserve
# 422 aux règles métier (§1.2).
spec = FlaskPydanticSpec(
    "flask",
    title="API Agôn Cup",
    version="3",
    ui="swagger",
    validation_error_code=400,
    before=avant_validation,
    after=apres_validation,
)

# Jeton JWT : configuré dans utils/authentification.py.
jwt = JWTManager()

# Limitation de débit par adresse. Stockage en mémoire : suffisant pour un seul
# processus ; plusieurs instances demanderaient un stockage partagé (Redis).
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
