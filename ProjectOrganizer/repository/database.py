"""
Instance SQLAlchemy unique, importée par app.py (pour db.init_app) et par
repository/models.py (pour déclarer les modèles).
La séparer dans son propre fichier évite l'import circulaire classique
app.py <-> models.py.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
