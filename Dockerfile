# =============================================================================
#  API Agôn Cup — image de production.
#
#  gunicorn remplace le serveur de développement de Flask : un seul processus
#  (l'identité des connexions temps réel, les métriques et le limiteur de débit
#  vivent en mémoire) et beaucoup de threads (en mode `threading`, chaque
#  connexion ouverte en occupe un). Voir docs/ARCHITECTURE.md.
#
#  Lancement de toute la pile : docker compose -f docker-compose.complet.yml up --build
# =============================================================================

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Les dépendances d'abord : cette couche ne se reconstruit que si requirements.txt change.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY project_organizer ./project_organizer
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Un utilisateur sans droits : un défaut de l'application ne donne pas la main sur le conteneur.
RUN useradd --system --uid 10001 --no-create-home agon \
    && chmod +x /usr/local/bin/docker-entrypoint.sh
USER agon

EXPOSE 5000

# /health répond 503 quand la base est injoignable : le conteneur est alors « unhealthy ».
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"]

ENTRYPOINT ["docker-entrypoint.sh"]
# Pas de journal d'accès gunicorn : l'application journalise elle-même chaque requête (JSON).
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "100", \
     "--bind", "0.0.0.0:5000", "project_organizer.wsgi:application"]
