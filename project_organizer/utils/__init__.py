"""
Utilitaires transverses, utilisables par toutes les couches.

    authentification.py  jeton en cookie, @publique, @administrateur_requis
    cache_http.py        no-cache + ETag sur les GET publics, no-store ailleurs
    database.py          sessions transactionnelles sur le moteur SQLAlchemy
    entetes_securite.py  en-têtes de sécurité sur toutes les réponses
    erreurs.py           erreurs métier traduites au format du contrat
    journalisation.py    configuration des logs (sortie standard, JSON ou texte)
    metriques.py         compteurs du temps réel, en mémoire
    mots_de_passe.py     hachage argon2
    origine.py           refus des écritures venues d'une origine non autorisée
    proxy.py             adresse réelle du client derrière un reverse proxy
    requetes.py          une ligne de log par requête HTTP
"""
