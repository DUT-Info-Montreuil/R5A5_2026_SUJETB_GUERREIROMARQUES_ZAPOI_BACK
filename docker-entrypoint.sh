#!/bin/sh
# Prépare l'environnement du conteneur, puis lance la commande demandée.
set -e

# La clé qui signe les jetons de session ne doit JAMAIS être écrite dans le dépôt.
# Si on n'en fournit pas (FLASK_SECRET_KEY), on en tire une au hasard au démarrage :
# elle vit le temps du conteneur, et les sessions ouvertes ne survivent donc pas à un
# redémarrage. Pour les garder, définir FLASK_SECRET_KEY (voir le README).
if [ -z "$FLASK_SECRET_KEY" ]; then
    FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    export FLASK_SECRET_KEY
    echo "FLASK_SECRET_KEY absente : clé temporaire générée pour ce démarrage."
fi

exec "$@"
