"""Lancement en développement : python -m project_organizer"""

from .app import create_app
from .config import Config
from .extensions import socketio

if __name__ == "__main__":
    application = create_app()
    # socketio.run et non app.run : le serveur doit gérer HTTP ET WebSocket.
    socketio.run(
        application,
        host="127.0.0.1",
        port=Config.PORT,
        debug=True,
        allow_unsafe_werkzeug=True,  # serveur de développement uniquement
    )
