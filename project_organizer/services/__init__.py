"""
Services — les règles du sujet.

Un fichier par domaine : `<ressource>_service.py`. C'est ici que vivent les
droits d'accès, les transitions d'état du tournoi, la propagation dans l'arbre.

Un service ouvre la transaction (`with database.session() as session:`) et la
passe au repository. Il lève les erreurs de `utils/erreurs.py` et ne connaît
ni Flask ni HTTP.

Modèle à recopier : sante_service.py
"""
