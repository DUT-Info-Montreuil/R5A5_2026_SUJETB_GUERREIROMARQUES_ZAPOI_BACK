"""
Instances partagées par toute l'application.

Elles sont créées ici, sans application, puis attachées à l'application dans
`create_app()`. Les contrôleurs et les gestionnaires de sockets les importent
depuis ce module — c'est ce qui évite les imports circulaires avec app.py.

L'outil de documentation d'API (Flasgger, selon le cours) viendra s'ajouter ici.
"""

from flask_socketio import SocketIO

# async_mode="threading" : fonctionne avec le serveur de développement de Flask
# et simple-websocket, sans eventlet ni gevent à installer.
socketio = SocketIO(async_mode="threading")
