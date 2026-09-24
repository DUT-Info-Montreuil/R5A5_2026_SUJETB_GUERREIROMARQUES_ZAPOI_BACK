"""
Contrôleurs — la porte d'entrée HTTP.

Un fichier par ressource : `<ressource>_controller.py`, qui déclare un
Blueprint Flask. Penser à l'enregistrer dans app.py (app.register_blueprint).

Un contrôleur lit la requête, appelle UN service, et renvoie la réponse mise en
forme par un DTO. Il ne contient ni règle métier ni SQL.

Modèle à recopier : sante_controller.py
"""
