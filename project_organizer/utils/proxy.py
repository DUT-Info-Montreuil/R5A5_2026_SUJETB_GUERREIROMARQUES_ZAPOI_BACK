"""
Adresse réelle du client derrière un reverse proxy.

Derrière Nginx, `request.remote_addr` est l'adresse du PROXY : tous les
utilisateurs auraient la même, et le limiteur de débit (5 connexions par minute
et par adresse) serait partagé par toute la plateforme. Le proxy transmet la
vraie adresse dans `X-Forwarded-For` ; `ProxyFix` la lit.

Un en-tête `X-Forwarded-For` n'est fiable que s'il vient de NOTRE proxy : un
client peut en envoyer un faux. D'où le réglage `PROXIES_DE_CONFIANCE`, le
nombre de proxys placés devant l'application, et zéro par défaut — l'en-tête
est alors ignoré, comme en développement local.
"""

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix


def installer(app: Flask, nombre_de_proxys: int) -> None:
    """Fait lire à Flask l'adresse réelle du client quand `nombre_de_proxys` reverse proxys sont devant l'API (0 : rien n'est changé).
    """
    if nombre_de_proxys <= 0:
        return
    app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
        app.wsgi_app, x_for=nombre_de_proxys, x_proto=nombre_de_proxys, x_host=nombre_de_proxys
    )
