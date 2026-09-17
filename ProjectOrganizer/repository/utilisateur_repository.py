"""
Couche repository pour Utilisateur.
Responsabilité unique : parler à la base. Aucune règle métier ici (pas de
hachage de mot de passe, pas de génération de jeton) — ça vit dans le service.
"""
from typing import Optional

from repository.database import db
from repository.models import Utilisateur


def get_by_id(id_utilisateur: int) -> Optional[Utilisateur]:
    return db.session.get(Utilisateur, id_utilisateur)


def get_by_email(email: str) -> Optional[Utilisateur]:
    return db.session.query(Utilisateur).filter_by(email=email).first()


def get_by_pseudo(pseudo: str) -> Optional[Utilisateur]:
    return db.session.query(Utilisateur).filter_by(pseudo=pseudo).first()


def create(pseudo: str, email: str, mot_de_passe_hash: str) -> Utilisateur:
    utilisateur = Utilisateur(
        pseudo=pseudo,
        email=email,
        mot_de_passe_hash=mot_de_passe_hash,
    )
    db.session.add(utilisateur)
    db.session.commit()
    return utilisateur


def incrementer_version_jeton(utilisateur: Utilisateur) -> None:
    """Révoque tous les jetons déjà émis pour ce compte (§2.3 du contrat)."""
    utilisateur.version_jeton += 1
    db.session.commit()
