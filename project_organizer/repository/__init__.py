"""
Repository — l'accès à la base.

Un fichier par table ou agrégat : `<ressource>_repository.py`. Chaque fonction
reçoit la session du service en premier paramètre et ne fait jamais de commit :
la transaction appartient au service.

ORM pour le CRUD simple, SQL explicite (sqlalchemy.text) dès qu'il y a trois
jointures ou une condition fine.

Modèle à recopier : sante_repository.py
"""
