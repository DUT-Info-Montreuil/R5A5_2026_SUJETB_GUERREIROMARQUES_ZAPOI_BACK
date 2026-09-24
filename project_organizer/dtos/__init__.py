"""
DTOs — la forme des données échangées avec le front.

Un fichier par ressource : `<ressource>_dto.py`. On y trouve :
    - la validation des données reçues (champs requis, formats) ;
    - la conversion des objets Python en dictionnaires JSON.

Le JSON est en camelCase (contrat d'API §1), le Python en snake_case : c'est
ici, et seulement ici, que se fait la traduction.

Modèle à recopier : sante_dto.py
"""
