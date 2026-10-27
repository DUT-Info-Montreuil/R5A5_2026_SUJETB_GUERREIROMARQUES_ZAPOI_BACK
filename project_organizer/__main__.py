"""Lancement en développement : python -m project_organizer"""

from .app import create_app
from .config import Config
from .extensions import socketio

if __name__ == "__main__":
    application = create_app()
    # socketio.run et non app.run : le serveur doit gérer HTTP ET WebSocket.
    socketio.run(
        application,
        host=Config.HOTE,
        port=Config.PORT,
        debug=Config.DEBUG,
        allow_unsafe_werkzeug=True,  # serveur de développement uniquement
    )
