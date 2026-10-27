"""
Point d'entrée de production : gunicorn y cherche l'objet `application`.

    gunicorn --worker-class gthread --workers 1 --threads 100 project_organizer.wsgi:application

Un seul processus (--workers 1) : l'identité des connexions temps réel, les
métriques et le limiteur de débit vivent en mémoire (voir docs/ARCHITECTURE.md).
Plusieurs threads (--threads) : en mode `threading`, chaque connexion ouverte en
occupe un. Le serveur de développement (python -m project_organizer) n'est pas
fait pour la production.
"""

from .app import create_app

application = create_app()
